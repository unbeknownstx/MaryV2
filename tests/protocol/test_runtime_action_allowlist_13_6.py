import pytest

from mary.protocol.models import RuntimeActionRequest


def test_13_6_bounded_runtime_actions_are_protocol_reachable():
    actions = [
        "realtime.voice_activity",
        "realtime.brain_activity.status",
        "perception.browser.observe",
        "runtime.performance.status",
        "runtime.performance.set",
        "game.action.preview",
        "capability.invocations.status",
    ]
    for action in actions:
        parsed = RuntimeActionRequest.from_dict({
            "action": action,
            "args": {},
            "device_id": "iphone",
        })
        assert parsed.action == action


def test_runtime_action_allowlist_still_rejects_arbitrary_execution():
    with pytest.raises(ValueError):
        RuntimeActionRequest.from_dict({
            "action": "shell.execute",
            "args": {"command": "anything"},
            "device_id": "iphone",
        })
