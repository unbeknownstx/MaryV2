from mary.llm.provider_pressure import ProviderPressureBook


def test_unknown_evidence_preserves_configured_order():
    book = ProviderPressureBook()
    assert book.order(["groq", "gemini", "ollama"]) == ["groq", "gemini", "ollama"]


def test_rate_limited_provider_is_demoted():
    book = ProviderPressureBook()
    book.failure("groq", rate_limited=True, cooldown_seconds=60)
    assert book.order(["groq", "gemini"]) == ["gemini", "groq"]


def test_quota_headroom_can_prefer_less_exhausted_lane():
    book = ProviderPressureBook()
    book.quota("groq", 0.05)
    book.quota("gemini", 0.9)
    assert book.order(["groq", "gemini"])[0] == "gemini"


def test_snapshot_is_content_free():
    book = ProviderPressureBook()
    book.success("groq", 123.0)
    snapshot = book.snapshot()
    assert snapshot["content_retained"] is False
    assert snapshot["authority"] == "operational_routing_evidence_only"
    assert set(snapshot["providers"]["groq"]) == {
        "successes", "failures", "rate_limits", "latency_ema_ms",
        "quota_remaining_fraction", "cooldown_remaining_seconds", "score",
        "content_retained",
    }
