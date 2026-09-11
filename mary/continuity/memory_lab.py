"""Deterministic memory evaluation harness for MaryV2."""
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
    VERSION = 1

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
