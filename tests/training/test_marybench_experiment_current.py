from __future__ import annotations

import pytest

from mary.training.marybench_experiment import (
    REQUIRED_MODEL_SCORE_DIMENSIONS,
    comparison_scorecard,
    summarize_marybench_results,
)


def _report(variant: str, pass_rate_rows, *, fingerprint="bench-exact"):
    results = [
        {
            "case_id": f"case-{index}",
            "category": category,
            "passed": passed,
            "failures": [] if passed else ["forbidden pattern matched"],
            "checks": 5,
            "latency_ms": latency,
        }
        for index, (category, passed, latency) in enumerate(pass_rate_rows, start=1)
    ]
    return {
        "variant": variant,
        "model": "mlx-community/Qwen3-1.7B-4bit",
        "artifact_fingerprint": "adapter-exact" if variant == "adapter" else "",
        "dataset_fingerprint": "dataset-exact",
        "benchmark_fingerprint": fingerprint,
        "case_count": len(results),
        "summary": summarize_marybench_results(results),
    }


def test_marybench_summary_keeps_guardrail_results_separate_from_semantic_scores():
    summary = summarize_marybench_results([
        {
            "category": "identity_boundary",
            "passed": True,
            "checks": 4,
            "latency_ms": 100,
            "failures": [],
        },
        {
            "category": "style_voice",
            "passed": False,
            "checks": 5,
            "latency_ms": 200,
            "failures": ["forbidden phrase present"],
        },
    ])

    assert summary["cases"] == 2
    assert summary["deterministic_pass_rate"] == 0.5
    assert summary["mean_latency_ms"] == 150.0
    assert summary["semantic_score_claimed"] is False
    assert summary["categories"]["identity_boundary"]["pass_rate"] == 1.0
    assert summary["categories"]["style_voice"]["pass_rate"] == 0.0


def test_base_adapter_scorecard_requires_explicit_semantic_review():
    base = _report(
        "base",
        [
            ("identity_boundary", False, 120),
            ("style_voice", True, 100),
        ],
    )
    adapter = _report(
        "adapter",
        [
            ("identity_boundary", True, 150),
            ("style_voice", True, 130),
        ],
    )

    scorecard = comparison_scorecard(base, adapter)

    assert scorecard["delta"]["deterministic_pass_rate"] == 0.5
    assert scorecard["delta"]["mean_latency_ms"] == 30.0
    assert set(scorecard["scores"]) == set(REQUIRED_MODEL_SCORE_DIMENSIONS)
    assert all(value is None for value in scorecard["scores"].values())
    assert scorecard["review"]["creator_or_explicit_judge_review_required"] is True
    assert scorecard["boundaries"]["automatic_score_inference"] is False
    assert scorecard["boundaries"]["automatic_benchmark_registration"] is False


def test_base_adapter_scorecard_refuses_mismatched_held_out_runs():
    base = _report("base", [("character_reaction", True, 100)], fingerprint="a")
    adapter = _report("adapter", [("character_reaction", True, 100)], fingerprint="b")

    with pytest.raises(ValueError, match="fingerprints must match"):
        comparison_scorecard(base, adapter)
