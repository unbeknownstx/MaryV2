"""Canonical Presence arbitration for MaryV2 realtime character behavior.

Presence is deliberately *not* a second personality or a background LLM loop.
Producers publish typed, grounded events.  Presence keeps those events bounded,
deduplicates obvious repeats, and later arbitrates whether one is worth an
unsolicited Mary beat.  Event ingestion and speech timing are separate so a
useful event is not permanently lost merely because it arrived while Mary was
speaking or inside the minimum-speak cooldown.
"""
from __future__ import annotations

import os
from collections import deque
from dataclasses import replace
from pathlib import Path
from threading import RLock
from time import monotonic
from typing import Any
import uuid

from mary.mind.behavior import CharacterBehaviorEngine
from mary.realtime import AttentionBus, AttentionSource, AttentionDisposition

from .bus import LiveContextBus
from .events import PresenceEvent, PresenceEventType
from .idle import IdleBehavior
from .initiative import InitiativeAction, InitiativeDecision, InitiativeEngine
from .pending_thoughts import PendingThoughtStore
from .live_scene import LiveScene, SceneParticipant


_RAW_MEDIA_KEYS = {
    "image", "frame", "screenshot", "raw_image", "pixels", "base64",
}


class PresenceManager:
    """One ephemeral event/initiative coordinator for canonical Mary."""

    def __init__(self, root: str | Path, *, attention: AttentionBus | None = None) -> None:
        self.root = Path(root)
        self.bus = LiveContextBus()
        self.attention = attention
        self.initiative = InitiativeEngine(
            min_speak_interval=float(
                os.getenv("MARY_PRESENCE_MIN_SPEAK_INTERVAL", "35") or 35
            ),
            threshold=float(os.getenv("MARY_PRESENCE_THRESHOLD", "0.72") or 0.72),
        )
        self.thoughts = PendingThoughtStore(self.root)
        self.idle = IdleBehavior()
        self.behavior = CharacterBehaviorEngine()
        self.scene = LiveScene()
        self._lock = RLock()
        self._initiative_candidates: deque[PresenceEvent] = deque(maxlen=64)
        self._candidate_created_at: dict[str, float] = {}
        self._last_claimed_event_id: str | None = None
        self._last_creator_activity_at = monotonic()
        self._last_curiosity_offer_at = 0.0
        self._dedupe_window = max(
            1.0,
            float(os.getenv("MARY_PRESENCE_DEDUPE_WINDOW", "20") or 20),
        )
        self._candidate_ttl = max(
            20.0,
            float(os.getenv("MARY_PRESENCE_CANDIDATE_TTL", "300") or 300),
        )
        self.mode = (
            os.getenv("MARY_PRESENCE_MODE", "companion").strip().lower()
            or "companion"
        )
        self.scene.set_mode(self.mode)
        self.visual_enabled = (
            os.getenv("MARY_VISUAL_CONTEXT", "off").strip().lower()
            not in {"", "off", "false", "0", "none"}
        )

    # ------------------------------------------------------------------
    # Activity timing
    # ------------------------------------------------------------------

    def note_creator_activity(self) -> None:
        """Record that the creator interacted with Mary.

        This is process-local timing only.  It is not relationship or memory
        evidence and is used solely to keep proactive curiosity from jumping
        into an active conversation.
        """

        with self._lock:
            self._last_creator_activity_at = monotonic()
        self.scene.set_floor("creator")
        self.scene.upsert_participant(
            SceneParticipant(
                participant_id="creator",
                role="creator",
                display_name="creator",
                speaking=True,
                attention=1.0,
            )
        )

    def represented_curiosity_ready(
        self,
        *,
        surface_visible: bool,
        focus_active: bool,
        realtime_phase: str,
        performance_mode: str = "private",
    ) -> bool:
        """Return whether an already-represented curiosity may surface now."""

        if not surface_visible or focus_active:
            return False
        if self.mode in {"off", "listen"}:
            return False
        if str(realtime_phase or "idle").strip().lower() != "idle":
            return False
        if str(performance_mode or "private").strip().lower() in {
            "focus", "stream", "performance",
        }:
            return False
        if not self.initiative.cooldown_ready():
            return False

        idle_required = max(
            60.0,
            float(os.getenv("MARY_PRESENCE_CURIOSITY_IDLE", "150") or 150),
        )
        gap_required = max(
            120.0,
            float(os.getenv("MARY_PRESENCE_CURIOSITY_GAP", "300") or 300),
        )
        now = monotonic()
        with self._lock:
            idle_seconds = max(0.0, now - self._last_creator_activity_at)
            since_curiosity = (
                float("inf")
                if self._last_curiosity_offer_at <= 0.0
                else max(0.0, now - self._last_curiosity_offer_at)
            )
        return idle_seconds >= idle_required and since_curiosity >= gap_required

    def mark_curiosity_offered(self) -> None:
        with self._lock:
            self._last_curiosity_offer_at = monotonic()

    # ------------------------------------------------------------------
    # Event ingestion
    # ------------------------------------------------------------------

    @staticmethod
    def _fingerprint(event_type: PresenceEventType, source: str, summary: str) -> str:
        return "|".join(
            (
                event_type.value,
                str(source or "").strip().casefold()[:80],
                " ".join(str(summary or "").split()).casefold()[:600],
            )
        )

    def _candidate_fingerprint(self, event: PresenceEvent) -> str:
        return self._fingerprint(event.event_type, event.source, event.summary)

    def _find_recent_duplicate_locked(
        self,
        *,
        fingerprint: str,
        now: float,
    ) -> PresenceEvent | None:
        for item in reversed(self._initiative_candidates):
            created = self._candidate_created_at.get(item.id, now)
            if now - created > self._dedupe_window:
                continue
            if self._candidate_fingerprint(item) == fingerprint:
                return item
        return None

    def publish(
        self,
        event_type: PresenceEventType,
        summary: str,
        *,
        source: str,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Publish one grounded event without deciding *when* Mary speaks.

        Salience is evaluated here, but cooldown/focus/realtime timing is not.
        Those gates belong to :meth:`claim_initiative`.  This mirrors a realtime
        performer queue: producers report what happened; one arbiter decides
        whether the character should interrupt.
        """

        safe_meta = dict(metadata or {})
        for key in list(safe_meta):
            if str(key).casefold() in _RAW_MEDIA_KEYS:
                safe_meta.pop(key, None)

        normalized_summary = " ".join(str(summary or "").split())[:1000]
        resolved_source = str(source or "presence")[:80]
        event = PresenceEvent(
            event_type=event_type,
            summary=normalized_summary,
            source=resolved_source,
            importance=max(0.0, min(1.0, float(importance))),
            metadata=safe_meta,
        )

        # Salience only.  Do not apply the speak cooldown during ingestion: an
        # event worth reacting to remains available until the later arbiter can
        # safely schedule it.
        decision = self.initiative.decide(
            event,
            mode=self.mode,
            creator_active=False,
        )

        # The canonical AttentionBus now owns the cheap react/note/drop gate.
        # Direct/addressed events are deterministic; ambient events may become
        # peripheral awareness without paying for a model turn.  This does not
        # grant authority and does not mutate durable memory.
        attention_judgment = None
        attention_source = AttentionSource.BACKGROUND
        if self.attention is not None:
            source_map = {
                PresenceEventType.CREATOR_SPEECH: AttentionSource.CREATOR_SPEECH,
                PresenceEventType.VISUAL_OBSERVATION: AttentionSource.VISUAL,
                PresenceEventType.SYSTEM: AttentionSource.SYSTEM,
            }
            attention_source = source_map.get(event.event_type, AttentionSource.BACKGROUND)
            addressed = bool(
                event.event_type in {PresenceEventType.CREATOR_SPEECH, PresenceEventType.TWITCH_MENTION}
                or safe_meta.get("addressed")
                or safe_meta.get("direct_to_mary")
            )
            noise = bool(safe_meta.get("noise"))
            try:
                attention_judgment = self.attention.judge(
                    attention_source,
                    importance=event.importance,
                    addressed=addressed,
                    noise=noise,
                    novelty=float(safe_meta.get("novelty", 0.5) or 0.5),
                )
                safe_meta["attention_disposition"] = attention_judgment.disposition.value
                safe_meta["attention_score"] = round(float(attention_judgment.score), 3)
                event = replace(event, metadata={**event.metadata, **safe_meta})
                if attention_judgment.disposition == AttentionDisposition.NOTE:
                    note = self.attention.note_peripheral(
                        attention_source,
                        event.summary,
                        importance=event.importance,
                        metadata={
                            "presence_event_id": event.id,
                            "presence_type": event.event_type.value,
                            "source": event.source,
                        },
                        dedupe_key=self._fingerprint(event.event_type, event.source, event.summary),
                    )
                    event = replace(event, metadata={**event.metadata, "peripheral_note_id": note.note_id})
                    decision = InitiativeDecision(
                        InitiativeAction.SILENCE,
                        float(attention_judgment.score),
                        "peripheral awareness noted without waking cognition",
                        False,
                    )
                elif attention_judgment.disposition == AttentionDisposition.DROP:
                    decision = InitiativeDecision(
                        InitiativeAction.SILENCE,
                        float(attention_judgment.score),
                        "attention gate dropped low-value ambient event",
                        False,
                    )
            except Exception:
                attention_judgment = None

        fingerprint = self._candidate_fingerprint(event)
        now = monotonic()
        if decision.speak:
            with self._lock:
                duplicate = self._find_recent_duplicate_locked(
                    fingerprint=fingerprint,
                    now=now,
                )
            if duplicate is not None:
                coalesced = InitiativeDecision(
                    InitiativeAction.SILENCE,
                    float(decision.score),
                    "duplicate live-context event coalesced",
                    False,
                )
                return {
                    "event": duplicate.to_dict(),
                    "decision": coalesced.to_dict(),
                    "coalesced": True,
                }

        # Presence and Attention are two views of the same ephemeral event.
        # Keep the attention id on the Presence event so reacting to one also
        # removes its duplicate from the general context queue.
        if self.attention is not None and (
            attention_judgment is None
            or attention_judgment.disposition == AttentionDisposition.REACT
        ):
            try:
                attention_event = self.attention.publish(
                    attention_source,
                    event.summary,
                    importance=event.importance,
                    metadata={
                        "presence_event_id": event.id,
                        "presence_type": event.event_type.value,
                        "source": event.source,
                        "attention_disposition": (
                            attention_judgment.disposition.value if attention_judgment is not None else "react"
                        ),
                    },
                )
                event = replace(
                    event,
                    metadata={**event.metadata, "attention_event_id": attention_event.id},
                )
            except Exception:
                pass

        self.bus.publish(event)
        try:
            self.scene.observe(
                event_id=event.id,
                kind=event.event_type.value,
                source=event.source,
                summary=event.summary,
                importance=event.importance,
                metadata=event.metadata,
            )
        except Exception:
            # LiveScene is a disposable projection; event ingestion remains
            # authoritative even if the projection fails.
            pass

        if decision.action == InitiativeAction.HOLD_THOUGHT and not (
            attention_judgment is not None
            and attention_judgment.disposition in {AttentionDisposition.NOTE, AttentionDisposition.DROP}
        ):
            self.thoughts.add(
                event.summary,
                context=event.event_type.value,
                importance=event.importance,
                source=event.source,
            )
        elif decision.speak:
            event = replace(
                event,
                metadata={
                    **event.metadata,
                    "initiative_action": decision.action.value,
                    "initiative_score": round(float(decision.score), 3),
                },
            )
            with self._lock:
                self._initiative_candidates.append(event)
                self._candidate_created_at[event.id] = now

        return {
            "event": event.to_dict(),
            "decision": decision.to_dict(),
            "coalesced": False,
        }

    # ------------------------------------------------------------------
    # Arbitration
    # ------------------------------------------------------------------

    def _prune_stale_candidates_locked(self, now: float) -> int:
        if not self._initiative_candidates:
            return 0
        kept: deque[PresenceEvent] = deque(maxlen=64)
        dropped = 0
        for event in self._initiative_candidates:
            created = self._candidate_created_at.get(event.id, now)
            ttl = 45.0 if event.event_type == PresenceEventType.TWITCH_MENTION else self._candidate_ttl
            if now - created > ttl:
                dropped += 1
                attention_event_id = str(event.metadata.get("attention_event_id") or "").strip()
                if attention_event_id and self.attention is not None:
                    try:
                        self.attention.claim(attention_event_id)
                    except Exception:
                        pass
                self._candidate_created_at.pop(event.id, None)
                continue
            kept.append(event)
        self._initiative_candidates = kept
        return dropped

    def claim_initiative(
        self,
        *,
        focus_active: bool = False,
        realtime_phase: str = "idle",
        surface_visible: bool = True,
        initiative_gain: float = 1.0,
    ) -> dict[str, Any]:
        """Claim at most one grounded event worth an unsolicited Mary beat."""

        phase = str(realtime_phase or "idle").strip().lower()
        if not surface_visible:
            return self._no_initiative("surface_not_visible")
        if self.mode in {"off", "listen"}:
            return self._no_initiative("presence_mode_blocks_initiative")
        if phase != "idle":
            return self._no_initiative(f"realtime_phase_{phase}")
        if not self.initiative.cooldown_ready():
            return self._no_initiative("speak_cooldown")

        gain = max(0.15, min(1.5, float(initiative_gain)))
        now = monotonic()
        with self._lock:
            stale_dropped = self._prune_stale_candidates_locked(now)
            candidates = list(self._initiative_candidates)
        if not candidates and self.attention is not None and not focus_active:
            # A repeatedly noticed peripheral event may become worth mentioning
            # after the creator has the floor again. This is still grounded in
            # an observed note; no model invents the topic.
            try:
                peripheral = self.attention.peripheral(3)
            except Exception:
                peripheral = []
            for note in peripheral:
                importance = float(getattr(note, "importance", 0.0) or 0.0)
                times_seen = int(getattr(note, "times_seen", 1) or 1)
                if importance < .86 and not (importance >= .62 and times_seen >= 3):
                    continue
                candidate = PresenceEvent(
                    event_type=PresenceEventType.SYSTEM,
                    summary=str(getattr(note, "summary", ""))[:1000],
                    source=f"peripheral:{getattr(getattr(note, 'source', None), 'value', 'context')}",
                    importance=max(importance, .74),
                    metadata={
                        "peripheral_note_id": str(getattr(note, "note_id", "")),
                        "times_seen": times_seen,
                        "initiative_action": InitiativeAction.REACT.value,
                    },
                )
                with self._lock:
                    self._initiative_candidates.append(candidate)
                    self._candidate_created_at[candidate.id] = now
                    candidates = list(self._initiative_candidates)
                break
        if not candidates:
            payload = self._no_initiative("no_grounded_candidate")
            payload["stale_dropped"] = stale_dropped
            return payload

        # Highest adjusted salience wins; FIFO breaks ties. Focus is not
        # absolute silence, but only truly strong events can cut through it.
        ranked = sorted(
            enumerate(candidates),
            key=lambda pair: (float(pair[1].importance) * gain, -pair[0]),
            reverse=True,
        )
        selected: PresenceEvent | None = None
        for _index, event in ranked:
            score = max(0.0, min(1.0, float(event.importance) * gain))
            if (
                focus_active
                and score < 0.92
                and event.event_type != PresenceEventType.TWITCH_MENTION
            ):
                continue
            if score < max(0.58, self.initiative.threshold * 0.82):
                continue
            selected = event
            break
        if selected is None:
            payload = self._no_initiative("candidate_below_current_gate")
            payload["stale_dropped"] = stale_dropped
            return payload

        with self._lock:
            self._initiative_candidates = deque(
                (event for event in self._initiative_candidates if event.id != selected.id),
                maxlen=64,
            )
            self._candidate_created_at.pop(selected.id, None)
            self._last_claimed_event_id = selected.id

        attention_event_id = str(selected.metadata.get("attention_event_id") or "").strip()
        if attention_event_id and self.attention is not None:
            try:
                self.attention.claim(attention_event_id)
            except Exception:
                pass

        peripheral_note_id = str(selected.metadata.get("peripheral_note_id") or "").strip()
        if peripheral_note_id and self.attention is not None:
            try:
                self.attention.claim_peripheral([peripheral_note_id])
            except Exception:
                pass

        self.scene.set_floor("mary", realtime_phase="thinking")
        self.scene.set_context(
            mary_target=(
                str(selected.metadata.get("display_name") or "chat")
                if selected.event_type in {PresenceEventType.TWITCH_CHAT, PresenceEventType.TWITCH_MENTION}
                else "creator"
            )
        )

        return {
            "speak": True,
            "candidate": selected.to_dict(),
            "authority": "environment_context_only",
            "reason": "grounded_presence_candidate",
            "stale_dropped": stale_dropped,
        }

    def mark_spoken(self, *, event_id: str | None = None) -> None:
        self.initiative.mark_spoken()
        self.scene.set_floor("none", realtime_phase="idle")
        if event_id:
            self._last_claimed_event_id = str(event_id)[:120]

    def requeue_initiative(self, event_payload: dict[str, Any] | PresenceEvent | None) -> None:
        """Return a claimed Presence event after a failed cognition attempt."""

        if event_payload is None:
            return
        if isinstance(event_payload, PresenceEvent):
            event = event_payload
        elif isinstance(event_payload, dict):
            try:
                event = PresenceEvent(
                    event_type=PresenceEventType(
                        str(event_payload.get("event_type") or "system")
                    ),
                    summary=str(event_payload.get("summary") or "")[:1000],
                    source=str(event_payload.get("source") or "presence")[:80],
                    importance=max(
                        0.0,
                        min(1.0, float(event_payload.get("importance", 0.5) or 0.5)),
                    ),
                    metadata=dict(event_payload.get("metadata") or {}),
                    created_at=str(event_payload.get("created_at") or ""),
                    id=(
                        str(event_payload.get("id") or "")
                        or f"presence_{uuid.uuid4().hex[:12]}"
                    ),
                )
            except Exception:
                return
        else:
            return
        if not event.summary:
            return
        with self._lock:
            if not any(item.id == event.id for item in self._initiative_candidates):
                self._initiative_candidates.appendleft(event)
                self._candidate_created_at[event.id] = monotonic()

    @staticmethod
    def _no_initiative(reason: str) -> dict[str, Any]:
        return {
            "speak": False,
            "candidate": None,
            "authority": "environment_context_only",
            "reason": str(reason or "silence")[:120],
        }

    # ------------------------------------------------------------------
    # Cheap local behavior / observability
    # ------------------------------------------------------------------

    def idle_tick(self, *, focus_active: bool = False) -> dict[str, Any]:
        action = self.idle.choose({"animation"} if focus_active else None)
        decision = self.behavior.idle_decision(
            focus_active=focus_active,
            pending_thoughts=self.thoughts.active(8),
            idle_action=action.to_dict(),
        )
        return {
            "action": action.to_dict(),
            "behavior": decision.to_dict(),
            "mode": self.mode,
            "focus_quiet": bool(focus_active),
        }

    def snapshot(self) -> dict[str, Any]:
        now = monotonic()
        with self._lock:
            creator_idle = max(0.0, now - self._last_creator_activity_at)
            curiosity_gap = (
                None
                if self._last_curiosity_offer_at <= 0.0
                else max(0.0, now - self._last_curiosity_offer_at)
            )
            candidate_count = len(self._initiative_candidates)
        return {
            "mode": self.mode,
            "visual_enabled": self.visual_enabled,
            "recent": self.bus.snapshot(12),
            "pending_thoughts": self.thoughts.active(8),
            "initiative_candidates": candidate_count,
            "seconds_since_spoken": self.initiative.seconds_since_spoken(),
            "seconds_since_creator_activity": round(creator_idle, 2),
            "seconds_since_curiosity_offer": (
                None if curiosity_gap is None else round(curiosity_gap, 2)
            ),
            "last_claimed_event_id": self._last_claimed_event_id,
            "attention": self.attention.snapshot() if self.attention is not None else None,
            "live_scene": self.scene.snapshot(),
            "policy": (
                "typed ephemeral context; ingestion is separate from speech arbitration; "
                "silence is valid; environmental text never gains creator/system authority"
            ),
        }
