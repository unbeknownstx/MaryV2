from mary.distributed.model_capability_evidence import (
    build_capability_evidence,
    run_boolean_probe,
)
from mary.distributed.model_instances import model_instance_from_capability


def test_probe_keeps_only_structural_outcome():
    result = run_boolean_probe("tools", lambda: True)
    payload = result.to_dict()
    assert payload["supported"] is True
    assert "prompt" not in payload
    assert "response" not in payload


def test_probe_failure_is_normalized_without_provider_error_prose():
    def boom():
        raise ConnectionError("secret endpoint detail")

    result = run_boolean_probe("vision", boom)
    assert result.supported is None
    assert result.error_class == "transport"
    assert "secret endpoint detail" not in str(result.to_dict())


def test_measured_negative_capability_overrides_advertised_positive():
    evidence = build_capability_evidence(
        qualified_model_id="node/ollama/qwen",
        model_fingerprint="abc123",
        probes={"tools": lambda: False, "vision": lambda: True},
        loaded_context=4096,
    )
    metadata = {
        "configured_model": "qwen",
        "supports_tools": True,
        "supports_vision": False,
        **evidence.metadata_overlay(),
    }
    instance = model_instance_from_capability(
        node_id="node",
        capability_name="llm.ollama",
        metadata=metadata,
    )
    assert instance is not None
    assert instance.capabilities["tools"].value is False
    assert instance.capabilities["tools"].source == "measured"
    assert instance.capabilities["vision"].value is True
    assert instance.capabilities["vision"].source == "measured"
    assert instance.loaded_context == 4096


def test_evidence_overlay_carries_structured_json_without_claiming_authority():
    evidence = build_capability_evidence(
        qualified_model_id="node/openai_compat/model",
        model_fingerprint="fingerprint",
        probes={
            "structured_json": lambda: True,
            "embeddings": lambda: False,
        },
        trained_context=32768,
    )
    overlay = evidence.metadata_overlay()
    assert overlay["measured_structured_json"] is True
    assert overlay["measured_embeddings"] is False
    assert overlay["trained_context"] == 32768
    assert evidence.to_dict()["authority"] == "measured_runtime_evidence_only"

    instance = model_instance_from_capability(
        node_id="node",
        capability_name="llm.openai_compat",
        metadata={
            "configured_model": "model",
            "supports_structured_json": False,
            **overlay,
        },
    )
    assert instance is not None
    assert instance.capabilities["structured_json"].value is True
    assert instance.capabilities["structured_json"].source == "measured"
    assert instance.capabilities["embeddings"].value is False
    assert instance.capabilities["embeddings"].source == "measured"
