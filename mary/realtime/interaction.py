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
        self.attention = attention or AttentionBus()
        self.anti_echo = bool(anti_echo)
        self._lock = RLock()
        self._phase = InteractionPhase.IDLE
        self._active_turn: InteractionTurn | None = None
        self._speech_turn_id: str | None = None
        self._interrupt_generation = 0
        self._stats = {
            "turns": 0,
            "speech_starts": 0,
            "interruptions": 0,
            "suppressed_echo_inputs": 0,
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
            self._transition(InteractionPhase.SPEAKING, reason=f"speech_started:{source}")

    def speech_ended(self, *, reason: str = "speech_finished") -> None:
        with self._lock:
            self._speech_turn_id = None
            self._transition(InteractionPhase.IDLE, reason=reason)

    def mark_listening(self, active: bool, *, source: str = "microphone") -> None:
        with self._lock:
            if active:
                if self._phase == InteractionPhase.SPEAKING:
                    self.interrupt(reason="microphone_barge_in", by_source=source)
                self._transition(InteractionPhase.LISTENING, reason=f"listening:{source}")
            elif self._phase == InteractionPhase.LISTENING:
                self._transition(InteractionPhase.IDLE, reason=f"listening_stopped:{source}")

    def mark_transcribing(self, active: bool, *, source: str = "stt") -> None:
        with self._lock:
            if active:
                self._transition(InteractionPhase.TRANSCRIBING, reason=f"transcribing:{source}")
            elif self._phase == InteractionPhase.TRANSCRIBING:
                self._transition(InteractionPhase.IDLE, reason=f"transcription_finished:{source}")

    def interrupt(self, *, reason: str = "barge_in", by_source: str = "creator") -> int:
        with self._lock:
            self._interrupt_generation += 1
            self._stats["interruptions"] += 1
            if self._active_turn is not None:
                self._active_turn.interrupted = True
                self._active_turn.interruption_reason = str(reason)[:160]
            self._speech_turn_id = None
            self._transition(InteractionPhase.INTERRUPTED, reason=f"{reason}:{by_source}")
            return self._interrupt_generation

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
                "semantics": "coordination state only; no identity or memory authority",
            }
