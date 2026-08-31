"""Integration coverage for Core/device capability authority boundaries."""

from copy import deepcopy
from threading import Barrier, Event, Thread
from time import monotonic
from types import SimpleNamespace

import pytest

from mary.core.service import MaryCoreService
from mary.distributed import DeviceExecutionPermissions, NodeRegistry


class _BoundaryMary:
    def __init__(self):
        self.node_registry = NodeRegistry()
        self.engagement = SimpleNamespace(status=lambda: {}, set_mode=lambda mode: {})
        self.realtime = SimpleNamespace(status=lambda: {})
        self.memory = SimpleNamespace(status=lambda: {"records": 1})
        self.relationship = SimpleNamespace(governance_status=lambda: {})
        self.growth = SimpleNamespace(status=lambda: {})
        self.runtime_environment = SimpleNamespace(snapshot=lambda: {})
        self._canonical_state = {
            "memory": [{"id": "mary-memory", "text": "Keep this private."}],
            "identity": {"name": "Mary", "owner": "core"},
            "experience": [{"kind": "creator_turn", "id": "experience-1"}],
        }

    def live_state(self, runtime_status=None):
        return {"name": "Mary"}

    def canonical_state(self):
        return deepcopy(self._canonical_state)


class _BoundaryApplication:
    def __init__(self):
        self.mary = _BoundaryMary()
        self.state = SimpleNamespace(to_dict=lambda: {})
        self.ecosystem = SimpleNamespace()

    def save(self):
        return True

    def close(self):
        return True


def _register(service, node_id, *, local=True):
    response = service.register_node({
        "node_id": node_id,
        "host_type": "desktop",
        "platform": "windows",
        "surface": "desktop",
        "local": local,
        "capabilities": [
            {"name": "personal_search", "private": True, "local": local}
        ],
    })
    assert response["ok"] is True
    return response["node_token"]


def _service():
    service = MaryCoreService(_BoundaryApplication(), instance_id="boundary-core")
    service.register_creator_surface({"surface_id": "test-creator"})
    return service


def test_preview_never_executes_and_dispatch_only_queues_a_typed_unapproved_task():
    service = _service()
    _register(service, "device-a")
    before = service.device_tasks.snapshot()

    preview = service.preview_capability_task({
        "capability": "personal_search",
        "intent": "Find the manuscript",
        "device_id": "phone",
    })
    assert preview["plan"]["selected_node_id"] == "device-a"
    assert preview["plan"]["execution_authorized"] is False
    assert preview["execution"] == {
        "authorized": False,
        "endpoint": None,
        "policy": "preview only; no device task was executed",
    }
    assert service.device_tasks.snapshot() == before

    body = service.dispatch_capability_task({
        "capability": "personal_search",
        "intent": "Find the manuscript",
        "args": {"query": " manuscript ", "limit": 99},
        "device_id": "phone",
    })
    assert body["execution"]["authorized_by_core"] is False
    assert body["execution"]["device_permission_required"] is True
    assert body["task"]["status"] == "queued"
    assert body["task"]["selected_node_id"] == "device-a"
    assert body["task"]["args"] == {"query": "manuscript", "limit": 12}
    assert service.device_tasks.snapshot()["queued"] == 1


def test_unknown_and_stale_nodes_cannot_receive_tasks_or_complete_another_nodes_task():
    service = _service()
    with pytest.raises(PermissionError, match="not live"):
        service.poll_capability_task({"node_id": "unknown-device"})

    selected_token = _register(service, "selected-device")
    other_token = _register(service, "other-device", local=False)
    queued = service.dispatch_capability_task({
        "capability": "personal_search",
        "intent": "Find the manuscript",
        "args": {"query": "manuscript"},
    })["task"]

    with pytest.raises(PermissionError, match="selected node"):
        service.complete_capability_task({
            "node_id": "other-device",
            "task_id": queued["task_id"],
            "status": "completed",
            "result": {"count": 99},
        }, node_token=other_token)
    assert service.capability_task_status(queued["task_id"])["task"]["result"] == {}

    with pytest.raises(KeyError, match="Unknown capability task"):
        service.complete_capability_task({
            "node_id": "selected-device",
            "task_id": "capability_task_missing",
            "status": "completed",
            "result": {"count": 1},
        }, node_token=selected_token)

    stale = service.mary.node_registry.get("selected-device")
    assert stale is not None
    stale.last_heartbeat_monotonic = monotonic() - service.mary.node_registry.stale_after - 1
    # Make every capable node stale; stale advertisements are not routes.
    other = service.mary.node_registry.get("other-device")
    assert other is not None
    other.last_heartbeat_monotonic = monotonic() - service.mary.node_registry.stale_after - 1
    with pytest.raises(LookupError, match="No connected node"):
        service.dispatch_capability_task({
            "capability": "personal_search",
            "intent": "Find only on stale nodes",
            "args": {"query": "manuscript"},
        })


