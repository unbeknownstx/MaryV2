"""Local MaryBench experiment artifacts and comparison helpers.

Raw held-out prompts/responses belong to the experiment machine. These helpers
summarize them for review but never turn deterministic anti-pattern checks into
semantic Mary-quality scores and never write to the canonical model ledger.
"""
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Iterable


REQUIRED_MODEL_SCORE_DIMENSIONS = (
    "mary_likeness",
    "naturalism",
    "context_adherence",
    "identity_boundary",
    "fiction_boundary",
    "epistemic_honesty",
    "relationship_continuity",
    "character_restraint",
)


def summarize_marybench_results(
    results: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    rows = [dict(item) for item in results]
    categories: dict[str, dict[str, Any]] = {}
    latencies: list[float] = []
    failures = 0
    checks = 0
    for row in rows:
        category = str(row.get("category") or "character")[:80]
        passed = bool(row.get("passed"))
        bucket = categories.setdefault(
            category,
            {"cases": 0, "passed": 0, "failed": 0, "checks": 0},
        )
        bucket["cases"] += 1
        bucket["passed"] += int(passed)
        bucket["failed"] += int(not passed)
        row_checks = max(0, int(row.get("checks") or 0))
        bucket["checks"] += row_checks
        checks += row_checks
        failures += int(not passed)
        try:
            latency = float(row.get("latency_ms"))
        except (TypeError, ValueError):
            latency = -1.0
        if latency >= 0:
            latencies.append(latency)

    for bucket in categories.values():
        count = int(bucket["cases"])
        bucket["pass_rate"] = round(
            float(bucket["passed"]) / count if count else 0.0,
            4,
        )

    count = len(rows)
    return {
        "cases": count,
        "passed": count - failures,
        "failed": failures,
        "deterministic_pass_rate": round(
            float(count - failures) / count if count else 0.0,
            4,
        ),
        "checks": checks,
        "mean_latency_ms": (
            None if not latencies else round(mean(latencies), 2)
        ),
        "categories": categories,
        "failure_reasons": dict(Counter(
            failure
            for row in rows
            for failure in list(row.get("failures") or [])
        )),
        "semantic_score_claimed": False,
    }


def comparison_scorecard(
    base_report: dict[str, Any],
    adapter_report: dict[str, Any],
) -> dict[str, Any]:
    base = dict(base_report or {})
    adapter = dict(adapter_report or {})
    base_fingerprint = str(base.get("benchmark_fingerprint") or "")
    adapter_fingerprint = str(adapter.get("benchmark_fingerprint") or "")
    if not base_fingerprint or base_fingerprint != adapter_fingerprint:
        raise ValueError("MaryBench fingerprints must match for A/B comparison")
    if int(base.get("case_count") or 0) != int(adapter.get("case_count") or 0):
        raise ValueError("MaryBench case counts must match for A/B comparison")

    base_summary = dict(base.get("summary") or {})
    adapter_summary = dict(adapter.get("summary") or {})
    base_categories = dict(base_summary.get("categories") or {})
    adapter_categories = dict(adapter_summary.get("categories") or {})
    category_delta: dict[str, float] = {}
    for category in sorted(set(base_categories) | set(adapter_categories)):
        before = float(dict(base_categories.get(category) or {}).get("pass_rate") or 0.0)
        after = float(dict(adapter_categories.get(category) or {}).get("pass_rate") or 0.0)
        category_delta[category] = round(after - before, 4)

    base_rate = float(base_summary.get("deterministic_pass_rate") or 0.0)
    adapter_rate = float(adapter_summary.get("deterministic_pass_rate") or 0.0)
    base_latency = base_summary.get("mean_latency_ms")
    adapter_latency = adapter_summary.get("mean_latency_ms")
    latency_delta = None
    if base_latency is not None and adapter_latency is not None:
        latency_delta = round(float(adapter_latency) - float(base_latency), 2)

    return {
        "version": "marybench-ab-scorecard-v1",
        "benchmark_fingerprint": base_fingerprint,
        "benchmark_case_count": int(base.get("case_count") or 0),
        "base": {
            "variant": base.get("variant"),
            "model": base.get("model"),
            "artifact_fingerprint": base.get("artifact_fingerprint", ""),
            "deterministic_pass_rate": base_rate,
            "mean_latency_ms": base_latency,
        },
        "adapter": {
            "variant": adapter.get("variant"),
            "model": adapter.get("model"),
            "artifact_fingerprint": adapter.get("artifact_fingerprint", ""),
            "dataset_fingerprint": adapter.get("dataset_fingerprint", ""),
            "deterministic_pass_rate": adapter_rate,
            "mean_latency_ms": adapter_latency,
        },
        "delta": {
            "deterministic_pass_rate": round(adapter_rate - base_rate, 4),
            "mean_latency_ms": latency_delta,
            "categories": category_delta,
        },
        "scores": {
            key: None for key in REQUIRED_MODEL_SCORE_DIMENSIONS
        },
        "review": {
            "required_semantic_dimensions": list(REQUIRED_MODEL_SCORE_DIMENSIONS),
            "deterministic_checks_are_not_semantic_scores": True,
            "creator_or_explicit_judge_review_required": True,
            "promotion_performed": False,
        },
        "boundaries": {
            "raw_responses_included": False,
            "prompt_text_included": False,
            "automatic_score_inference": False,
            "automatic_benchmark_registration": False,
            "automatic_promotion": False,
        },
    }
