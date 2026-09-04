from types import SimpleNamespace

from mary.core.service import MaryCoreService
from mary.protocol.models import TurnRequest


class FakeEngagement:
    def __init__(self):
        self.mode = "adaptive"
        self.last_plan = {"effective_mode": "adaptive"}
    def set_mode(self, mode):
        self.mode = mode
        self.last_plan = {"effective_mode": mode}
    def status(self):
        return {"mode": self.mode, "last_plan": dict(self.last_plan), "active_session": {}}


class FakeRealtime:
    def status(self):
        return {"phase": "idle"}


class FakeMemory:
    def status(self):
        return {"episodic": {"count": 1}}


class FakeGrowth:
    def status(self):
        return {"version": "13.0", "journal": {"records": 0}}


class FakeRelationship:
    def governance_status(self):
        return {"ok": True}


class FakeMary:
    def __init__(self):
        self.engagement = FakeEngagement()
        self.realtime = FakeRealtime()
        self.memory = FakeMemory()
        self.growth = FakeGrowth()
        self.relationship = FakeRelationship()
        self.runtime_environment = SimpleNamespace(snapshot=lambda: {"host_type": "test"})
        self.node_registry = SimpleNamespace(snapshot=lambda: {"nodes": []})
    def live_state(self, runtime_status=None):
        return {"name": "Mary", "runtime_status": runtime_status}


class FakeApplication:
    def __init__(self):
        self.mary = FakeMary()
        self.state = SimpleNamespace(to_dict=lambda: {"status": "ready"})
        self.calls = []
    def run(self, text, turn_id=None, metadata=None):
        self.calls.append((text, dict(metadata or {})))
        return SimpleNamespace(success=True, output="hi", error=None, turn_id=turn_id or "turn-1", metadata={"pipeline_values": {}})
    def save(self):
        return True
    def close(self):
        return True


def test_core_owns_and_uses_one_application_turn_pipeline():
    app = FakeApplication()
    core = MaryCoreService(app, instance_id="test-core")
    core.register_creator_surface({"surface_id": "iphone"})
    result = core.process_turn(TurnRequest.from_dict({
        "text": "hello",
        "conversation_id": "c1",
        "device_id": "iphone",
        "requested_mode": "quick",
    }))
    assert core.application is app
    assert core.mary is app.mary
    assert result.response == "hi"
    assert result.conversation_id == "c1"
    assert result.effective_mode == "quick"
    assert app.calls[0][1]["device_id"] == "iphone"
    assert app.calls[0][1]["conversation_id"] == "c1"


def test_core_turn_projects_bounded_timing_and_lane_observability():
    app = FakeApplication()
    reasoning = SimpleNamespace(metadata={
        "provider": "groq",
        "model": "test-model",
        "provider_attempts": [{
            "provider": "groq",
            "status": "success",
            "error": "private provider exception text",
        }],
        "conversation_lane": {
            "lane": "conversation",
            "rationale": "internal policy detail",
            "latency_target_ms": 3500,
        },
    })
    cycle = SimpleNamespace(
        reasoning=reasoning,
        metadata={
            "timings": {
                "context_ms": 1.25,
                "reasoning_ms": 4.5,
                "cognition_total_ms": 7.75,
                "private_timing": 999.0,
            },
        },
    )

    def run(text, metadata=None):
        app.calls.append((text, dict(metadata or {})))
        return SimpleNamespace(
            success=True,
            output="hi",
            error=None,
            turn_id="turn-observed",
            metadata={
                "pipeline_values": {
                    "cognitive_cycle": cycle,
                },
            },
        )

    app.run = run
    core = MaryCoreService(app, instance_id="observability-core")
    core.register_creator_surface({"surface_id": "iphone"})
    result = core.process_turn(TurnRequest.from_dict({
        "text": "hello",
        "conversation_id": "observability",
        "device_id": "iphone",
    }))

    assert result.provenance["conversation_lane"] == {"lane": "conversation"}
    assert result.provenance["provider_attempts"] == [
        {"provider": "groq", "status": "success"}
    ]
    assert result.display_hints["timings"]["context_ms"] == 1.25
    assert result.display_hints["timings"]["reasoning_ms"] == 4.5
    assert result.display_hints["timings"]["cognition_total_ms"] == 7.75
    assert result.display_hints["timings"]["pipeline_ms"] >= 0.0
    assert "private_timing" not in result.display_hints["timings"]
    assert "rationale" not in result.provenance["conversation_lane"]


def test_creator_surface_registration_returns_core_continuity_handshake():
    app = FakeApplication()
    core = MaryCoreService(app, instance_id="surface-core")
    payload = core.register_creator_surface({"surface_id": "mac-app"})
    assert payload["handshake"]["instance_id"] == "surface-core"
    assert payload["handshake"]["architecture"] == "13.3"
    assert payload["handshake"]["peer_kind"] == "creator_surface"
    assert payload["handshake"]["state_authority"] == "core"