def test_local_permission_and_task_completion_do_not_mutate_canonical_mary_state(tmp_path):
    service = _service()
    first_device = DeviceExecutionPermissions(tmp_path / "first.json")
    second_device = DeviceExecutionPermissions(tmp_path / "second.json")
    first_device.allow("personal_search")
    assert first_device.is_allowed("personal_search") is True
    assert second_device.is_allowed("personal_search") is False

    permitted_token = _register(service, "permitted-device")
    dispatched = service.dispatch_capability_task({
        "capability": "personal_search",
        "intent": "Find the manuscript",
        "args": {"query": "manuscript"},
    })
    assert dispatched["execution"]["authorized_by_core"] is False
    before = service.mary.canonical_state()

    completed = service.complete_capability_task({
        "node_id": "permitted-device",
        "task_id": dispatched["task"]["task_id"],
        "status": "completed",
        "result": {"count": 1, "items": [{"name": "draft.md"}]},
    }, node_token=permitted_token)
    assert completed["task"]["result"]["count"] == 1
    assert service.mary.canonical_state() == before
    assert service.device_tasks.snapshot()["tasks"][-1]["status"] == "completed"


def test_stale_task_expires_lazily_when_status_is_observed():
    service = _service()
    _register(service, "device-a")
    queued = service.dispatch_capability_task({
        "capability": "personal_search",
        "intent": "Find the manuscript",
        "args": {"query": "manuscript"},
    })["task"]
    node = service.mary.node_registry.get("device-a")
    assert node is not None
    node.last_heartbeat_monotonic = monotonic() - service.mary.node_registry.stale_after - 1

    # No worker request is needed: the bounded broker sweep observes lease loss
    # on ordinary task status reads.
    assert service.capability_task_status(queued["task_id"])["task"]["status"] == "expired"


def test_disconnect_races_have_linearizable_task_outcomes_and_reenrollment_revokes_old_token():
    service = _service()
    old_token = _register(service, "device-a")
    queued = service.dispatch_capability_task({
        "capability": "personal_search", "intent": "Find", "args": {"query": "draft"},
    })["task"]
    barrier = Barrier(2)
    poll_result: list[object] = []

    def poll():
        barrier.wait()
        try:
            poll_result.append(service.poll_capability_task(
                {"node_id": "device-a"}, node_token=old_token,
            ))
        except Exception as exc:
            poll_result.append(exc)

    def disconnect():
        barrier.wait()
        service.disconnect_node({"node_id": "device-a"}, node_token=old_token)

    workers = [Thread(target=poll), Thread(target=disconnect)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=1.0)
        assert not worker.is_alive()
    # Poll may linearize before disconnect, but disconnect atomically expires
    # even a just-claimed nonterminal task.
    assert poll_result
    assert service.capability_task_status(queued["task_id"])["task"]["status"] == "expired"

    # Creator-controlled recovery of a disconnected ID gets a new credential;
    # the pre-disconnect credential cannot revive or control the re-enrolled ID.
    new_token = _register(service, "device-a")
    assert new_token != old_token
    with pytest.raises(PermissionError, match="scoped node token"):
        service.heartbeat_node({"node_id": "device-a"}, node_token=old_token)

    claimed = service.dispatch_capability_task({
        "capability": "personal_search", "intent": "Find", "args": {"query": "draft"},
    })["task"]
    service.poll_capability_task({"node_id": "device-a"}, node_token=new_token)
    barrier = Barrier(2)
    completion_result: list[object] = []

    def complete():
        barrier.wait()
        try:
            completion_result.append(service.complete_capability_task({
                "node_id": "device-a", "task_id": claimed["task_id"],
                "status": "completed", "result": {"count": 1},
            }, node_token=new_token))
        except Exception as exc:
            completion_result.append(exc)

    def disconnect_reenrolled():
        barrier.wait()
        service.disconnect_node({"node_id": "device-a"}, node_token=new_token)

    workers = [Thread(target=complete), Thread(target=disconnect_reenrolled)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=1.0)
        assert not worker.is_alive()
    assert completion_result
    assert service.capability_task_status(claimed["task_id"])["task"]["status"] in {"completed", "expired"}


