from mary.llm.adaptive_provider_routing import ProviderEvidence, choose_provider, score_provider
from mary.llm.endpoint_policy import validate_endpoint, resolved_address_allowed
from mary.llm.provider_analytics import ProviderAnalytics
import pytest


def test_task_type_changes_advisory_preference_without_prompt_inspection():
    fast = ProviderEvidence("fast", reliability=.95, latency_ms=100, quota_remaining=.8, capability_fit=.55, samples=10)
    smart = ProviderEvidence("smart", reliability=.95, latency_ms=1500, quota_remaining=.8, capability_fit=1.0, samples=10)
    assert score_provider(fast, task_type="chat") > score_provider(smart, task_type="chat")
    assert score_provider(smart, task_type="code") > score_provider(fast, task_type="code")


def test_hysteresis_avoids_route_flapping_and_exploration_is_explicit():
    current = ProviderEvidence("a", reliability=.9, latency_ms=500, quota_remaining=.8, capability_fit=.8, samples=8)
    peer = ProviderEvidence("b", reliability=.91, latency_ms=480, quota_remaining=.8, capability_fit=.8, samples=8)
    assert choose_provider([current, peer], current_provider="a", switch_margin=.08) == "a"
    fresh = ProviderEvidence("fresh", samples=0)
    assert choose_provider([current, fresh], current_provider="a", explore=True) == "fresh"


def test_endpoint_policy_blocks_metadata_link_local_and_private_by_default():
    for url in ("http://169.254.169.254/latest/meta-data", "http://metadata.google.internal", "http://127.0.0.1:11434"):
        with pytest.raises(ValueError):
            validate_endpoint(url)
    assert validate_endpoint("http://127.0.0.1:11434", allow_local=True)
    assert not resolved_address_allowed("169.254.169.254", allow_local=True)
    assert resolved_address_allowed("127.0.0.1", allow_local=True)


def test_provider_analytics_retains_metrics_not_content():
    book = ProviderAnalytics(max_samples=8)
    for value in (100, 200, 300, 400):
        book.observe("groq", latency_ms=value, ttft_ms=value / 2, success=True)
    book.observe("groq", success=False)
    snapshot = book.snapshot()
    assert snapshot["content_retained"] is False
    assert snapshot["providers"]["groq"]["samples"] == 5
    assert snapshot["providers"]["groq"]["success_rate"] == .8
    text = repr(snapshot).lower()
    assert "prompt" not in text and "response" not in text and "api_key" not in text
