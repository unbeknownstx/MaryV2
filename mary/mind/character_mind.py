"""Mary's fast local character-mind coordinator.

This layer decides whether a turn can be handled by already represented local
state before invoking a language model.  It does not replace cognition; it is a
low-latency front porch to cognition.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
from threading import RLock
from time import monotonic
from typing import Any

from mary.cognition.intent import Intent
from mary.conversation.lanes import LaneDecision, classify_conversation_lane
from .dialogue_policy import LocalDialoguePolicy
from .hot_state import HotMindState
from .local_authority_confirmation import confirm_dialogue_plan_authority
from .local_composer_v2 import ProceduralLocalComposerV2
from .local_models import OllamaModelLab
from .local_response_audit import audit_local_response
from .local_response_projector import project_canonical_response_plan
from .reservoir import CognitiveReservoir
from .response_risk import ResponseRiskClass, classify_response_risk
from .sources import authoritative_records


@dataclass(frozen=True)
class LocalMindResult:
    handled: bool
    response: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class CharacterMind:
    def __init__(self, mary: Any, *, reservoir: CognitiveReservoir | None = None) -> None:
        self.mary = mary
        self.hot = HotMindState()
        self.reservoir = reservoir or CognitiveReservoir.in_memory()
        self.policy = LocalDialoguePolicy()
        self.composer = ProceduralLocalComposerV2()
        self._phrase_history: deque[str] = deque(maxlen=8)
        self._phrase_history_lock = RLock()
        self.enabled = os.getenv("MARY_LOCAL_MIND_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
        self.local_dialogue_enabled = os.getenv("MARY_LOCAL_DIALOGUE_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
        self.last_result: dict[str, Any] = {}
        self.reservoir_dirty = False
        self.hot.refresh(mary)

    def configure_persistence(self, path: str | Path, *, rebuild: bool | None = None) -> None:
        old = self.reservoir
        max_records = int(os.getenv("MARY_RESERVOIR_MAX_RECORDS", "50000") or 50000)
        max_mb = int(os.getenv("MARY_RESERVOIR_MAX_MB", "512") or 512)
        self.reservoir = CognitiveReservoir(path, max_records=max_records, max_megabytes=max_mb)
        try:
            old.close()
        except Exception:
            pass
        should_rebuild = self.reservoir.status().get("records", 0) == 0 if rebuild is None else bool(rebuild)
        if should_rebuild:
            self.rebuild_reservoir()

    def configure_ephemeral(self, *, rebuild: bool = True) -> None:
        """Use an in-memory derived reservoir for temporary/test runtimes.

        This keeps release verification and other disposable MaryApplication
        instances from leaving SQLite file handles behind on Windows while
        preserving the exact same retrieval/authority semantics. Canonical
        desktop/runtime state continues to use the persistent reservoir by
        default.
        """
        old = self.reservoir
        self.reservoir = CognitiveReservoir.in_memory()
        try:
            old.close()
        except Exception:
            pass
        if rebuild:
            self.rebuild_reservoir()

    def close(self) -> None:
        """Release derived local-mind resources deterministically."""
        with self._phrase_history_lock:
            self._phrase_history.clear()
        try:
            self.reservoir.close()
        except Exception:
            pass

    def rebuild_reservoir(self) -> int:
        count = self.reservoir.rebuild(authoritative_records(self.mary))
        self.reservoir_dirty = False
        return count

    def maintenance(self, *, force: bool = False) -> dict[str, Any]:
        """Refresh derived reservoir state outside the response-critical path."""
        rebuilt = 0
        if force or self.reservoir_dirty:
            rebuilt = self.rebuild_reservoir()
        return {"rebuilt": rebuilt, "dirty": self.reservoir_dirty, "reservoir": self.reservoir.status()}

    def refresh(self, *, rebuild_reservoir: bool = False) -> None:
        self.hot.refresh(self.mary)
        if rebuild_reservoir:
            self.rebuild_reservoir()

    def prompt_hits(self, text: str, *, limit: int = 5) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        hits = self.reservoir.search(text, limit=limit, minimum_confidence=0.65)
        return [
            {
                "content": hit.content,
                "kind": hit.kind,
                "authority": hit.authority,
                "confidence": round(hit.confidence, 3),
                "source": hit.source,
            }
            for hit in hits
        ]

    def try_respond(self, text: str, *, intent: Intent | None, context: dict[str, Any]) -> LocalMindResult:
        started = monotonic()
        if not self.enabled or not self.local_dialogue_enabled:
            return LocalMindResult(False, metadata={"reason": "local mind disabled"})
        # Explicitly injected test/custom routers retain their requested
        # cognition path. This keeps dependency-injection tests meaningful while
        # the canonical runtime still uses Mary's local reflex layer.
        # This is detected structurally so the local path never calls a provider,
        # including provider-name methods, merely to decide whether to run.
        if self._uses_injected_router():
            return LocalMindResult(False, metadata={"reason": "injected test router"})

        mind_state = self._mind_state(context)
        disposition = mind_state.get("disposition")
        represented_preferred_length = (
            str(disposition.get("preferred_length") or "").strip()
            if isinstance(disposition, Mapping)
            else ""
        )
        intent_name = intent.intent_type.value if intent is not None else ""
        policy_started = monotonic()
        try:
            hot = self.hot.snapshot() or self.hot.refresh(self.mary)
            plan = self.policy.plan(
                text,
                intent=intent,
                hot_state=hot,
                reservoir=self.reservoir,
            )
        except Exception:
            lane = classify_conversation_lane(
                text,
                intent_name=intent_name,
                preferred_length=represented_preferred_length,
            )
            metadata = self._base_metadata(
                plan=None,
                lane=lane,
                response_class=ResponseRiskClass.THINKING_REQUIRED.value,
                classification_ms=_elapsed_ms(policy_started),
                canonical_plan=None,
            )
            return self._escalate(
                metadata,
                reason="local_policy_failed",
                started=started,
            )

        preferred_length = represented_preferred_length or (
            plan.target_length if plan.local else ""
        )
        lane = classify_conversation_lane(
            text,
            intent_name=intent_name,
            preferred_length=preferred_length,
        )

        classification_started = monotonic()
        try:
            owner_confirmations = confirm_dialogue_plan_authority(
                self.mary,
                plan,
            )
            projection = project_canonical_response_plan(
                dialogue_plan=plan,
                input_text=text,
                lane=lane,
                mind_state=mind_state,
                hot_state=hot,
                owner_confirmations=owner_confirmations,
            )
            decision = classify_response_risk(
                dialogue=plan,
                intent=intent,
                lane=lane,
                authority=projection.authority_context,
            )
            canonical = projection.canonical_plan
            canonical_view = canonical.to_dict() if canonical is not None else None
        except Exception:
            metadata = self._base_metadata(
                plan=plan,
                lane=lane,
                response_class=ResponseRiskClass.THINKING_REQUIRED.value,
                classification_ms=_elapsed_ms(classification_started),
                canonical_plan=None,
            )
            return self._escalate(
                metadata,
                reason="local_classification_failed",
                started=started,
            )
        classification_ms = _elapsed_ms(classification_started)
        metadata = self._base_metadata(
            plan=plan,
            lane=lane,
            response_class=decision.response_class.value,
            classification_ms=classification_ms,
            canonical_plan=canonical_view,
        )

        if decision.response_class not in {
            ResponseRiskClass.PRECISION_LOCAL,
            ResponseRiskClass.SOCIAL_LOW_RISK,
        }:
            reason = (
                "response_risk_thinking_required"
                if decision.response_class == ResponseRiskClass.THINKING_REQUIRED
                else "response_risk_open_conversation"
            )
            return self._escalate(
                metadata,
                reason=reason,
                started=started,
            )

        if canonical is None:
            return self._escalate(
                metadata,
                reason=projection.escalation_reason or "canonical_plan_incomplete",
                started=started,
            )

        composer_started = monotonic()
        try:
            realization = self.composer.compose(
                canonical.realization,
                seed=self._response_seed(text, canonical.plan_id),
                variation_ordinal=self._history_size(),
                recent_phrase_history=self._recent_phrase_history(
                    mind_state=mind_state,
                ),
            )
        except Exception:
            metadata["local_composer_ms"] = _elapsed_ms(composer_started)
            return self._escalate(
                metadata,
                reason="local_composer_v2_failed",
                started=started,
            )
        metadata["local_composer_ms"] = _elapsed_ms(composer_started)

        audit_started = monotonic()
        try:
            audit = audit_local_response(canonical, realization)
        except Exception:
            metadata["local_audit_ms"] = _elapsed_ms(audit_started)
            return self._escalate(
                metadata,
                reason="local_audit_failed",
                started=started,
            )
        metadata["local_audit_ms"] = _elapsed_ms(audit_started)
        metadata["local_audit"] = audit.to_dict()
        if not audit.accepted or not realization.text.strip():
            return self._escalate(
                metadata,
                reason="local_audit_rejected",
                started=started,
            )

        response = realization.text.strip()
        with self._phrase_history_lock:
            self._phrase_history.append(response)
        metadata.update({
            "response_engine": "local_composer_v2",
            "escalation_reason": None,
            "elapsed_ms": _elapsed_ms(started),
            "reservoir_records": self._reservoir_record_count(),
            "local_only": True,
        })
        result = LocalMindResult(
            True,
            response=response,
            confidence=plan.confidence,
            metadata=metadata,
        )
        self.last_result = self._diagnostic_metadata(metadata)
        return result

    def _base_metadata(
        self,
        *,
        plan: Any | None,
        lane: LaneDecision,
        response_class: str,
        classification_ms: float,
        canonical_plan: dict[str, Any] | None,
    ) -> dict[str, Any]:
        lane_view = lane.to_dict()
        plan_view = (
            {
                "act": plan.act.value,
                "confidence": round(float(plan.confidence), 3),
                "local": bool(plan.local),
                "target_length": str(plan.target_length),
            }
            if plan is not None
            else None
        )
        return {
            "plan": plan_view,
            "canonical_plan": canonical_plan,
            "response_class": response_class,
            "response_engine": None,
            "classification_ms": classification_ms,
            "local_composer_ms": 0.0,
            "local_audit_ms": 0.0,
            "escalation_reason": None,
            "shadow_enabled": False,
            "shadow_model": None,
            "shadow_ms": None,
            "lane": dict(lane_view),
            "conversation_lane": dict(lane_view),
            "local_only": False,
        }

    def _escalate(
        self,
        metadata: dict[str, Any],
        *,
        reason: str,
        started: float,
    ) -> LocalMindResult:
        metadata["escalation_reason"] = _bounded_reason(reason)
        metadata["elapsed_ms"] = _elapsed_ms(started)
        result = LocalMindResult(False, metadata=metadata)
        self.last_result = self._diagnostic_metadata(metadata)
        return result

    def _mind_state(self, context: Any) -> Mapping[str, Any]:
        if not isinstance(context, Mapping):
            return {}
        value = context.get("mind_state")
        return value if isinstance(value, Mapping) else {}

    def _recent_phrase_history(
        self,
        *,
        mind_state: Mapping[str, Any],
    ) -> tuple[str, ...]:
        continuity = mind_state.get("continuity")
        raw_recent = (
            continuity.get("recent_mary_responses")
            if isinstance(continuity, Mapping)
            else ()
        )
        context_recent: list[str] = []
        if (
            isinstance(raw_recent, Sequence)
            and not isinstance(raw_recent, (str, bytes, bytearray, Mapping))
        ):
            for item in tuple(raw_recent)[-8:]:
                if isinstance(item, str):
                    value = " ".join(item.split()).strip()
                    if value:
                        context_recent.append(value[:320])
        with self._phrase_history_lock:
            process_recent = tuple(self._phrase_history)
        return tuple((context_recent + list(process_recent))[-8:])

    def _history_size(self) -> int:
        with self._phrase_history_lock:
            return len(self._phrase_history)

    def _response_seed(self, text: str, plan_id: str) -> int:
        material = f"{plan_id}|{text}"
        return int.from_bytes(
            hashlib.sha256(material.encode("utf-8")).digest()[:8],
            "big",
            signed=False,
        )

    def _uses_injected_router(self) -> bool:
        try:
            router = getattr(self.mary, "llm", None)
            configured = getattr(getattr(router, "config", None), "llm", None)
            provider = str(
                getattr(configured, "provider", "") or ""
            ).strip().lower()
        except Exception:
            return True
        if provider in {"test", "fake", "mock"}:
            return True
        return type(router).__module__ != "mary.llm.router"

    def _reservoir_record_count(self) -> int:
        try:
            return max(0, int(self.reservoir.status().get("records", 0) or 0))
        except Exception:
            return 0

    def _diagnostic_metadata(self, metadata: Mapping[str, Any]) -> dict[str, Any]:
        """Retain no creator/Mary semantic values in status diagnostics."""

        safe: dict[str, Any] = {}
        plan = metadata.get("plan")
        if isinstance(plan, Mapping):
            safe["plan"] = {
                key: plan.get(key)
                for key in ("act", "local", "target_length")
                if key in plan
            }
        for key in (
            "response_class",
            "response_engine",
            "classification_ms",
            "local_composer_ms",
            "local_audit_ms",
            "escalation_reason",
            "shadow_enabled",
            "shadow_model",
            "shadow_ms",
            "elapsed_ms",
            "local_only",
        ):
            if key in metadata:
                safe[key] = metadata.get(key)
        lane = metadata.get("conversation_lane")
        if isinstance(lane, Mapping):
            safe["conversation_lane"] = {
                key: lane.get(key)
                for key in (
                    "lane",
                    "latency_target_ms",
                    "allow_model_revision",
                )
                if key in lane
            }
        return safe

    def observe_completed_turn(self, result: Any) -> None:
        """Refresh cheap state after a turn; rebuild only after represented learning."""
        metadata = dict(getattr(result, "metadata", {}) or {})
        system_action = str(metadata.get("system_action") or "").strip().lower()
        learned = bool(
            metadata.get("natural_relationship_learning")
            or metadata.get("shared_work_learning")
            or system_action in {
                "memory_store", "relationship_share", "creator_directive",
                "remember", "remember_fact", "remember_event",
            }
        )
        # Keep the cheap RAM projection current immediately, but defer the
        # potentially larger derived-index rebuild until idle/close/explicit
        # maintenance so learning does not extend perceived response latency.
        self.refresh(rebuild_reservoir=False)
        if learned:
            self.reservoir_dirty = True

    def status(self) -> dict[str, Any]:
        with self._phrase_history_lock:
            phrase_history_count = len(self._phrase_history)
        return {
            "enabled": self.enabled,
            "local_dialogue_enabled": self.local_dialogue_enabled,
            "hot": self.hot.status(),
            "reservoir": self.reservoir.status(),
            "last_local_decision": deepcopy(self.last_result),
            "response_engine": "local_composer_v2",
            "phrase_history_count": phrase_history_count,
            "phrase_history_capacity": 8,
            "phrase_history_persistence": "process_local_only",
            "reservoir_dirty": bool(self.reservoir_dirty),
            "local_model_catalog": OllamaModelLab.catalog(),
            "semantics": "rebuildable local projection; canonical Mary state remains authoritative",
        }


def _elapsed_ms(started: float) -> float:
    return round(min(60_000.0, max(0.0, (monotonic() - started) * 1000.0)), 4)


def _bounded_reason(value: Any) -> str:
    text = " ".join(str(value or "local_escalation").split()).strip()
    return text[:160] or "local_escalation"
