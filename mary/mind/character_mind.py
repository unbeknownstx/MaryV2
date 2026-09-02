"""Mary's bounded production-local character-mind coordinator.

The cognitive reservoir remains a rebuildable selector/index.  Eligible local
turns are projected into an immutable canonical response plan, realized by the
procedural V2 composer, and independently audited before any wording may leave
this layer.  Anything incomplete or authority-sensitive fails closed to Mary's
existing cognition/provider route.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
from time import monotonic
from typing import Any, Mapping

from mary.cognition.intent import Intent, IntentType
from mary.conversation.lanes import ConversationLane, LaneDecision, classify_conversation_lane
from .dialogue_policy import LocalDialoguePolicy
from .hot_state import HotMindState
from .local_authority_confirmation import confirm_dialogue_plan_authority
from .local_models import OllamaModelLab
from .local_response_audit import audit_local_response
from .local_response_projector import (
    project_canonical_response_plan,
    project_response_authority,
)
from .reservoir import CognitiveReservoir
from .hybrid_retrieval import HybridReservoirRetriever
from .sources import authoritative_records
from .production_local import (
    ProceduralLocalComposerV2, ResponseRiskClass, classify_local_response,
    LOCAL_ENGINE, THINKING_ESCALATION, OPEN_ESCALATION, COMPOSER_FAILURE,
)


@dataclass(frozen=True)
class LocalMindResult:
    handled: bool
    response: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class CharacterMind:
    """Fast deterministic front porch to Mary cognition.

    This object owns no canonical facts and never calls an LLM on its local
    path.  Its only process-local mutable conversational state is a bounded
    phrase-history used to avoid robotic repetition.
    """

    _PHRASE_HISTORY_LIMIT = 8

    def __init__(self, mary: Any, *, reservoir: CognitiveReservoir | None = None) -> None:
        self.mary = mary
        self.hot = HotMindState()
        self.reservoir = reservoir or CognitiveReservoir.in_memory()
        self.retrieval = HybridReservoirRetriever(self.reservoir)
        self.policy = LocalDialoguePolicy()
        self.composer = ProceduralLocalComposerV2()
        self.enabled = os.getenv("MARY_LOCAL_MIND_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
        self.local_dialogue_enabled = os.getenv("MARY_LOCAL_DIALOGUE_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
        self.last_result: dict[str, Any] = {}
        self.reservoir_dirty = False
        self._phrase_history: list[str] = []
        self.hot.refresh(mary)

    def configure_persistence(self, path: str | Path, *, rebuild: bool | None = None) -> None:
        old = self.reservoir
        max_records = int(os.getenv("MARY_RESERVOIR_MAX_RECORDS", "50000") or 50000)
        max_mb = int(os.getenv("MARY_RESERVOIR_MAX_MB", "512") or 512)
        self.reservoir = CognitiveReservoir(path, max_records=max_records, max_megabytes=max_mb)
        self.retrieval.reservoir = self.reservoir
        self.retrieval.configure_vector_index(Path(path).with_name("mary_vectors.sqlite3"))
        try:
            old.close()
        except Exception:
            pass
        should_rebuild = self.reservoir.status().get("records", 0) == 0 if rebuild is None else bool(rebuild)
        if should_rebuild:
            self.rebuild_reservoir()

    def configure_ephemeral(self, *, rebuild: bool = True) -> None:
        old = self.reservoir
        self.reservoir = CognitiveReservoir.in_memory()
        self.retrieval.reservoir = self.reservoir
        self.retrieval.configure_vector_index(None)
        try:
            old.close()
        except Exception:
            pass
        if rebuild:
            self.rebuild_reservoir()

    def close(self) -> None:
        try:
            self.retrieval.close()
        except Exception:
            pass
        try:
            self.reservoir.close()
        except Exception:
            pass

    def rebuild_reservoir(self) -> int:
        count = self.reservoir.rebuild(authoritative_records(self.mary))
        self.reservoir_dirty = False
        return count

    def maintenance(self, *, force: bool = False) -> dict[str, Any]:
        rebuilt = 0
        if force or self.reservoir_dirty:
            rebuilt = self.rebuild_reservoir()
        return {
            "rebuilt": rebuilt,
            "dirty": self.reservoir_dirty,
            "reservoir": self.reservoir.status(),
            "retrieval": self.retrieval.status(),
        }

    def rebuild_vectors(self, *, limit: int | None = None) -> dict[str, Any]:
        records = authoritative_records(self.mary)
        return self.retrieval.rebuild_vectors(records, limit=limit)

    def refresh(self, *, rebuild_reservoir: bool = False) -> None:
        self.hot.refresh(self.mary)
        if rebuild_reservoir:
            self.rebuild_reservoir()

    def prompt_hits(
        self,
        text: str,
        *,
        limit: int = 5,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        hits = self.retrieval.search(
            text,
            limit=limit,
            minimum_confidence=0.65,
            context=context,
        )
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

    @staticmethod
    def _ms(started: float) -> float:
        return max(0.0, min(60_000.0, round((monotonic() - started) * 1000.0, 4)))

    @staticmethod
    def _safe_plan(plan: Any) -> dict[str, Any]:
        try:
            return {
                "act": plan.act.value,
                "local": bool(plan.local),
                "target_length": str(plan.target_length),
            }
        except Exception:
            return {"act": "escalate", "local": False, "target_length": "brief"}

    def _base_metadata(
        self,
        *,
        plan: Any = None,
        lane: Any = None,
        response_class: str = ResponseRiskClass.THINKING_REQUIRED.value,
        escalation_reason: str | None = None,
        classification_ms: float = 0.0,
        local_composer_ms: float = 0.0,
        local_audit_ms: float = 0.0,
        response_engine: str | None = None,
        elapsed_ms: float = 0.0,
        local_only: bool = False,
    ) -> dict[str, Any]:
        lane_dict = lane.to_dict() if hasattr(lane, "to_dict") else {}
        return {
            "plan": self._safe_plan(plan),
            "response_class": str(response_class),
            "response_engine": response_engine,
            "classification_ms": float(classification_ms),
            "local_composer_ms": float(local_composer_ms),
            "local_audit_ms": float(local_audit_ms),
            "escalation_reason": escalation_reason,
            "shadow_enabled": False,
            "shadow_model": None,
            "shadow_ms": None,
            "conversation_lane": lane_dict,
            "lane": lane_dict,
            "elapsed_ms": float(elapsed_ms),
            "reservoir_records": self.reservoir.status().get("records", 0),
            "local_only": bool(local_only),
        }

    def _remember_last(self, metadata: Mapping[str, Any]) -> None:
        # Diagnostics intentionally retain only bounded control-plane facts.
        allowed = {
            "response_class", "response_engine", "classification_ms",
            "local_composer_ms", "local_audit_ms", "escalation_reason",
            "shadow_enabled", "shadow_model", "shadow_ms", "conversation_lane",
            "lane", "elapsed_ms", "reservoir_records", "local_only", "plan",
        }
        safe = {key: metadata.get(key) for key in allowed if key in metadata}
        for lane_key in ("conversation_lane", "lane"):
            lane_value = safe.get(lane_key)
            if isinstance(lane_value, Mapping):
                safe[lane_key] = {
                    key: lane_value.get(key)
                    for key in ("lane", "latency_target_ms", "allow_model_revision")
                    if key in lane_value
                }
        if "plan" in safe:
            safe["plan"] = self._safe_plan(type("PlanView", (), {
                "act": type("Act", (), {"value": safe["plan"].get("act", "escalate")})(),
                "local": safe["plan"].get("local", False),
                "target_length": safe["plan"].get("target_length", "brief"),
            })())
        safe.pop("lane", None) if safe.get("lane") == safe.get("conversation_lane") else None
        self.last_result = safe

    def _history_for(self, context: Mapping[str, Any]) -> tuple[str, ...]:
        continuity: Mapping[str, Any] = {}
        mind_state = context.get("mind_state") if isinstance(context, Mapping) else None
        if isinstance(mind_state, Mapping):
            raw = mind_state.get("continuity")
            if isinstance(raw, Mapping):
                continuity = raw
        external = continuity.get("recent_mary_responses", ())
        if not isinstance(external, (list, tuple)):
            external = ()
        values = [
            " ".join(str(item).split()).strip()[:320]
            for item in (*external, *self._phrase_history)
            if isinstance(item, str) and str(item).strip()
        ]
        return tuple(values[-self._PHRASE_HISTORY_LIMIT:])

    def try_respond(self, text: str, *, intent: Intent | None, context: dict[str, Any]) -> LocalMindResult:
        started = monotonic()
        if not self.enabled or not self.local_dialogue_enabled:
            meta = self._base_metadata(
                escalation_reason="local_mind_disabled",
                elapsed_ms=self._ms(started),
            )
            self._remember_last(meta)
            return LocalMindResult(False, metadata=meta)

        context_view: Mapping[str, Any] = context if isinstance(context, Mapping) else {}
        mind_state = context_view.get("mind_state")
        mind_state = mind_state if isinstance(mind_state, Mapping) else {}
        disposition = mind_state.get("disposition")
        disposition = disposition if isinstance(disposition, Mapping) else {}
        intent_type = intent.intent_type if isinstance(intent, Intent) else IntentType.UNKNOWN
        lane = classify_conversation_lane(
            text,
            intent_name=intent_type.value,
            preferred_length=str(disposition.get("preferred_length") or ""),
            explicit_paid_authorization=False,
        )
        hot = self.hot.snapshot() or self.hot.refresh(self.mary)

        classification_started = monotonic()
        try:
            plan = self.policy.plan(text, intent=intent, hot_state=hot, reservoir=self.reservoir)
            if (
                plan.local
                and plan.act.value == "react"
                and str(plan.slots.get("reaction_kind") or "").strip().lower() == "milestone"
            ):
                # A creator milestone can contain technical nouns such as
                # "tests" or "deploy" while still being a fact-free social
                # reaction. The local dialogue policy has already classified
                # the semantic act, so do not let keyword-only lane heuristics
                # force an unnecessary language-cortex call.
                lane = LaneDecision(
                    ConversationLane.SOCIAL_INSTANT,
                    "high-confidence local milestone reaction",
                    1_800,
                    False,
                )
            authority = project_response_authority(plan, lane=lane, input_text=text)
            risk = classify_local_response(
                dialogue=plan,
                intent=intent_type,
                lane=lane,
                authority=authority,
            )
        except Exception:
            classification_ms = self._ms(classification_started)
            meta = self._base_metadata(
                plan=None,
                lane=lane,
                response_class=ResponseRiskClass.THINKING_REQUIRED.value,
                escalation_reason="local_policy_failed",
                classification_ms=classification_ms,
                elapsed_ms=self._ms(started),
            )
            self._remember_last(meta)
            return LocalMindResult(False, metadata=meta)
        classification_ms = self._ms(classification_started)

        if risk.response_class in {
            ResponseRiskClass.OPEN_CONVERSATION,
            ResponseRiskClass.THINKING_REQUIRED,
        } or not plan.local:
            reason = (
                THINKING_ESCALATION
                if risk.response_class == ResponseRiskClass.THINKING_REQUIRED
                else OPEN_ESCALATION
            )
            meta = self._base_metadata(
                plan=plan,
                lane=lane,
                response_class=risk.response_class.value,
                escalation_reason=reason,
                classification_ms=classification_ms,
                elapsed_ms=self._ms(started),
            )
            self._remember_last(meta)
            return LocalMindResult(False, metadata=meta)

        confirmations = confirm_dialogue_plan_authority(self.mary, plan)
        projection = project_canonical_response_plan(
            dialogue_plan=plan,
            input_text=text,
            lane=lane,
            mind_state=mind_state,
            hot_state=hot,
            owner_confirmations=confirmations,
        )
        if projection.canonical_plan is None:
            meta = self._base_metadata(
                plan=plan,
                lane=lane,
                response_class=risk.response_class.value,
                escalation_reason=projection.escalation_reason,
                classification_ms=classification_ms,
                elapsed_ms=self._ms(started),
            )
            self._remember_last(meta)
            return LocalMindResult(False, metadata=meta)

        canonical = projection.canonical_plan
        history = self._history_for(context_view)
        seed_material = f"{text.strip().casefold()}|{getattr(canonical, 'semantic_fingerprint', '')}|{len(history)}"
        seed = int.from_bytes(hashlib.sha256(seed_material.encode("utf-8")).digest()[:16], "big", signed=False)
        # signed 128-bit contract
        if seed >= 2**127:
            seed -= 2**128

        compose_started = monotonic()
        try:
            realized = self.composer.compose(
                canonical.realization,
                seed=seed,
                variation_ordinal=min(len(history), 1_000_000),
                recent_phrase_history=history,
            )
        except Exception:
            composer_ms = self._ms(compose_started)
            meta = self._base_metadata(
                plan=plan,
                lane=lane,
                response_class=risk.response_class.value,
                escalation_reason=COMPOSER_FAILURE,
                classification_ms=classification_ms,
                local_composer_ms=composer_ms,
                elapsed_ms=self._ms(started),
            )
            self._remember_last(meta)
            return LocalMindResult(False, metadata=meta)
        composer_ms = self._ms(compose_started)

        audit_started = monotonic()
        try:
            audit = audit_local_response(canonical, realized)
        except Exception:
            audit_ms = self._ms(audit_started)
            meta = self._base_metadata(
                plan=plan,
                lane=lane,
                response_class=risk.response_class.value,
                escalation_reason="local_audit_failed",
                classification_ms=classification_ms,
                local_composer_ms=composer_ms,
                local_audit_ms=audit_ms,
                elapsed_ms=self._ms(started),
            )
            self._remember_last(meta)
            return LocalMindResult(False, metadata=meta)
        audit_ms = self._ms(audit_started)
        if not audit.accepted:
            meta = self._base_metadata(
                plan=plan,
                lane=lane,
                response_class=risk.response_class.value,
                escalation_reason="local_audit_rejected",
                classification_ms=classification_ms,
                local_composer_ms=composer_ms,
                local_audit_ms=audit_ms,
                elapsed_ms=self._ms(started),
            )
            self._remember_last(meta)
            return LocalMindResult(False, metadata=meta)

        response = str(realized.text).strip()
        self._phrase_history.append(response)
        del self._phrase_history[:-self._PHRASE_HISTORY_LIMIT]
        meta = self._base_metadata(
            plan=plan,
            lane=lane,
            response_class=risk.response_class.value,
            response_engine=LOCAL_ENGINE,
            escalation_reason=None,
            classification_ms=classification_ms,
            local_composer_ms=composer_ms,
            local_audit_ms=audit_ms,
            elapsed_ms=self._ms(started),
            local_only=True,
        )
        # Immediate caller may inspect the immutable display-safe contract.  It
        # is intentionally not retained by status()/diagnostics.
        meta["canonical_plan"] = canonical.to_dict()
        self._remember_last(meta)
        return LocalMindResult(
            True,
            response=response,
            confidence=float(plan.confidence),
            metadata=meta,
        )

    def observe_completed_turn(self, result: Any) -> None:
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
        self.refresh(rebuild_reservoir=False)
        if learned:
            self.reservoir_dirty = True

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "local_dialogue_enabled": self.local_dialogue_enabled,
            "hot": self.hot.status(),
            "reservoir": self.reservoir.status(),
            "retrieval": self.retrieval.status(),
            "last_local_decision": dict(self.last_result),
            "phrase_history_count": len(self._phrase_history),
            "reservoir_dirty": bool(self.reservoir_dirty),
            "local_model_catalog": OllamaModelLab.catalog(),
            "semantics": "rebuildable local projection; canonical Mary state remains authoritative",
        }
