from threading import RLock
from types import SimpleNamespace

from mary.core.service import MaryCoreService
from mary.protocol.models import RuntimeActionRequest
from mary.relationship.manager import RelationshipManager
from mary.relationship.relational_presence import RelationalPresenceRuntime


def _core(tmp_path):
    manager = RelationshipManager(path=tmp_path / "relationship.json")
    manager.load()
    relational = RelationalPresenceRuntime(manager)
    core = object.__new__(MaryCoreService)
    core._closed = False
    core._turn_lock = RLock()
    core.mary = SimpleNamespace(
        performance_hardening=SimpleNamespace(relational_presence=relational)
    )
    return core, manager, relational


def _action(core, action, args=None):
    return core.runtime_action(RuntimeActionRequest.from_dict({
        "action": action,
        "args": dict(args or {}),
        "device_id": "creator-test",
    }))


def test_relationship_mode_and_shared_activity_flow_through_single_writer_core(tmp_path):
    core, manager, relational = _core(tmp_path)

    changed = _action(core, "relationship.set_mode", {"mode": "close"})
    assert changed["mode"] == "close"
    assert manager.history.summary()["relationship_mode"] == "close"

    started = _action(core, "shared_activity.start", {
        "activity_type": "create",
        "title": "Create together",
        "context": "Work on a creative project together.",
    })
    assert started["durable_write_performed"] is False
    assert relational.snapshot()["active_activity"]["activity_type"] == "create"

    _action(core, "shared_activity.note", {"note": "We found a useful direction."})
    completed = _action(core, "shared_activity.complete", {
        "summary": "Mary and creator worked on a creative project together.",
        "importance": 0.85,
    })
    assert completed["durable_write_performed"] is True
    assert completed["event"]["type"] == "shared_experience"
    assert relational.snapshot()["active_activity"] is None
    assert manager.history.summary()["shared_experiences"] == 1


def test_shared_activity_cancel_is_ephemeral(tmp_path):
    core, manager, relational = _core(tmp_path)
    before = manager.history.summary()["shared_experiences"]
    _action(core, "shared_activity.start", {
        "activity_type": "music",
        "title": "Listen together",
    })
    cancelled = _action(core, "shared_activity.cancel")
    assert cancelled["durable_write_performed"] is False
    assert relational.snapshot()["active_activity"] is None
    assert manager.history.summary()["shared_experiences"] == before


def test_relational_actions_are_typed_protocol_actions():
    for action in (
        "relationship.status",
        "relationship.set_mode",
        "shared_activity.start",
        "shared_activity.note",
        "shared_activity.complete",
        "shared_activity.cancel",
    ):
        assert RuntimeActionRequest.from_dict({"action": action, "args": {}}).action == action
