from mary.distributed.model_instances import (
    CapabilityFact,
    ModelInstanceIdentity,
    ModelInstanceRegistry,
    capability_fact,
    instances_from_node_snapshot,
)


def test_same_model_on_two_nodes_has_distinct_qualified_identity():
    left = ModelInstanceIdentity(node_id="pc", engine="ollama", model="qwen3:4b")
    right = ModelInstanceIdentity(node_id="mac", engine="ollama", model="qwen3:4b")
    assert left.qualified_id != right.qualified_id
    assert left.fingerprint != right.fingerprint


def test_measured_false_beats_weaker_positive_guess():
    fact = capability_fact(
        measured=False,
        advertised=True,
        known=True,
        heuristic=True,
    )
    assert fact == CapabilityFact(False, "measured")


def test_registry_refuses_ambiguous_bare_model_name():
    registry = ModelInstanceRegistry([
        ModelInstanceIdentity(node_id="pc", engine="ollama", model="qwen3:4b"),
        ModelInstanceIdentity(node_id="mac", engine="ollama", model="qwen3:4b"),
    ])
    try:
        registry.resolve("qwen3:4b")
    except ValueError as exc:
        assert "ambiguous" in str(exc).lower()
        assert "pc/ollama/qwen3:4b" in str(exc)
        assert "mac/ollama/qwen3:4b" in str(exc)
    else:
        raise AssertionError("ambiguous bare model must not be guessed")


def test_node_snapshot_projects_exact_runtime_model_instance():
    snapshot = {
        "nodes": [{
            "node_id": "desktop",
            "capabilities": {
                "llm.ollama": {
                    "metadata": {
                        "configured_model": "qwen3:4b",
                        "num_ctx": 8192,
                        "quantization": "Q4_K_M",
                        "supports_tools": True,
                        "measured_tools": False,
                    }
                },
                "personal_search": {"metadata": {}},
            },
        }]
    }
    [instance] = instances_from_node_snapshot(snapshot)
    assert instance.qualified_id == "desktop/ollama/qwen3:4b@Q4_K_M"
    assert instance.loaded_context == 8192
    assert instance.capabilities["tools"].value is False
    assert instance.capabilities["tools"].source == "measured"
    assert instance.to_dict()["authority"] == "replaceable_cognition_worker_only"
