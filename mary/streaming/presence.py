"""Bridge platform-neutral chat into canonical Mary Presence.

The coordinator keeps hard social-floor rules deterministic while allowing a
replaceable FastBrain to improve the cheap *interest/attention* decision.  A
FastBrain may influence whether a chat message is worth Mary's attention; it
cannot grant authority, call tools, or bypass Presence/Attention provenance.
"""
from __future__ import annotations

from typing import Any

from mary.mind.fast_brain import DeterministicFastBrain, FastBrainProvider, FastBrainRequest
from mary.presence.live_scene import SceneParticipant
from mary.presence import PresenceEventType
from mary.realtime import SpeakerOpportunity, SpeakerScheduler, FloorDisposition
from .chat import ChatAggregator, ChatMessage, ChatSelection
from .social import AudienceRoster


_ACTION_WEIGHT = {"ignore": 0.15, "notice": 0.52, "respond": 0.84}


class StreamingPresenceCoordinator:
    VERSION = "2"

    def __init__(
        self,
        presence: Any,
        *,
        aggregator: ChatAggregator | None = None,
        fast_brain: FastBrainProvider | None = None,
        speaker_scheduler: SpeakerScheduler | None = None,
    ) -> None:
        self.presence = presence
        self.chat = aggregator or ChatAggregator()
        self.fast_brain: FastBrainProvider = fast_brain or DeterministicFastBrain()
        self.speaker_scheduler = speaker_scheduler or SpeakerScheduler()
        self.audience = AudienceRoster()
        self._last_fast_brain: dict[str, Any] | None = None
        self._stats = {
            "received": 0,
            "ignored": 0,
            "noticed": 0,
            "respond_candidates": 0,
            "fast_brain_calls": 0,
            "fast_brain_failures": 0,
            "floor_waits": 0,
            "floor_drops": 0,
        }

    @staticmethod
    def _action_for_score(score: float) -> str:
        return "respond" if score >= .67 else ("notice" if score >= .42 else "ignore")

    def _rerank_with_fast_brain(
        self,
        message: ChatMessage,
        baseline: ChatSelection,
        *,
        creator_speaking: bool,
    ) -> ChatSelection:
        # Floor ownership is not probabilistic. A learned/small model must not
        # talk Mary over the creator merely because it finds chat interesting.
        if creator_speaking:
            self._last_fast_brain = {
                "skipped": True,
                "reason": "creator_has_floor",
                "baseline": baseline.to_dict(),
            }
            return baseline

        try:
            result = self.fast_brain.classify(
                FastBrainRequest(
                    task="stream_attention",
                    text=message.text,
                    context={
                        "platform": message.platform,
                        "channel": message.channel,
                        "direct_to_mary": bool(message.direct_to_mary),
                        "baseline_action": baseline.action,
                        "baseline_score": baseline.score,
                    },
                    labels=("ignore", "notice", "respond"),
                )
            )
            self._stats["fast_brain_calls"] += 1
            result_payload = result.to_dict()
            self._last_fast_brain = result_payload
        except Exception as exc:  # noqa: BLE001 - specialist failure must be non-fatal
            self._stats["fast_brain_failures"] += 1
            self._last_fast_brain = {
                "error": type(exc).__name__,
                "fallback": "chat_aggregator",
            }
            return baseline

        label = str(result.label or "").strip().casefold()
        if label not in _ACTION_WEIGHT:
            return baseline

        # The specialist is a reranker, not the sole decision maker. Direct
        # messages already recognized by deterministic chat parsing retain a
        # strong floor so a quirky small model cannot silently erase them.
        specialist_score = _ACTION_WEIGHT[label] * max(.15, min(1.0, float(result.confidence)))
        score = baseline.score * .55 + specialist_score * .45
        if message.direct_to_mary and baseline.action == "respond":
            score = max(score, .67)
        score = max(0.0, min(1.0, score))
        action = self._action_for_score(score)
        reasons = tuple(baseline.reasons) + (f"fast_brain:{label}",)
        return ChatSelection(message, score, action, reasons)

    def ingest_chat(self, message: ChatMessage, *, creator_speaking: bool = False) -> dict[str, Any]:
        if not self.chat.add(message):
            return {"accepted": False, "reason": "duplicate_or_empty"}
        self._stats["received"] += 1
        baseline = self.chat.select(message, creator_speaking=creator_speaking)
        selection = self._rerank_with_fast_brain(
            message,
            baseline,
            creator_speaking=creator_speaking,
        )
        member = self.audience.observe(message, selection)

        # Ranking and floor ownership are separate concerns.  A tiny model may
        # think chat deserves a response, but creator/participant floor rules
        # remain deterministic in the shared realtime scheduler.
        floor_decision = None
        if selection.action == "respond":
            opportunity = SpeakerOpportunity(
                speaker_id="mary",
                source_kind="viewer",
                source_id=member.identity,
                target=member.identity,
                relevance=selection.score,
                direct=bool(message.direct_to_mary),
                priority=35 if message.direct_to_mary else 55,
                ttl_seconds=20.0,
                metadata={"platform": member.platform, "channel": message.channel},
            )
            floor_decision = self.speaker_scheduler.consider(
                opportunity,
                floor_owner="creator" if creator_speaking else None,
            )
            if floor_decision.disposition == FloorDisposition.WAIT:
                self._stats["floor_waits"] += 1
                selection = ChatSelection(
                    selection.message,
                    selection.score,
                    "notice",
                    tuple(selection.reasons) + ("speaker_floor:wait",),
                )
            elif floor_decision.disposition == FloorDisposition.DROP:
                self._stats["floor_drops"] += 1
                selection = ChatSelection(
                    selection.message,
                    selection.score,
                    "ignore",
                    tuple(selection.reasons) + ("speaker_floor:drop",),
                )

        self._stats[{"ignore": "ignored", "notice": "noticed", "respond": "respond_candidates"}[selection.action]] += 1
        try:
            self.presence.scene.upsert_participant(
                SceneParticipant(
                    participant_id=member.identity,
                    role="viewer",
                    display_name=member.display_name,
                    speaking=False,
                    attention=selection.score,
                    metadata={
                        "platform": member.platform,
                        "familiarity": round(member.familiarity, 3),
                        "messages_seen": member.messages_seen,
                    },
                )
            )
        except Exception:
            pass

        if selection.action == "ignore":
            return {
                "accepted": True,
                "selection": selection.to_dict(),
                "published": False,
                "fast_brain": self._last_fast_brain,
            }

        direct = bool(message.direct_to_mary or selection.action == "respond")
        event_type = PresenceEventType.TWITCH_MENTION if direct else PresenceEventType.TWITCH_CHAT
        published = self.presence.publish(
            event_type,
            f"{message.display_name}: {message.text}",
            source=f"{message.platform}:chat",
            importance=max(.25, selection.score),
            metadata={
                "message_id": message.message_id,
                "author_id": message.author_id,
                "display_name": message.display_name,
                "platform": message.platform,
                "channel": message.channel,
                "chat_action": selection.action,
                "chat_score": round(selection.score, 3),
                "fast_brain_provider": (self._last_fast_brain or {}).get("provider"),
                "fast_brain_model": (self._last_fast_brain or {}).get("model"),
                "floor_disposition": (floor_decision.disposition.value if floor_decision is not None else "not_considered"),
            },
        )
        return {
            "accepted": True,
            "selection": selection.to_dict(),
            "published": True,
            "presence": published,
            "fast_brain": self._last_fast_brain,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "stats": dict(self._stats),
            "chat": self.chat.snapshot(),
            "audience": self.audience.snapshot(),
            "fast_brain": {
                "type": type(self.fast_brain).__name__,
                "last": self._last_fast_brain,
                "authority": "ranking_only",
            },
            "speaker_scheduler": self.speaker_scheduler.status(),
            "policy": "stream input enters Presence as environment_context_only; it cannot authorize tools",
        }
