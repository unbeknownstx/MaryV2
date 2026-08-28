from mary.protocol.models import TurnRequest


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
