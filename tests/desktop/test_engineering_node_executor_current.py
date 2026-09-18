from __future__ import annotations

from types import SimpleNamespace

from mary.desktop import device_node as device_module
from mary.desktop.device_node import DesktopCapabilityNodeAgent
from mary.distributed import DeviceExecutionPermissions


class FakeGateway:
    device_id = "engineering-node"

    def __init__(self):
        self.completions = []

    def register_node(self, **kwargs):
        return {"ok": True}

    def heartbeat_node(self):
        return {"ok": True}

    def disconnect_node(self):
        return {"ok": True}

    def complete_capability_task(self, task_id, *, status, result=None, error=""):
        payload = {
            "task_id": task_id,
            "status": status,
            "result": result or {},
            "error": error,
        }
        self.completions.append(payload)
        return {"ok": True, "task": payload}


class FakeBridge:
    integrations = SimpleNamespace(status=lambda: [])
    creative_workspace = SimpleNamespace(configured=False)


class FakeApplication:
    ecosystem = SimpleNamespace(search=None)


class FakeEngineeringWorker:
    calls = []

    def execute(self, capability, args):
        self.__class__.calls.append((capability, dict(args)))
        return {
            "ok": True,
            "capability": capability,
            "summary": "bounded proposal ready",
            "proposal_id": "engineering_proposal_test",
            "diff": "--- a\n+++ b",
        }


def _task():
    return {
        "task_id": "capability_task_engineering",
        "capability": "engineering.repair.plan",
        "intent": "Fix a bounded MaryV2 issue",
        "args": {
            "task": "Fix the status projection",
            "max_files": 4,
        },
    }


def test_engineering_task_is_rejected_until_local_permission_exists(tmp_path, monkeypatch):
    FakeEngineeringWorker.calls = []
    monkeypatch.setattr(device_module, "EngineeringWorker", FakeEngineeringWorker)

    gateway = FakeGateway()
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    agent = DesktopCapabilityNodeAgent(
        gateway,
        application=FakeApplication(),
        bridge=FakeBridge(),
        permissions=permissions,
    )

    result = agent._handle_task(_task())

    assert result["task"]["status"] == "rejected"
    assert "does not allow" in gateway.completions[-1]["error"]
    assert FakeEngineeringWorker.calls == []


def test_authorized_engineering_task_uses_bounded_worker(tmp_path, monkeypatch):
    FakeEngineeringWorker.calls = []
    monkeypatch.setattr(device_module, "EngineeringWorker", FakeEngineeringWorker)

    gateway = FakeGateway()
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    permissions.allow("engineering.repair.plan")
    agent = DesktopCapabilityNodeAgent(
        gateway,
        application=FakeApplication(),
        bridge=FakeBridge(),
        permissions=permissions,
    )

    result = agent._handle_task(_task())

    assert result["task"]["status"] == "completed"
    assert FakeEngineeringWorker.calls == [
        (
            "engineering.repair.plan",
            {"task": "Fix the status projection", "max_files": 4},
        )
    ]
    payload = gateway.completions[-1]["result"]
    assert payload["proposal_id"] == "engineering_proposal_test"
    assert payload["summary"] == "bounded proposal ready"
