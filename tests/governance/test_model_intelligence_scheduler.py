from __future__ import annotations

from mary.governance.limits import RuntimeLimits
from mary.governance.model_scheduler import ModelIntelligenceScheduler
from mary.governance.resource import ResourceGovernor


def test_cold_start_preserves_deterministic_policy_order():
    scheduler = ModelIntelligenceScheduler(mode="adaptive", minimum_samples=3)

    order = ["ollama", "groq", "openrouter"]

    assert scheduler.rank(order) == order


def test_ordered_mode_never_reorders_even_with_evidence():
    scheduler = ModelIntelligenceScheduler(mode="ordered", minimum_samples=1)
    for _ in range(5):
        scheduler.record_outcome("groq", "success", latency_ms=25, quality=1.0)
        scheduler.record_outcome("ollama", "error", latency_ms=20_000, quality=0.0)

    assert scheduler.rank(["ollama", "groq"]) == ["ollama", "groq"]


def test_adaptive_mode_can_promote_better_measured_provider():
    scheduler = ModelIntelligenceScheduler(mode="adaptive", minimum_samples=3)

    for _ in range(6):
        scheduler.record_outcome("ollama", "error", latency_ms=20_000, quality=0.1)
        scheduler.record_outcome("groq", "success", latency_ms=100, quality=0.95)

    assert scheduler.rank(["ollama", "groq"])[0] == "groq"


def test_scheduler_never_adds_provider_outside_eligible_set():
    scheduler = ModelIntelligenceScheduler(mode="adaptive", minimum_samples=1)
    for _ in range(4):
        scheduler.record_outcome("openai", "success", latency_ms=1, quality=1.0)

    ranked = scheduler.rank(["ollama", "groq"])

    assert set(ranked) == {"ollama", "groq"}
    assert "openai" not in ranked


def test_not_configured_does_not_pollute_learning_samples():
    scheduler = ModelIntelligenceScheduler(mode="adaptive", minimum_samples=1)

    scheduler.record_outcome("deepseek", "not_configured")

    evidence = scheduler.status()["providers"]["deepseek"]
    assert evidence["attempts"] == 0
    assert evidence["hard_failures"] == 0
    assert evidence["soft_failures"] == 0


def test_usage_learning_is_content_free_and_bounded_to_structural_metrics():
    scheduler = ModelIntelligenceScheduler(mode="adaptive", minimum_samples=1)
    scheduler.record_outcome("qwen_cloud", "success")
    scheduler.record_usage(
        {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "reasoning_tokens": 10,
            "cached_prompt_tokens": 25,
            "total_tokens": 150,
            "prompt": "must never be retained",
            "response": "must never be retained",
        }
    )

    snapshot = scheduler.status()
    provider = snapshot["providers"]["qwen_cloud"]

    assert provider["prompt_tokens"] == 100
    assert provider["completion_tokens"] == 50
    assert provider["reasoning_tokens"] == 10
    assert provider["cached_prompt_tokens"] == 25
    assert provider["total_tokens"] == 150
    assert "prompt" not in str(provider).lower()
    assert "response" not in str(provider).lower()
    assert snapshot["content_retention"] == "none"


def test_resource_governor_applies_scheduler_only_inside_router_order():
    scheduler = ModelIntelligenceScheduler(mode="adaptive", minimum_samples=1)
    governor = ResourceGovernor(
        RuntimeLimits(provider_attempts_per_generation=2),
        model_scheduler=scheduler,
    )

    for _ in range(4):
        governor.record_attempt("groq", "success", latency_ms=50, quality=1.0)
        governor.record_attempt("ollama", "error", latency_ms=10_000, quality=0.0)

    ranked = governor.provider_order(["ollama", "groq", "openrouter"])

    assert ranked[0] == "groq"
    assert len(ranked) == 2
    assert set(ranked).issubset({"ollama", "groq", "openrouter"})


def test_resource_status_exposes_scheduler_without_content():
    governor = ResourceGovernor()
    governor.record_generation_start(route="free_first", order=["groq", "ollama"])
    governor.record_attempt("groq", "success")
    governor.record_usage({"prompt_tokens": 10, "completion_tokens": 5})

    status = governor.status()

    assert status["model_scheduler"]["policy"] == "hard_constraints_then_adaptive_scoring"
    assert status["model_scheduler"]["providers"]["groq"]["successes"] == 1
    assert status["last_generation"]["scheduler_mode"] in {"adaptive", "ordered"}
