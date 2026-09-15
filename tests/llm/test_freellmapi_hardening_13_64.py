from datetime import datetime, timedelta, timezone

import pytest

from mary.governance.resource import ResourceGovernor
from mary.llm.catalog_trust import CatalogEnvelope, CatalogTrustPolicy
from mary.llm.embedding_router import EmbeddingRoute, EmbeddingRouter
from mary.llm.provider_identity import RouteIdentity, enforce_identity
from mary.llm.quota_guard import QuotaLimit
from mary.llm.quota_hysteresis import QuotaHysteresis
from mary.llm.readiness import ReadinessAggregator, ReadinessSignal
from mary.llm.transport_normalization import ImagePart, ProviderCapabilities, RequestCapabilities, prefilter


def test_signed_catalog_requires_pinned_fresh_monotonic_signature():
    now = datetime.now(timezone.utc)
    policy = CatalogTrustPolicy({"catalog-key"})
    env = CatalogEnvelope(b"{}", b"sig", "catalog-key", now - timedelta(seconds=1), now + timedelta(minutes=5), 7)
    decision = policy.verify(env, lambda key, payload, signature: True, now=now)
    assert decision.accepted and decision.authority == "routing_metadata_only"
    assert not policy.verify(env, lambda *_: True, now=now).accepted


def test_readiness_unknown_is_not_invented_failure():
    book = ReadinessAggregator()
    assert book.status("groq") == "unknown"
    book.observe("groq", ReadinessSignal("probe", True, 10.0, 100.0))
    assert book.status("groq", now=11.0) == "ready"


def test_embedding_failover_never_crosses_space():
    router = EmbeddingRouter([
        EmbeddingRoute("a", "bge", 3, "space-1"),
        EmbeddingRoute("b", "bge", 3, "space-1"),
        EmbeddingRoute("c", "other", 3, "space-2"),
    ])
    assert [r.provider for r in router.candidates(family="bge", dimensions=3, space_identity="space-1")] == ["a", "b"]


def test_provider_substitution_is_detected_and_rejected_by_default():
    identity = RouteIdentity("gateway", "model-a", "gateway", "model-b")
    assert identity.substitution() == "substituted"
    with pytest.raises(RuntimeError):
        enforce_identity(identity)


def test_quota_hysteresis_avoids_threshold_flapping():
    state = QuotaHysteresis(0.15, 0.25)
    assert state.update(0.14) is True
    assert state.update(0.20) is True
    assert state.update(0.26) is False


def test_image_normalization_and_capability_prefilter():
    part = ImagePart("data:image/png;base64,AAAA", "image/png")
    assert part.openai_part()["type"] == "image_url"
    evidence = {"vision": ProviderCapabilities(vision=True), "text": ProviderCapabilities()}
    assert prefilter(["text", "vision"], evidence, RequestCapabilities(vision=True)) == ["vision"]


def test_resource_governor_filters_only_after_router_supplied_eligible_set():
    governor = ResourceGovernor()
    governor.provider_health.update("bad", "unreachable")
    governor.configure_provider_quota("scarce", QuotaLimit(requests_per_day=1, reserve_fraction=0.0))
    governor.provider_quota.record("scarce")
    result = governor.provider_order(["bad", "scarce", "good"])
    assert result == ["good"]
    # The governor cannot introduce a provider that was not in the eligible list.
    assert set(result) <= {"bad", "scarce", "good"}
