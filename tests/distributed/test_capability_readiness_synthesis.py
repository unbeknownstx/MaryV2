from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry


def _node(node_id: str, readiness: str):
    cap = CapabilityDescriptor(
        "llm.llama_cpp", private=True, local=True, cost="local", readiness=readiness,
    )
    return NodeDescriptor(
        node_id=node_id, role="worker", host_type="desktop", platform="test",
        capabilities={cap.name: cap},
    )


def test_starting_capability_is_not_routable_but_ready_one_is():
    registry = NodeRegistry()
    registry.register(_node("starting", "starting"))
    registry.register(_node("ready", "ready"))
    assert registry.choose("llm.llama_cpp").node_id == "ready"
    preview = registry.route_preview("llm.llama_cpp")
    assert preview["selected_node_id"] == "ready"
    assert preview["candidate_readiness"] == {"ready": "ready"}


def test_readiness_can_transition_without_reregistering_node():
    registry = NodeRegistry()
    registry.register(_node("mac", "starting"))
    assert registry.choose("llm.llama_cpp") is None
    assert registry.update_capability_readiness("mac", "llm.llama_cpp", "ready") is True
    assert registry.choose("llm.llama_cpp").node_id == "mac"
    snapshot = registry.snapshot()
    cap = snapshot["nodes"][0]["capabilities"]["llm.llama_cpp"]
    assert cap["readiness"] == "ready"
    assert cap["routable"] is True


def test_degraded_is_routable_but_loses_to_ready():
    registry = NodeRegistry()
    registry.register(_node("degraded", "degraded"))
    registry.register(_node("ready", "ready"))
    assert registry.choose("llm.llama_cpp").node_id == "ready"
