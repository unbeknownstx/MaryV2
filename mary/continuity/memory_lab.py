"""Deterministic memory and retrieval evaluation harness for MaryV2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


def _norm(value: str) -> str:
    return " ".join(str(value).strip().casefold().split())


@dataclass(frozen=True)
class MemoryCase:
    id: str
    category: str
    query: str
    expected_evidence: tuple[str, ...]
    forbidden_evidence: tuple[str, ...] = ()


class MemoryEvaluationSuite:
    VERSION = 2

    @staticmethod
    def default_cases() -> tuple[MemoryCase, ...]:
        return (
            MemoryCase("temporal_current", "temporal", "What is true now after an old fact changed?", ("current",), ("stale_as_current",)),
            MemoryCase("provenance_creator", "provenance", "Who actually supplied this fact?", ("source",), ("assistant_as_creator",)),
            MemoryCase("contradiction", "contradiction", "Resolve conflicting old/new evidence.", ("newer_verified",), ("merge_conflict_as_truth",)),
            MemoryCase("privacy_public", "privacy", "What may performer mode retrieve?", ("public_allowed",), ("creator_private",)),
            MemoryCase("long_range", "long_range", "Recall an old high-value event.", ("relevant_event",), ()),
            MemoryCase("false_memory", "false_memory", "Reject an event that never occurred.", ("not_found",), ("invented_event",)),
            MemoryCase("update", "update", "Honor a correction to a prior fact.", ("corrected_value",), ("superseded_value_as_current",)),
        )

    def evaluate(self, case: MemoryCase, evidence_labels: Iterable[str]) -> dict[str, Any]:
        labels = {_norm(label) for label in evidence_labels if str(label).strip()}
        expected = {_norm(item) for item in case.expected_evidence}
        forbidden = {_norm(item) for item in case.forbidden_evidence}
        missing = sorted(expected - labels)
        violations = sorted(forbidden & labels)
        passed = not missing and not violations
        return {
            "case_id": case.id,
            "category": case.category,
            "passed": passed,
            "missing": missing,
            "violations": violations,
        }

    def evaluate_retrieval(
        self,
        retriever: Any,
        *,
        query: str,
        expected_record_ids: Iterable[str],
        forbidden_record_ids: Iterable[str] = (),
        limit: int = 5,
        minimum_confidence: float = 0.0,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate Mary's actual derived retriever without becoming memory authority.

        ``retriever`` is intentionally injected. The canonical runtime passes
        ``mary.mind.retrieval``; tests can pass a bounded fake. This keeps Memory
        Lab from constructing a second reservoir/vector index or owning facts.
        """
        if retriever is None or not callable(getattr(retriever, "search", None)):
            raise TypeError("retriever must expose search()")
        bounded_limit = max(1, min(25, int(limit)))
        hits = list(
            retriever.search(
                str(query or ""),
                limit=bounded_limit,
                minimum_confidence=max(0.0, min(1.0, float(minimum_confidence))),
                context=dict(context or {}),
            )
            or []
        )
        ranked_ids = [str(getattr(hit, "record_id", "") or "") for hit in hits]
        ranked_ids = [value for value in ranked_ids if value]
        expected = [str(value) for value in expected_record_ids if str(value)]
        forbidden = {str(value) for value in forbidden_record_ids if str(value)}

        # Import lazily so the continuity package stays lightweight during Core
        # bootstrap and never creates its own mind/retrieval composition.
        from mary.mind.retrieval_evaluation import evaluate_ranking

        metrics = evaluate_ranking(ranked_ids, expected, k=bounded_limit)
        violations = [record_id for record_id in ranked_ids if record_id in forbidden]
        return {
            "query": str(query or "")[:500],
            "ranked_record_ids": ranked_ids,
            "expected_record_ids": expected,
            "forbidden_hits": violations,
            "metrics": metrics.to_dict(),
            "passed": metrics.recall >= 1.0 and not violations,
            "retrieval_authority": "derived_candidate_selection_only",
            "memory_promotion_performed": False,
        }

    def summarize(self, results: Iterable[dict[str, Any]]) -> dict[str, Any]:
        rows = list(results)
        passed = sum(1 for row in rows if row.get("passed"))
        total = len(rows)
        return {
            "version": self.VERSION,
            "passed": passed,
            "total": total,
            "score": 0.0 if total == 0 else round(passed / total, 4),
        }
