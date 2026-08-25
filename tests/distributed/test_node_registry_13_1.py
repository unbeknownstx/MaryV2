from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry


def node(node_id, *, local, private, cost="free"):
    cap = CapabilityDescriptor("llm.chat", private=private, local=local, cost=cost)
    return NodeDescriptor(node_id=node_id, role="test", host_type="test", platform="test", capabilities={cap.name: cap}, local=local)


def test_registry_prefers_private_local_free_node():
    registry = NodeRegistry(stale_after=90)
    registry.register(node("cloud", local=False, private=False, cost="provider_policy"))
    registry.register(node("home", local=True, private=True, cost="local"))
    assert registry.choose("llm.chat").node_id == "home"


def test_snapshot_is_display_safe_mapping():
    registry = NodeRegistry()
    descriptor = node("home", local=True, private=True)
    descriptor.capabilities["llm.chat"] = CapabilityDescriptor(
        "llm.chat", private=True, metadata={"model": "qwen", "api_key": "secret"}
    )
    registry.register(descriptor)
    snap = registry.snapshot()
    capabilities = snap["nodes"][0]["capabilities"]
    assert "llm.chat" in capabilities
    assert "api_key" not in capabilities["llm.chat"]["metadata"]
    assert "secret" not in repr(snap)
