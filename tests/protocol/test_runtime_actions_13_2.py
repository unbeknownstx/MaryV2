from types import SimpleNamespace

import pytest

from mary.core.service import MaryCoreService
from mary.protocol.models import RuntimeActionRequest, TurnRequest


class FakeEngagement:
    def __init__(self):
        self.mode = "adaptive"
        self.session = {}

    def set_mode(self, mode):
        self.mode = mode
        return self.status()

    def begin_session(self, mode="engaged", *, turns=8, reason="explicit"):
        self.session = {"mode": mode, "turns_remaining": turns, "reason": reason}

    def end_session(self):
        self.session = {}

    def status(self):
        return {"mode": self.mode, "last_plan": {"effective_mode": self.mode}, "active_session": dict(self.session)}


class FakeRealtime:
    def __init__(self):
        self.events = []

    def speech_started(self, **kwargs):
        self.events.append(("started", kwargs))

    def speech_ended(self, **kwargs):
        self.events.append(("ended", kwargs))

    def interrupt(self, **kwargs):
        self.events.append(("interrupt", kwargs))

    def status(self):
        return {"events": list(self.events)}


class FakeMary:
    def __init__(self):
        self.engagement = FakeEngagement()
        self.realtime = FakeRealtime()
        self.memory = SimpleNamespace(status=lambda: {})
        self.relationship = SimpleNamespace(governance_status=lambda: {})
        self.growth = SimpleNamespace(status=lambda: {})
        self.runtime_environment = SimpleNamespace(snapshot=lambda: {})
        self.node_registry = SimpleNamespace(snapshot=lambda: {})

    def live_state(self, runtime_status=None):
        return {"runtime_status": runtime_status}


class FakeApplication:
    def __init__(self):
        self.mary = FakeMary()
        self.state = SimpleNamespace(to_dict=lambda: {})
        self.calls = []
        self.ecosystem = SimpleNamespace()

    def run(self, text, metadata=None):
        self.calls.append(dict(metadata or {}))
        return SimpleNamespace(success=True, output="ok", error=None, turn_id="turn-1", metadata={"pipeline_values": {}})

    def save(self):
        return True

    def close(self):
        return True


def test_turn_request_carries_surface_and_voice_context_to_core():
    app = FakeApplication()
    core = MaryCoreService(app, instance_id="runtime-core")

    core.process_turn(
        TurnRequest.from_dict(
            {
                "text": "hello",
                "conversation_id": "creator-primary",
                "device_id": "iphone",
                "surface": "mobile",
                "voice_input": True,
            }
        )
    )

    metadata = app.calls[0]
    assert metadata["surface"] == "mobile"
    assert metadata["transport"] == "core"
    assert metadata["device_id"] == "iphone"
    assert metadata["voice_input"] is True


def test_runtime_action_controls_conversation_without_new_mary():
    app = FakeApplication()
    core = MaryCoreService(app, instance_id="runtime-core")

    result = core.runtime_action(
        {
            "action": "conversation.begin_session",
            "args": {"mode": "deep", "turns": 5},
            "device_id": "pc",
        }
    )

    assert core.application is app
    assert result["active_session"]["mode"] == "deep"
    assert result["active_session"]["turns_remaining"] == 5


def test_runtime_action_routes_presentation_speech_to_canonical_realtime():
    app = FakeApplication()
    core = MaryCoreService(app, instance_id="runtime-core")

    core.runtime_action(
        RuntimeActionRequest.from_dict(
            {
                "action": "realtime.speech_started",
                "args": {"turn_id": "turn-5"},
                "device_id": "iphone",
            }
        )
    )
    core.runtime_action(
        {
            "action": "realtime.interrupt",
            "args": {"reason": "barge_in"},
            "device_id": "iphone",
        }
    )

    events = app.mary.realtime.events
    assert events[0][0] == "started"
    assert events[0][1]["source"] == "protocol:iphone"
    assert events[1][0] == "interrupt"
    assert events[2][0] == "ended"
