from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry, preview_capability_task


def test_remote_capability_node_never_owns_mary_state():
    registry = NodeRegistry()
    cap = CapabilityDescriptor("filesystem", private=True, local=True)
    node = registry.register(
        NodeDescriptor(
            node_id="windows-pc",
            display_name="Windows PC",
            role="capability_node",
            host_type="desktop",
            platform="windows",
            surface="desktop",
            transport="mary_protocol",
            capabilities={cap.name: cap},
            execution_policy="authorization_required",
        )
    )

    payload = node.to_dict(stale_after=registry.stale_after)
    assert payload["connected"] is True
    assert payload["ownership"] == {
        "character_identity": False,
        "memory": False,
        "canonical_state": False,
    }
    assert payload["execution"]["authorized"] is False


def test_route_preview_selects_capability_but_cannot_execute():
    registry = NodeRegistry()
    cap = CapabilityDescriptor("personal_search", private=True, local=True)
    registry.register(
        NodeDescriptor(
            node_id="windows-pc",
            role="capability_node",
            host_type="desktop",
            platform="windows",
            capabilities={cap.name: cap},
        )
    )

    route = registry.route_preview("personal_search")
    assert route["selected_node_id"] == "windows-pc"
    assert route["execution"] == "not_authorized"

    plan = preview_capability_task(
        registry,
        capability="personal_search",
        intent="Find my current manuscript",
        requester_device_id="iphone",
    )
    assert plan.status == "route_candidate"
    assert plan.selected_node_id == "windows-pc"
    assert plan.execution_authorized is False
    assert plan.execution_endpoint is None


def test_disconnect_makes_node_immediately_unavailable():
    registry = NodeRegistry()
    cap = CapabilityDescriptor("filesystem", private=True, local=True)
    registry.register(
        NodeDescriptor(
            node_id="windows-pc",
            role="capability_node",
            host_type="desktop",
            platform="windows",
            capabilities={cap.name: cap},
        )
    )

    assert registry.choose("filesystem") is not None
    assert registry.disconnect("windows-pc") is True
    assert registry.choose("filesystem") is None
    assert registry.snapshot()["connected"] == 0


def test_capability_metadata_filters_secret_like_fields():
    cap = CapabilityDescriptor.from_dict({
        "name": "llm.ollama",
        "metadata": {
            "model_count": 3,
            "api_key": "do-not-expose",
            "authorization": "Bearer secret",
        },
    })
    payload = cap.to_dict()
    assert payload["metadata"] == {"model_count": 3}
    assert "do-not-expose" not in repr(payload)
