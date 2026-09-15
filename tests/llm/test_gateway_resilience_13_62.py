from mary.llm.failover_budget import FailoverBudget
from mary.llm.provider_health import ProviderHealthBook
from mary.llm.quota_guard import ProviderQuotaBook, QuotaLimit


def test_quota_headroom_preserves_provider_before_hard_limit():
    book = ProviderQuotaBook()
    book.configure("free", QuotaLimit(requests_per_minute=10, reserve_fraction=0.2))
    for second in range(7):
        book.record("free", now=float(second))
    assert book.allows("free", now=7.0)
    book.record("free", now=7.0)
    assert not book.allows("free", now=8.0)


def test_shared_token_budget_is_content_free_and_fail_open_when_unconfigured():
    book = ProviderQuotaBook()
    assert book.allows("unknown", estimated_tokens=999999)
    book.configure("metered", QuotaLimit(tokens_per_day=1000, reserve_fraction=0.1))
    book.record("metered", tokens=800, now=1.0)
    assert book.allows("metered", estimated_tokens=100, now=2.0)
    assert not book.allows("metered", estimated_tokens=101, now=2.0)
    assert book.snapshot()["content_retained"] is False


def test_failover_budget_stops_unhealthy_chain():
    budget = FailoverBudget(max_attempts=6, max_consecutive_failures=3)
    for _ in range(3):
        budget.begin_attempt()
        budget.failure()
    assert not budget.may_attempt()
    assert budget.snapshot()["exhausted"] is True


def test_success_resets_consecutive_failure_counter():
    budget = FailoverBudget(max_attempts=4, max_consecutive_failures=2)
    budget.begin_attempt(); budget.failure()
    budget.begin_attempt(); budget.success()
    assert budget.consecutive_failures == 0
    assert budget.may_attempt()


def test_provider_health_unknown_is_fail_open_but_known_bad_is_skipped():
    health = ProviderHealthBook(ttl_seconds=30)
    assert health.usable("new-provider")
    health.update("bad", "invalid")
    health.update("good", "healthy")
    assert not health.usable("bad")
    assert health.usable("good")
    assert health.ready(["bad", "good"])
    assert health.snapshot()["content_retained"] is False
