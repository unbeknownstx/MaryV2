"""Safe continuous-development loop for MaryV2 13.0.

The growth engine closes the gap between *remembering conversations* and
*developing because of experience*.  It runs after a completed turn and uses
only observable/canonical signals.  Model-authored dialogue is context, never
evidence that Mary permanently changed.
"""
from __future__ import annotations

from datetime import datetime
import re
from pathlib import Path
from typing import Any

from .experience import ExperienceJournal
from .preference_evidence import (
    extract_preference_evidence_items,
    stable_candidate_reference,
    stable_candidate_id,
    stable_developed_preference_reference,
    stable_developed_preference_id,
    stable_evidence_id,
)
from mary.runtime.turn_observability import (
    causal_operation_id,
    current_turn_trace,
    record_turn_stage,
)


_ACHIEVEMENT_RE = re.compile(
    r"\b(?:it works|it'?s working|we got it|we did it|finally works|passed all|all tests pass|fixed it|got .* working|made .* work)\b",
    re.IGNORECASE,
)


class GrowthEngine:
    VERSION = "13.0"

    def __init__(self, mary: Any) -> None:
        self.mary = mary
        self.journal = ExperienceJournal()
        self.auto_consolidate = True
        self.auto_develop_preferences = True
        self.preference_min_observations = 5
        self.preference_min_confidence = 0.85
        self.preference_min_consistency = 0.90
        self.preference_min_magnitude = 0.60
        self.semantic_promotions = 0
        self.preference_promotions = 0
        self.milestones_created = 0
        self.last_growth: dict[str, Any] = {}
        self._milestone_keys: set[str] = set()

    def configure(self, root: str | Path, *, auto_save: bool = True, load: bool = True) -> bool:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        ok = self.journal.configure(root / "experience_journal.json", auto_save=auto_save, load=load)
        # Rebuild dedupe keys from durable relationship milestones rather than
        # owning a second milestone database.
        try:
            for item in self.mary.relationship_milestones.get_milestones():
                meta = dict(item.get("metadata", {}) or {})
                key = str(meta.get("growth_key") or "").strip()
                if key:
                    self._milestone_keys.add(key)
        except Exception:
            pass
        return ok

    def observe_turn(
        self,
        *,
        input_text: str,
        result: Any,
        creator_authored: bool = True,
        input_authority: str = "creator",
        turn_id: str = "",
    ) -> dict[str, Any]:
        metadata = dict(getattr(result, "metadata", {}) or {})
        reasoning = dict(getattr(getattr(result, "reasoning", None), "metadata", {}) or {})
        emotion = dict(metadata.get("emotion_appraisal", {}) or {})
        relationship_learning = dict(metadata.get("natural_relationship_learning", {}) or {})
        shared_work = dict(metadata.get("shared_work_learning", {}) or {})
        engagement = dict(getattr(self.mary, "engagement", None).last_plan or {}) if getattr(self.mary, "engagement", None) else {}

        importance = self._importance(
            input_text=input_text,
            relationship_learning=relationship_learning,
            shared_work=shared_work,
            emotion=emotion,
            engagement=engagement,
            system_action=str(metadata.get("system_action") or ""),
        )

        experience = self.journal.add({
            "user_text": str(input_text),
            "mary_text": str(getattr(result, "final_response", "") or ""),
            "intent": getattr(getattr(getattr(result, "intent", None), "intent_type", None), "value", "unknown"),
            "importance": importance,
            "provider": reasoning.get("provider"),
            "model": reasoning.get("model"),
            "engagement_mode": engagement.get("effective_mode", "adaptive"),
            "emotion": emotion.get("emotion"),
            "emotion_intensity": emotion.get("intensity"),
            "relationship_learning": bool(relationship_learning.get("learned") or relationship_learning.get("already_known")),
            "shared_work": bool(shared_work.get("recorded")),
            "provenance": {
                "creator_input": "user_role",
                "mary_output": "assistant_role_context_only",
                "durable_self_evidence": False,
            },
        })

        preference_evidence = self._observe_creator_preference(
            input_text=input_text,
            experience_id=str(experience.get("id") or ""),
            creator_authored=creator_authored,
            input_authority=input_authority,
            turn_id=turn_id,
            generation_succeeded=not bool(reasoning.get("llm_unavailable", False)),
        )

        promoted_semantic = 0
        if self.auto_consolidate and importance >= 0.55:
            try:
                promoted_semantic = int(self.mary.memory.consolidate())
                self.semantic_promotions += promoted_semantic
            except Exception:
                promoted_semantic = 0

        promoted_preferences: list[str] = []
        if self.auto_develop_preferences:
            promoted_preferences = self._promote_strict_preference_candidates()
            self.preference_promotions += len(promoted_preferences)
        if preference_evidence.get("detected"):
            items = list(
                preference_evidence.get("evidence_items")
                or [preference_evidence]
            )
            for item in items:
                candidate_name = item.get("_candidate_name")
                if candidate_name in promoted_preferences:
                    item["disposition"] = "promoted"
                    item["candidate_state"] = "promoted"
                    item["promotion_result"] = "promoted"
                    item["developed_preference_id"] = item.get(
                        "_developed_preference_id"
                    )
                else:
                    item["promotion_result"] = item.get(
                        "promotion_result",
                        "deferred",
                    )
                item.pop("_candidate_name", None)
                item.pop("_developed_preference_id", None)
            if "evidence_items" in preference_evidence:
                preference_evidence["evidence_items"] = items
                preference_evidence.update(
                    {
                        key: value
                        for key, value in items[0].items()
                        if key != "evidence_items"
                    }
                )

        milestones: list[dict[str, Any]] = []
        if _ACHIEVEMENT_RE.search(str(input_text)) and (shared_work.get("recorded") or importance >= 0.75):
            milestone = self._relationship_milestone(
                key=f"achievement:{self._slug(input_text)[:80]}",
                title="A shared breakthrough",
                description=self._achievement_description(input_text),
                category="shared_achievement",
                importance=0.85,
            )
            if milestone:
                milestones.append(milestone)

        for name in promoted_preferences:
            milestone = self._relationship_milestone(
                key=f"mary_developed_preference:{name}",
                title="Mary developed a preference",
                description=f"Repeated grounded experience was strong and consistent enough for Mary to develop a durable preference around {name}.",
                category="mary_development",
                importance=0.80,
            )
            if milestone:
                milestones.append(milestone)

        self.milestones_created += len(milestones)
        self.last_growth = {
            "experience_id": experience.get("id"),
            "importance": importance,
            "semantic_promotions": promoted_semantic,
            "preference_promotions": len(promoted_preferences),
            "preference_evidence": preference_evidence,
            "milestones": [m.get("id") for m in milestones],
            "timestamp": datetime.now().isoformat(),
        }
        trace = current_turn_trace()
        trace_turn_id = str(
            turn_id or getattr(trace, "turn_id", "") or ""
        )
        record_turn_stage(
            "experience_growth",
            status="success",
            elapsed_ms=0.0,
            outcome="experience_recorded",
            result_ids={"experience_id": experience.get("id")},
        )
        evidence_items = list(
            preference_evidence.get("evidence_items")
            or ([preference_evidence] if preference_evidence else [])
        )
        evidence_ids = [
            item.get("evidence_id")
            for item in evidence_items
            if isinstance(item, dict) and item.get("evidence_id")
        ]
        candidate_ids = [
            item.get("candidate_id")
            for item in evidence_items
            if isinstance(item, dict) and item.get("candidate_id")
        ]
        developed_ids = [
            item.get("developed_preference_id")
            for item in evidence_items
            if isinstance(item, dict) and item.get("developed_preference_id")
        ]
        record_turn_stage(
            "preference_evidence",
            status=(
                "success"
                if preference_evidence.get("detected")
                else "skipped"
            ),
            elapsed_ms=0.0,
            outcome=str(
                preference_evidence.get("disposition")
                or "not_applicable"
            ),
            result_ids={
                "preference_evidence_id": evidence_ids,
                "preference_candidate_id": candidate_ids,
                "developed_preference_id": developed_ids,
            },
        )
        record_turn_stage(
            "memory_consolidation",
            status="success" if promoted_semantic else "skipped",
            elapsed_ms=0.0,
            outcome="promoted" if promoted_semantic else "deferred_or_none",
            result_ids={
                "memory_operation_id": causal_operation_id(
                    trace_turn_id,
                    "memory",
                    "consolidation",
                ),
            },
        )
        return dict(self.last_growth)

    def _observe_creator_preference(
        self,
        *,
        input_text: str,
        experience_id: str,
        creator_authored: bool,
        input_authority: str,
        turn_id: str,
        generation_succeeded: bool,
    ) -> dict[str, Any]:
        """Record one allow-listed creator signal without exposing its text."""

        authority = str(input_authority or "").strip().lower()
        if not creator_authored or authority != "creator":
            return {
                "detected": False,
                "disposition": "blocked",
                "block_reason": "non_creator_authority",
            }

        evidence_items = extract_preference_evidence_items(input_text)
        if not evidence_items:
            return {
                "detected": False,
                "disposition": "not_applicable",
            }
        if not generation_succeeded:
            first = evidence_items[0]
            return {
                "detected": False,
                "evidence_class": first.evidence_class,
                "signal": first.signal,
                "disposition": "blocked",
                "block_reason": "failed_turn",
            }

        diagnostics: list[dict[str, Any]] = []
        for evidence in evidence_items:
            evidence_id = stable_evidence_id(
                turn_id=turn_id,
                fallback_id=experience_id,
                evidence=evidence,
            )
            existing = self.mary.preference_promotion.get_candidate(evidence.name)
            duplicate = self.mary.preference_promotion.has_evidence_id(
                evidence.name,
                evidence_id,
            )

            evaluation = self.mary.observe_preference_experience(
                evidence.name,
                category=evidence.category,
                strength=evidence.strength,
                polarity=evidence.polarity,
                confidence=evidence.confidence,
                source=f"creator_{evidence.evidence_class}",
                reason=f"{evidence.evidence_class}:{evidence.signal}",
                evidence_id=evidence_id,
            )
            diagnostics.append(
                {
                    "detected": True,
                    "evidence_class": evidence.evidence_class,
                    "signal": evidence.signal,
                    "evidence_id": evidence_id,
                    "candidate_id": stable_candidate_id(evidence),
                    "candidate_created": existing is None and not duplicate,
                    "observation_count": int(
                        evaluation.get("observation_count", 0) or 0
                    ),
                    "candidate_state": (
                        "eligible"
                        if evaluation.get("eligible")
                        else "candidate"
                    ),
                    "gate_outcome": (
                        "duplicate"
                        if duplicate
                        else "base_eligible"
                        if evaluation.get("eligible")
                        else "deferred"
                    ),
                    "disposition": "duplicate" if duplicate else "deferred",
                    "promotion_result": "duplicate" if duplicate else "deferred",
                    "developed_preference_id": None,
                    "_candidate_name": evidence.name,
                    "_developed_preference_id": (
                        stable_developed_preference_id(evidence)
                    ),
                }
            )

        result = dict(diagnostics[0])
        if len(diagnostics) > 1:
            result["evidence_items"] = diagnostics
        return result

    def _promote_strict_preference_candidates(self) -> list[str]:
        promoted: list[str] = []
        system = self.mary.preference_promotion
        for candidate in list(system.get_candidates()):
            name = str(candidate.get("name") or "").strip()
            if not name:
                continue
            evaluation = system.evaluate(name)
            if not evaluation.get("eligible"):
                continue
            if int(evaluation.get("observation_count", 0) or 0) < self.preference_min_observations:
                continue
            if float(evaluation.get("mean_confidence", 0.0) or 0.0) < self.preference_min_confidence:
                continue
            if float(evaluation.get("consistency", 0.0) or 0.0) < self.preference_min_consistency:
                continue
            if float(evaluation.get("mean_magnitude", 0.0) or 0.0) < self.preference_min_magnitude:
                continue
            observations = list(candidate.get("observations", []) or [])
            # Every observation must already have passed the promotion system's
            # model-source block, but keep a second explicit guard at the
            # autonomous promotion boundary.
            bad = any(str(item.get("source") or "").strip().lower() in system.BLOCKED_SOURCES for item in observations if isinstance(item, dict))
            if bad:
                continue
            result = self.mary.promote_preference_candidate(name)
            if result.get("promoted"):
                promoted.append(name)
        return promoted

    def _relationship_milestone(self, *, key: str, title: str, description: str, category: str, importance: float) -> dict[str, Any] | None:
        if key in self._milestone_keys:
            return None
        try:
            milestone = self.mary.relationship_milestones.add_milestone(
                title=title,
                description=description,
                category=category,
                importance=importance,
                metadata={"growth_key": key, "source": "growth_engine_13"},
            )
            self._milestone_keys.add(key)
            self.mary.relationship.save()
            return milestone
        except Exception:
            return None

    @staticmethod
    def _importance(*, input_text: str, relationship_learning: dict[str, Any], shared_work: dict[str, Any], emotion: dict[str, Any], engagement: dict[str, Any], system_action: str) -> float:
        value = 0.30
        if relationship_learning.get("learned"):
            value = max(value, 0.78)
        if shared_work.get("recorded"):
            value = max(value, 0.82)
        if system_action in {"creator_directive", "relationship_share", "memory_store"}:
            value = max(value, 0.82)
        if str(engagement.get("effective_mode")) == "engaged":
            value = max(value, 0.62)
        if str(engagement.get("effective_mode")) == "deep":
            value = max(value, 0.72)
        try:
            relevance = float(emotion.get("relationship_relevance", 0.0) or 0.0)
            intensity = float(emotion.get("intensity", 0.0) or 0.0)
            if relevance >= 0.75 and intensity >= 0.45:
                value = max(value, 0.70)
        except (TypeError, ValueError):
            pass
        if len(str(input_text).split()) >= 35:
            value = max(value, 0.58)
        return round(min(1.0, value), 3)

    @staticmethod
    def _slug(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")

    @staticmethod
    def _achievement_description(text: str) -> str:
        value = " ".join(str(text).split()).strip()
        if len(value) > 180:
            value = value[:179].rstrip() + "…"
        return f"A creator-reported shared-work breakthrough was reached: {value}"

    def status(self) -> dict[str, Any]:
        candidates = []
        try:
            for item in self.mary.preference_promotion.get_candidates():
                name = str(item.get("name") or "")
                category = str(item.get("category") or "general")
                evaluation = self.mary.preference_promotion.evaluate(name)
                candidates.append({
                    "name": name,
                    "category": category,
                    "candidate_id": stable_candidate_reference(
                        name=name,
                        category=category,
                    ),
                    "state": (
                        "eligible"
                        if evaluation.get("eligible")
                        else "candidate"
                    ),
                    "observations": evaluation.get("observation_count", 0),
                    "eligible": bool(evaluation.get("eligible")),
                    "confidence": round(float(evaluation.get("mean_confidence", 0.0) or 0.0), 3),
                    "consistency": round(float(evaluation.get("consistency", 0.0) or 0.0), 3),
                })
        except Exception:
            candidates = []
        try:
            recent_milestones = self.mary.relationship_milestones.get_recent(limit=6)
        except Exception:
            recent_milestones = []

        try:
            memory_counts = dict(self.mary.memory.status().get("counts", {}) or {})
        except Exception:
            memory_counts = {}
        try:
            developed_self = dict(self.mary.developed_self_state.status() or {})
        except Exception:
            developed_self = {}
        try:
            relationship_milestone_count = len(self.mary.relationship_milestones.get_milestones())
        except Exception:
            relationship_milestone_count = 0
        developed_preferences = []
        try:
            for item in self.mary.preferences.get_preferences():
                if not isinstance(item, dict):
                    continue
                category = str(item.get("category") or "").strip().lower()
                source = str(item.get("source") or "").strip().lower()
                if (
                    category != "creator_interaction"
                    or source != "experience_promotion"
                ):
                    continue
                developed_preferences.append(
                    {
                        "developed_preference_id": (
                            stable_developed_preference_reference(
                                name=str(item.get("name") or ""),
                                category=category,
                            )
                        ),
                        "state": "active",
                    }
                )
        except Exception:
            developed_preferences = []

        process_counters = {
            "semantic_promotions": self.semantic_promotions,
            "preference_promotions": self.preference_promotions,
            "milestones_created": self.milestones_created,
        }
        durable_state = {
            "semantic_memories": int(memory_counts.get("semantic", 0) or 0),
            "developed_preferences": int(developed_self.get("preference_overrides", 0) or 0),
            "developed_personality_traits": int(developed_self.get("personality_overrides", 0) or 0),
            "relationship_milestones": int(relationship_milestone_count),
        }

        return {
            "version": self.VERSION,
            "journal": self.journal.status(),
            # Compatibility fields retained for older clients. These counters
            # describe activity since the current Mary Core process started;
            # canonical durable totals are projected separately below.
            "semantic_promotions": self.semantic_promotions,
            "preference_promotions": self.preference_promotions,
            "milestones_created": self.milestones_created,
            "counter_scope": "current_core_process",
            "process_counters": process_counters,
            "durable_state": durable_state,
            "last_growth": dict(self.last_growth),
            "preference_candidates": candidates[:12],
            "developed_preferences": developed_preferences[:12],
            "recent_milestones": [dict(x) for x in recent_milestones],
            "policy": {
                "automatic_safe_semantic_consolidation": self.auto_consolidate,
                "automatic_strict_preference_development": self.auto_develop_preferences,
                "model_dialogue_counts_as_self_evidence": False,
                "core_values_auto_rewritten": False,
                "canonical_personality_auto_rewritten": False,
                "process_counters_are_durable_totals": False,
            },
        }
