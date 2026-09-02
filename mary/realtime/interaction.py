"""Realtime interaction lifecycle and interruption/anti-echo coordination.

This is deliberately deterministic. It does not generate speech, transcribe
speech, or call an LLM. It gives every client a shared lifecycle vocabulary so
voice, text, future streaming STT/TTS, and barge-in can coordinate around the
same canonical Mary runtime.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any
import uuid

from .attention import AttentionBus, AttentionSource
from .decision_trace import RealtimeDecisionTrace
from .speaker_scheduler import SpeakerScheduler
from .data_plane import RealtimeDataPlane, RealtimeDatum
from .speech_arbiter import SpeechOutputArbiter, SpeechRequest


class InteractionPhase(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    RESPONDING = "responding"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ERROR = "error"


@dataclass
class InteractionTurn:
    id: str
    source: str
    transport: str
    attention_event_id: str | None
    phase: InteractionPhase = InteractionPhase.THINKING
    interrupted: bool = False
    interruption_reason: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    response_chars: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["phase"] = self.phase.value
        return payload


class RealtimeInteractionCoordinator:
    VERSION = "13.1"

    def __init__(self, *, attention: AttentionBus | None = None, anti_echo: bool = True) -> None:
        self.decision_trace = RealtimeDecisionTrace()
        self.attention = attention or AttentionBus(decision_trace=self.decision_trace)
        if getattr(self.attention, "decision_trace", None) is None:
            try:
                self.attention.decision_trace = self.decision_trace
            except Exception:
                pass
        self.data_plane = RealtimeDataPlane()
        self.speech_arbiter = SpeechOutputArbiter()
        self.speaker_scheduler = SpeakerScheduler(trace=self.decision_trace)
        self.anti_echo = bool(anti_echo)
        self._lock = RLock()
        self._phase = InteractionPhase.IDLE
        self._active_turn: InteractionTurn | None = None
        self._speech_turn_id: str | None = None
        self._interrupt_generation = 0
        self._stats = {
            "turns": 0,
            "initiative_turns": 0,
            "speech_starts": 0,
            "interruptions": 0,
            "suppressed_echo_inputs": 0,
            "vad_candidates": 0,
            "vad_confirmed_starts": 0,
            "vad_false_starts": 0,
        }
        self._voice_activity = {
            "active": False,
            "confirmed": False,
            "source": "",
            "confidence": None,
        }
        self._last_transition = {
            "from": InteractionPhase.IDLE.value,
            "to": InteractionPhase.IDLE.value,
            "reason": "startup",
        }

    @staticmethod
    def _source_for_surface(surface: str, *, voice: bool = False) -> AttentionSource:
        if voice:
            return AttentionSource.CREATOR_SPEECH
        return AttentionSource.CREATOR_TEXT

    def _transition(self, phase: InteractionPhase, *, reason: str) -> None:
        previous = self._phase
        self._phase = phase
        self._last_transition = {
            "from": previous.value,
            "to": phase.value,
            "reason": str(reason or "unspecified")[:160],
        }
        if self._active_turn is not None:
            self._active_turn.phase = phase

    def begin_turn(
        self,
        text: str,
        *,
        surface: str = "runtime",
        transport: str = "direct",
        voice: bool = False,
    ) -> InteractionTurn:
        value = " ".join(str(text or "").split()).strip()
        if not value:
            raise ValueError("Realtime turns require non-empty input.")
        with self._lock:
            if self._phase == InteractionPhase.SPEAKING:
                self.interrupt(reason="new_creator_input", by_source="creator_speech" if voice else "creator_text")
            source = self._source_for_surface(surface, voice=voice)
            self.data_plane.publish(
                RealtimeDatum(
                    kind="creator_speech" if voice else "creator_text",
                    source=str(surface or "runtime"),
                    summary=value,
                    salience=1.0,
                    metadata={"transport": transport},
                )
            )
            event = self.attention.publish(
                source,
                value,
                priority=0 if voice else 5,
                importance=1.0,
                interruptible=False,
                metadata={"surface": surface, "transport": transport},
            )
            # Creator input is already being processed by this call, so claim it
            # immediately instead of leaving it as pending background work.
            self.attention.claim(event.id)
            turn = InteractionTurn(
                id=f"interaction_{uuid.uuid4().hex[:12]}",
                source=str(surface or "runtime")[:60],
                transport=str(transport or "direct")[:60],
                attention_event_id=event.id,
                phase=InteractionPhase.THINKING,
            )
            self._active_turn = turn
            self._stats["turns"] += 1
            self._transition(InteractionPhase.THINKING, reason="creator_input_claimed")
            return turn

    def begin_initiative(
        self,
        summary: str,
        *,
        surface: str = "presence",
        transport: str = "core",
    ) -> InteractionTurn:
        """Begin a Mary-initiated turn without publishing creator attention.

        The caller must already have passed Presence arbitration.  This method
        only coordinates lifecycle/interruptibility and deliberately does not
        reinterpret environmental context as creator speech/text.
        """
        value = " ".join(str(summary or "").split()).strip()
        if not value:
            raise ValueError("Initiative turns require non-empty grounded context.")
        with self._lock:
            if self._phase != InteractionPhase.IDLE:
                raise RuntimeError(f"Cannot begin initiative while realtime phase is {self._phase.value}.")
            turn = InteractionTurn(
                id=f"initiative_{uuid.uuid4().hex[:12]}",
                source=str(surface or "presence")[:60],
                transport=str(transport or "core")[:60],
                attention_event_id=None,
                phase=InteractionPhase.THINKING,
            )
            self._active_turn = turn
            self._stats["turns"] += 1
            self._stats["initiative_turns"] += 1
            self._transition(InteractionPhase.THINKING, reason="mary_initiative_claimed")
            return turn

    def mark_responding(self, *, response_text: str = "") -> None:
        with self._lock:
            if self._active_turn is not None:
                self._active_turn.response_chars = len(str(response_text or ""))
            self._transition(InteractionPhase.RESPONDING, reason="response_ready")

    def finish_turn(self, *, response_text: str = "") -> None:
        with self._lock:
            if self._active_turn is not None:
                self._active_turn.response_chars = len(str(response_text or ""))
                self._active_turn.phase = InteractionPhase.RESPONDING
            # Text generation is complete. Playback can subsequently move the
            # shared state to SPEAKING via reportSpeechStarted/desktop callbacks.
            self._transition(InteractionPhase.IDLE, reason="generation_complete")
            self._active_turn = None

    def fail_turn(self, reason: str) -> None:
        with self._lock:
            self._transition(InteractionPhase.ERROR, reason=reason)
            self._active_turn = None
            self._transition(InteractionPhase.IDLE, reason="error_recovered")

    def speech_started(self, *, turn_id: str | None = None, source: str = "client") -> None:
        with self._lock:
            self._speech_turn_id = str(turn_id or "") or None
            self._stats["speech_starts"] += 1
            self.data_plane.publish(
                RealtimeDatum(
                    kind="mary_speech_started",
                    source=source,
                    summary=str(turn_id or "speech"),
                    salience=.65,
                )
            )
            self.speaker_scheduler.set_floor("mary", reason=f"speech_started:{source}")
            self.decision_trace.record("speech", "started", "Mary audio acquired presentation floor", source=source, target="audience")
            self._transition(InteractionPhase.SPEAKING, reason=f"speech_started:{source}")

    def speech_ended(self, *, reason: str = "speech_finished") -> None:
        with self._lock:
            self._speech_turn_id = None
            self.speech_arbiter.finish_active()
            self.data_plane.publish(
                RealtimeDatum(
                    kind="mary_speech_ended",
                    source="speech_output",
                    summary=reason,
                    salience=.45,
                )
            )
            self.speaker_scheduler.set_floor("none", reason=reason)
            self.decision_trace.record("speech", "ended", reason, source="mary", target="audience")
            self._transition(InteractionPhase.IDLE, reason=reason)


    def report_voice_activity(
        self,
        active: bool,
        *,
        confirmed: bool = False,
        source: str = "vad",
        confidence: float | None = None,
    ) -> dict[str, Any]:
        """Report VAD activity without letting a false start interrupt Mary.

        Open-LLM-VTuber and similar realtime systems distinguish raw VAD onset
        from a confirmed human speech start.  Candidate activity is useful for
        UI/latency preparation, but only *confirmed* speech may claim the human
        floor or barge into active Mary audio. Existing ``mark_listening``
        remains the backwards-compatible explicit-listening path.
        """
        with self._lock:
            source_value = str(source or "vad")[:64]
            confidence_value = None if confidence is None else max(0.0, min(1.0, float(confidence)))
            previous_active = bool(self._voice_activity.get("active"))
            previous_confirmed = bool(self._voice_activity.get("confirmed"))
            self._voice_activity = {
                "active": bool(active),
                "confirmed": bool(active and confirmed),
                "source": source_value,
                "confidence": confidence_value,
            }

            if active and not confirmed:
                if not previous_active:
                    self._stats["vad_candidates"] += 1
                self.data_plane.publish(RealtimeDatum(
                    kind="voice_activity_candidate", source=source_value,
                    summary="possible human speech", salience=.35,
                    metadata={"confirmed": False, "confidence": confidence_value},
                ))
                self.decision_trace.record(
                    "barge_in", "candidate",
                    "voice activity observed but speech start is not confirmed",
                    score=confidence_value, source=source_value, target="mary",
                )
            elif active and confirmed:
                if not previous_confirmed:
                    self._stats["vad_confirmed_starts"] += 1
                self.decision_trace.record(
                    "barge_in", "confirmed", "confirmed human speech start",
                    score=confidence_value, source=source_value, target="mary",
                )
                # RLock is re-entrant; reuse the canonical explicit-listening
                # transition rather than creating a second interruption path.
                self.mark_listening(True, source=source_value)
            else:
                if previous_active and not previous_confirmed:
                    self._stats["vad_false_starts"] += 1
                    self.decision_trace.record(
                        "barge_in", "dismissed",
                        "voice activity ended before confirmed speech",
                        source=source_value, target="mary",
                    )
                if previous_confirmed and self._phase == InteractionPhase.LISTENING:
                    self.mark_listening(False, source=source_value)

            return dict(self._voice_activity)

    def mark_listening(self, active: bool, *, source: str = "microphone") -> None:
        with self._lock:
            if active:
                if self._phase == InteractionPhase.SPEAKING:
                    self.interrupt(reason="microphone_barge_in", by_source=source)
                self.speaker_scheduler.set_floor("creator", reason=f"listening:{source}")
                self._transition(InteractionPhase.LISTENING, reason=f"listening:{source}")
            elif self._phase == InteractionPhase.LISTENING:
                self.speaker_scheduler.set_floor("none", reason=f"listening_stopped:{source}")
                self._transition(InteractionPhase.IDLE, reason=f"listening_stopped:{source}")

    def mark_transcribing(self, active: bool, *, source: str = "stt") -> None:
        with self._lock:
            if active:
                self.speaker_scheduler.set_floor("creator", reason=f"transcribing:{source}")
                self._transition(InteractionPhase.TRANSCRIBING, reason=f"transcribing:{source}")
            elif self._phase == InteractionPhase.TRANSCRIBING:
                self.speaker_scheduler.set_floor("none", reason=f"transcription_finished:{source}")
                self._transition(InteractionPhase.IDLE, reason=f"transcription_finished:{source}")

    def interrupt(self, *, reason: str = "barge_in", by_source: str = "creator") -> int:
        with self._lock:
            self._interrupt_generation += 1
            self._stats["interruptions"] += 1
            if self._active_turn is not None:
                self._active_turn.interrupted = True
                self._active_turn.interruption_reason = str(reason)[:160]
            self._speech_turn_id = None
            interrupted = self.speech_arbiter.interrupt_active(reason=reason)
            self.speaker_scheduler.set_floor("creator" if "creator" in str(by_source).casefold() or "microphone" in str(by_source).casefold() else "none", reason=f"interrupt:{reason}")
            self.decision_trace.record(
                "speech", "interrupted", reason, source=by_source, target="mary",
                metadata={"had_active_speech": interrupted is not None},
            )
            self.data_plane.publish(
                RealtimeDatum(
                    kind="speech_interrupted",
                    source=by_source,
                    summary=reason,
                    salience=.95,
                )
            )
            self._transition(InteractionPhase.INTERRUPTED, reason=f"{reason}:{by_source}")
            return self._interrupt_generation

    def request_speech(
        self,
        text: str,
        *,
        source: str = "mary",
        target: str = "creator",
        priority: int = 50,
        interruptible: bool = True,
        can_interrupt: bool = False,
        ttl_seconds: float = 30.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ask the shared speech floor to schedule one Mary utterance.

        Surfaces may use this before beginning TTS.  Existing clients remain
        compatible because lifecycle callbacks still work independently.
        """
        request = SpeechRequest(
            text=str(text or ""),
            source=source,
            target=target,
            priority=priority,
            interruptible=interruptible,
            can_interrupt=can_interrupt,
            ttl_seconds=ttl_seconds,
            metadata=dict(metadata or {}),
        )
        decision = self.speech_arbiter.request(request)
        self.decision_trace.record(
            "speech_arbitration", decision.disposition.value, decision.reason,
            source=request.source, target=request.target,
            metadata={"priority": int(request.priority)},
        )
        return {"request": request.to_dict(), "arbitration": decision.to_dict()}

    def should_accept_audio_input(self, *, source: str = "microphone") -> bool:
        with self._lock:
            if self.anti_echo and self._phase == InteractionPhase.SPEAKING:
                self._stats["suppressed_echo_inputs"] += 1
                return False
            return True

    @property
    def interrupt_generation(self) -> int:
        with self._lock:
            return self._interrupt_generation

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "version": self.VERSION,
                "phase": self._phase.value,
                "anti_echo": self.anti_echo,
                "interrupt_generation": self._interrupt_generation,
                "speech_turn_id": self._speech_turn_id,
                "active_turn": self._active_turn.to_dict() if self._active_turn else None,
                "last_transition": dict(self._last_transition),
                "stats": dict(self._stats),
                "attention": self.attention.snapshot(),
                "data_plane": self.data_plane.snapshot(),
                "speech_arbiter": self.speech_arbiter.status(),
                "speaker_scheduler": self.speaker_scheduler.status(),
                "decision_trace": self.decision_trace.snapshot(),
                "voice_activity": dict(self._voice_activity),
                "semantics": "coordination state only; no identity or memory authority",
            }
