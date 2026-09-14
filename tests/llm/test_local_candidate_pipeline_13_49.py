from mary.llm.local_candidate_pipeline import (
    candidate_catalog,
    candidates_from_discovery,
    measurement_plan,
)
from mary.llm.local_engine_discovery import DetectedLocalEngine


def _engine(**changes):
    values = {
        "engine_id": "lmstudio",
        "display_name": "LM Studio candidate",
        "base_url": "http://127.0.0.1:1234/v1",
        "protocol": "openai_compatible",
        "models": ("qwen",),
        "aliases": ("LM Studio",),
        "identity_strength": "port_hint",
        "reachable": True,
    }
    values.update(changes)
    return DetectedLocalEngine(**values)


def test_discovered_model_becomes_qualified_unmeasured_candidate():
    [candidate] = candidates_from_discovery([_engine()], node_id="desktop")
    assert candidate.qualified_id.startswith("desktop/lmstudio/qwen")
    assert candidate.model_fingerprint
    assert candidate.promotion_state == "measurement_required"
    assert candidate.auto_promoted is False


def test_shared_protocol_identity_remains_ambiguous_in_measurement_plan():
    engine = _engine(
        engine_id="openai_compat_8080",
        display_name="OpenAI-compatible endpoint :8080",
        base_url="http://127.0.0.1:8080/v1",
        identity_strength="protocol_only",
        aliases=("llama.cpp", "LocalAI", "TGI"),
    )
    [candidate] = candidates_from_discovery([engine], node_id="pc")
    plan = measurement_plan(candidate)
    assert plan["identity_action"] == "preserve_ambiguous_engine_identity"
    assert plan["execution_authorized"] is False
    assert plan["auto_promoted"] is False


def test_discovery_catalog_requires_capability_quality_and_resource_evidence():
    catalog = candidate_catalog([_engine(models=("qwen", "gemma"))], node_id="pc")
    assert catalog["count"] == 2
    assert catalog["auto_promoted"] == 0
    assert catalog["execution_authorized"] is False
    for plan in catalog["measurement_plans"]:
        assert "structured_json" in plan["capability_probes"]
        assert "conversation" in plan["benchmark_lanes"]
        assert plan["resource_measurement"] == "required"


def test_duplicate_model_listing_is_deduplicated_stably():
    candidates = candidates_from_discovery(
        [_engine(models=("qwen", "qwen", "gemma"))],
        node_id="pc",
    )
    assert [item.model for item in candidates] == ["gemma", "qwen"]
