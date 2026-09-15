"""Deterministic retrieval quality evidence for MaryV2 derived search lanes.

The evaluator never stores query text or retrieved memory content. Callers give
stable case IDs, expected record IDs, and ranked result IDs for lexical/vector/
hybrid candidates. Metrics decide whether a derived retrieval lane has enough
measured evidence to be preferred over the safe lexical baseline.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

VERSION = "13.43"


def _ids(values: Iterable[Any], *, limit: int = 100) -> tuple[str, ...]:
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()[:240]
        if text and text not in output:
            output.append(text)
        if len(output) >= limit:
            break
    return tuple(output)


@dataclass(frozen=True)
class RetrievalCase:
    case_id: str
    expected_record_ids: tuple[str, ...]
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        case_id = str(self.case_id or "").strip()[:120]
        if not case_id:
            raise ValueError("retrieval case_id is required")
        expected = _ids(self.expected_record_ids)
        if not expected:
            raise ValueError("retrieval case requires at least one expected record ID")
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "expected_record_ids", expected)
        object.__setattr__(self, "tags", _ids(self.tags, limit=16))


@dataclass(frozen=True)
class RetrievalCaseResult:
    case_id: str
    hit_at_k: bool
    reciprocal_rank: float
    precision_at_k: float
    recall_at_k: float
    expected_count: int
    returned_count: int
    first_relevant_rank: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalScorecard:
    lane: str
    cases: int
    k: int
    hit_rate_at_k: float
    mean_reciprocal_rank: float
    mean_precision_at_k: float
    mean_recall_at_k: float
    coverage: float
    case_results: tuple[RetrievalCaseResult, ...]
    version: str = VERSION
    authority: str = "operational_quality_evidence_only"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["case_results"] = [item.to_dict() for item in self.case_results]
        return payload


def evaluate_case(
    case: RetrievalCase,
    ranked_record_ids: Sequence[str] | None,
    *,
    k: int = 5,
) -> RetrievalCaseResult:
    bounded_k = max(1, min(50, int(k)))
    ranked = _ids(ranked_record_ids or (), limit=bounded_k)
    expected = set(case.expected_record_ids)
    relevant_ranks = [
        index + 1
        for index, record_id in enumerate(ranked[:bounded_k])
        if record_id in expected
    ]
    hits = len(relevant_ranks)
    first = relevant_ranks[0] if relevant_ranks else None
    return RetrievalCaseResult(
        case_id=case.case_id,
        hit_at_k=bool(hits),
        reciprocal_rank=(1.0 / first if first else 0.0),
        precision_at_k=(hits / max(1, len(ranked[:bounded_k]))),
        recall_at_k=(hits / max(1, len(expected))),
        expected_count=len(expected),
        returned_count=len(ranked[:bounded_k]),
        first_relevant_rank=first,
    )


def evaluate_lane(
    lane: str,
    cases: Sequence[RetrievalCase],
    ranked_results: Mapping[str, Sequence[str]],
    *,
    k: int = 5,
) -> RetrievalScorecard:
    name = str(lane or "").strip().lower()[:80]
    if not name:
        raise ValueError("retrieval lane name is required")
    bounded_k = max(1, min(50, int(k)))
    results = tuple(
        evaluate_case(case, ranked_results.get(case.case_id, ()), k=bounded_k)
        for case in cases
    )
    count = len(results)
    if not count:
        return RetrievalScorecard(
            lane=name,
            cases=0,
            k=bounded_k,
            hit_rate_at_k=0.0,
            mean_reciprocal_rank=0.0,
            mean_precision_at_k=0.0,
            mean_recall_at_k=0.0,
            coverage=0.0,
            case_results=(),
        )
    observed = sum(1 for item in results if item.returned_count > 0)
    return RetrievalScorecard(
        lane=name,
        cases=count,
        k=bounded_k,
        hit_rate_at_k=round(sum(item.hit_at_k for item in results) / count, 6),
        mean_reciprocal_rank=round(sum(item.reciprocal_rank for item in results) / count, 6),
        mean_precision_at_k=round(sum(item.precision_at_k for item in results) / count, 6),
        mean_recall_at_k=round(sum(item.recall_at_k for item in results) / count, 6),
        coverage=round(observed / count, 6),
        case_results=results,
    )


def promotion_decision(
    baseline: RetrievalScorecard,
    candidate: RetrievalScorecard,
    *,
    minimum_cases: int = 8,
    minimum_coverage: float = 0.90,
    minimum_hit_rate: float = 0.75,
    minimum_mrr: float = 0.60,
    allowed_hit_regression: float = 0.02,
    allowed_mrr_regression: float = 0.02,
) -> dict[str, Any]:
    """Return conservative measured promotion advice for a derived lane."""
    reasons: list[str] = []
    if candidate.cases < max(1, int(minimum_cases)):
        reasons.append("insufficient_cases")
    if candidate.coverage < max(0.0, min(1.0, float(minimum_coverage))):
        reasons.append("insufficient_coverage")
    if candidate.hit_rate_at_k < max(0.0, min(1.0, float(minimum_hit_rate))):
        reasons.append("hit_rate_below_floor")
    if candidate.mean_reciprocal_rank < max(0.0, min(1.0, float(minimum_mrr))):
        reasons.append("mrr_below_floor")
    if candidate.hit_rate_at_k + float(allowed_hit_regression) < baseline.hit_rate_at_k:
        reasons.append("hit_rate_regressed_vs_baseline")
    if candidate.mean_reciprocal_rank + float(allowed_mrr_regression) < baseline.mean_reciprocal_rank:
        reasons.append("mrr_regressed_vs_baseline")

    promoted = not reasons
    return {
        "version": VERSION,
        "baseline_lane": baseline.lane,
        "candidate_lane": candidate.lane,
        "promotion": "eligible" if promoted else "hold",
        "reasons": reasons,
        "metrics": {
            "baseline_hit_rate_at_k": baseline.hit_rate_at_k,
            "candidate_hit_rate_at_k": candidate.hit_rate_at_k,
            "baseline_mrr": baseline.mean_reciprocal_rank,
            "candidate_mrr": candidate.mean_reciprocal_rank,
            "candidate_coverage": candidate.coverage,
            "candidate_cases": candidate.cases,
        },
        "authority": (
            "advisory retrieval evidence only; this never mutates canonical memory "
            "or silently changes the active retrieval policy"
        ),
    }


def result_ids(rows: Sequence[Mapping[str, Any]] | None) -> tuple[str, ...]:
    """Extract only stable record IDs from a retrieval result for evaluation."""
    return _ids(
        row.get("record_id")
        for row in (rows or ())
        if isinstance(row, Mapping)
    )
