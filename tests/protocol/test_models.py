from mary.protocol.models import CreatorSurfaceRequest, TurnRequest


def test_turn_request_normalizes_contract():
    request = TurnRequest.from_dict({"text": "  hello  ", "device_id": "iphone", "requested_mode": "DEEP"})
    assert request.text == "hello"
    assert request.device_id == "iphone"
    assert request.requested_mode == "deep"
    assert request.conversation_id.startswith("conversation_")


def test_turn_request_rejects_bad_mode():
    try:
        TurnRequest.from_dict({"text": "hello", "requested_mode": "turbo"})
    except ValueError as exc:
        assert "requested_mode" in str(exc)
    else:
        raise AssertionError("invalid mode should fail")


def test_node_task_poll_request_bounds_long_poll_wait():
    from mary.protocol.models import NodeTaskPollRequest

    request = NodeTaskPollRequest.from_dict({"node_id": "windows-pc", "wait_seconds": 20})
    assert request.wait_seconds == 20.0
    assert NodeTaskPollRequest.from_dict({"node_id": "windows-pc", "wait_seconds": 999}).wait_seconds == 25.0
    assert NodeTaskPollRequest.from_dict({"node_id": "windows-pc"}).wait_seconds == 0.0



def test_surface_presentation_capabilities_are_bounded_and_boolean():
    request = CreatorSurfaceRequest.from_dict({
        "surface_id": "desktop-session",
        "presentation_capabilities": {
            "expression_cues": True,
            "motion_assets": False,
            "transparent_overlay": True,
        },
    })
    assert request.presentation_capabilities == {
        "expression_cues": True,
        "motion_assets": False,
        "transparent_overlay": True,
    }

    try:
        CreatorSurfaceRequest.from_dict({
            "surface_id": "desktop-session",
            "presentation_capabilities": {"arbitrary_shell_access": True},
        })
    except ValueError as exc:
        assert "presentation capability" in str(exc).lower()
    else:
        raise AssertionError("unknown presentation capability should fail")

    try:
        CreatorSurfaceRequest.from_dict({
            "surface_id": "desktop-session",
            "presentation_capabilities": {"motion_assets": "yes"},
        })
    except ValueError as exc:
        assert "booleans" in str(exc)
    else:
        raise AssertionError("non-boolean presentation capability should fail")


def test_turn_request_can_bind_to_exact_creator_surface_lease():
    request = TurnRequest.from_dict({
        "text": "hello",
        "device_id": "pc",
        "surface": "desktop",
        "surface_id": "desktop-pc-session-123",
    })
    assert request.surface_id == "desktop-pc-session-123"
