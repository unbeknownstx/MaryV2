from types import SimpleNamespace

from mary.desktop import device_node as device_module
from mary.desktop.device_node import DesktopCapabilityNodeAgent
from mary.distributed import DeviceExecutionPermissions


class FakeSearch:
    roots = ["C:/private-root"]

    def search(self, query, *, limit=8):
        assert query == "Unbeknownst"
        return [{
            "name": "Unbeknownst Final.docx",
            "relative_path": "Books/Unbeknownst Final.docx",
            "root": "C:/Users/private/Documents",
            "path": "C:/Users/private/Documents/Books/Unbeknownst Final.docx",
            "kind": "docx",
            "snippet": "latest manuscript result",
            "match": "name",
        }]


class FakeGateway:
    device_id = "windows-pc"

    def __init__(self):
        self.completions = []

    def register_node(self, **kwargs):
        return {"ok": True}

    def heartbeat_node(self):
        return {"ok": True}

    def disconnect_node(self):
        return {"ok": True}

    def complete_capability_task(self, task_id, *, status, result=None, error=""):
        payload = {"task_id": task_id, "status": status, "result": result or {}, "error": error}
        self.completions.append(payload)
        return {"ok": True, "task": payload}


class FakeBridge:
    integrations = SimpleNamespace(status=lambda: [])
    creative_workspace = SimpleNamespace(configured=False)


class FakeApplication:
    ecosystem = SimpleNamespace(search=FakeSearch())


def _task():
    return {
        "task_id": "capability_task_123",
        "capability": "personal_search",
        "intent": "Find newest manuscript",
        "args": {"query": "Unbeknownst", "limit": 8},
    }


def test_personal_search_task_is_rejected_until_local_permission_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(device_module, "_ollama_capability", lambda: None)
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


def test_authorized_personal_search_omits_absolute_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(device_module, "_ollama_capability", lambda: None)
    gateway = FakeGateway()
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    permissions.allow("personal_search")
    agent = DesktopCapabilityNodeAgent(
        gateway,
        application=FakeApplication(),
        bridge=FakeBridge(),
        permissions=permissions,
    )
    result = agent._handle_task(_task())
    assert result["task"]["status"] == "completed"
    payload = gateway.completions[-1]["result"]
    assert payload["count"] == 1
    assert payload["items"][0]["relative_path"] == "Books/Unbeknownst Final.docx"
    assert "C:/Users/private" not in repr(payload)
    assert "root" not in payload["items"][0]
    assert "path" not in payload["items"][0]
