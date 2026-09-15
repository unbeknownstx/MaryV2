from mary.distributed.research_runtime_catalog import CATALOG, research_runtime_status


def test_research_runtime_catalog_contains_mined_frontier_candidates():
    ids = {item.runtime_id for item in CATALOG}
    assert {
        "coconut",
        "recurrent_reasoning",
        "latent_verifier",
        "vllm",
        "sglang",
        "executorch",
        "mlc_llm",
        "exo",
        "pipecat",
        "livekit_agents",
        "a2a_gateway",
        "areal",
        "verl",
        "opentelemetry",
    } <= ids


def test_research_runtimes_are_optional_and_non_authoritative(monkeypatch):
    for item in CATALOG:
        if item.readiness_probe.startswith("env:"):
            monkeypatch.delenv(item.readiness_probe.split(":", 1)[1], raising=False)
    status = research_runtime_status()
    semantics = status["semantics"]
    assert semantics["discovery_only"] is True
    assert semantics["core_startup_dependency"] is False
    assert semantics["identity_authority"] is False
    assert semantics["memory_authority"] is False
    assert semantics["tool_authority"] is False
    assert semantics["automatic_training"] is False
    assert semantics["automatic_self_modification"] is False
