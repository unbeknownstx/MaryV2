"""Deterministic evaluation helpers for Mary's derived retrieval layers."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import log2
from typing import Iterable, Sequence


@dataclass(frozen=True)
class RankingMetrics:
    hit_rate: float
    precision: float
    recall: float
    reciprocal_rank: float
    ndcg: float
    k: int

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def evaluate_ranking(
    ranked_ids: Sequence[str] | Iterable[str],
    expected_ids: Sequence[str] | Iterable[str],
    *,
    k: int = 5,
) -> RankingMetrics:
    limit = max(1, min(100, int(k)))
    ranked = [str(value) for value in list(ranked_ids)[:limit]]
    expected = {str(value) for value in expected_ids if str(value)}
    relevant = [1 if item in expected else 0 for item in ranked]
    hits = sum(relevant)
    precision = hits / limit
    recall = hits / len(expected) if expected else 1.0
    first = next((index for index, item in enumerate(ranked, start=1) if item in expected), None)
    rr = 1.0 / first if first else 0.0
    dcg = sum(rel / log2(index + 1) for index, rel in enumerate(relevant, start=1))
    ideal_hits = min(len(expected), limit)
    idcg = sum(1.0 / log2(index + 1) for index in range(1, ideal_hits + 1))
    ndcg = dcg / idcg if idcg else 1.0
    return RankingMetrics(
        hit_rate=1.0 if hits else 0.0,
        precision=precision,
        recall=recall,
        reciprocal_rank=rr,
        ndcg=ndcg,
        k=limit,
    )


def compare_rankings(
    base_ids: Sequence[str],
    reranked_ids: Sequence[str],
    expected_ids: Sequence[str],
    *,
    k: int = 5,
) -> dict[str, object]:
    base = evaluate_ranking(base_ids, expected_ids, k=k)
    reranked = evaluate_ranking(reranked_ids, expected_ids, k=k)
    return {
        "base": base.to_dict(),
        "reranked": reranked.to_dict(),
        "delta": {
            "reciprocal_rank": reranked.reciprocal_rank - base.reciprocal_rank,
            "ndcg": reranked.ndcg - base.ndcg,
            "recall": reranked.recall - base.recall,
        },
        "improved": (
            reranked.ndcg > base.ndcg
            or reranked.reciprocal_rank > base.reciprocal_rank
            or reranked.recall > base.recall
        ),
        "semantics": "evaluation measures derived retrieval quality; it never changes canonical memory truth",
    }