def test_parked_old_token_poll_cannot_claim_or_complete_after_reenrollment():
    service = _service()
    old_token = _register(service, "device-a")
    first_validation = Event()
    original_is_live = service.mary.node_registry.is_live

    def observed_is_live(node_id):
        first_validation.set()
        return original_is_live(node_id)

    # The service's per-poll validator resolves this method on every wake.
    service.mary.node_registry.is_live = observed_is_live
    old_poll_result: list[object] = []

    def old_long_poll():
        try:
            old_poll_result.append(service.poll_capability_task(
                {"node_id": "device-a", "wait_seconds": 1.0},
                node_token=old_token,
            ))
        except Exception as exc:
            old_poll_result.append(exc)

    worker = Thread(target=old_long_poll)
    worker.start()
    assert first_validation.wait(timeout=1.0)

    # Keep disconnect, credential rotation, and enqueue in one lifecycle
    # transaction. The parked request can wake only after the new task exists.
    with service.mary.node_registry.lifecycle_lock:
        service.disconnect_node({"node_id": "device-a"}, node_token=old_token)
        new_token = _register(service, "device-a")
        queued = service.dispatch_capability_task({
            "capability": "personal_search",
            "intent": "Find",
            "args": {"query": "draft"},
        })["task"]

    worker.join(timeout=1.0)
    assert not worker.is_alive()
    assert len(old_poll_result) == 1
    assert isinstance(old_poll_result[0], PermissionError)
    assert service.capability_task_status(queued["task_id"])["task"]["status"] == "queued"

    with pytest.raises(PermissionError, match="scoped node token"):
        service.complete_capability_task({
            "node_id": "device-a",
            "task_id": queued["task_id"],
            "status": "completed",
            "result": {"count": 1},
        }, node_token=old_token)
    assert service.poll_capability_task(
        {"node_id": "device-a"}, node_token=new_token,
    )["task"]["task_id"] == queued["task_id"]


def test_stale_reenrollment_expires_queued_and_claimed_prior_session_work():
    service = _service()
    old_token = _register(service, "device-a")
    claimed = service.dispatch_capability_task({
        "capability": "personal_search",
        "intent": "Prior claimed work",
        "args": {"query": "claimed"},
    })["task"]
    queued = service.dispatch_capability_task({
        "capability": "personal_search",
        "intent": "Prior queued work",
        "args": {"query": "queued"},
    })["task"]
    assert service.poll_capability_task(
        {"node_id": "device-a"}, node_token=old_token,
    )["task"]["task_id"] == claimed["task_id"]

    node = service.mary.node_registry.get("device-a")
    assert node is not None
    node.last_heartbeat_monotonic = monotonic() - service.mary.node_registry.stale_after - 1
    new_token = _register(service, "device-a")
    assert new_token != old_token

    for task_id in (claimed["task_id"], queued["task_id"]):
        old_task = service.capability_task_status(task_id)["task"]
        assert old_task["status"] == "expired"
        assert "enrollment/session was replaced" in old_task["error"]

    # The replacement credential cannot transition prior-session work.
    completion = service.complete_capability_task({
        "node_id": "device-a",
        "task_id": claimed["task_id"],
        "status": "completed",
        "result": {"count": 1},
    }, node_token=new_token)
    assert completion["task"]["status"] == "expired"
    assert service.poll_capability_task(
        {"node_id": "device-a"}, node_token=new_token,
    )["task"] is None

    fresh = service.dispatch_capability_task({
        "capability": "personal_search",
        "intent": "Replacement-session work",
        "args": {"query": "fresh"},
    })["task"]
    assert service.poll_capability_task(
        {"node_id": "device-a"}, node_token=new_token,
    )["task"]["task_id"] == fresh["task_id"]