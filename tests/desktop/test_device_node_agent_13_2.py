from types import SimpleNamespace

from mary.desktop import device_node as device_module
from mary.desktop.device_node import DesktopCapabilityNodeAgent, desktop_capabilities


class FakeGateway:
    device_id = "windows-pc"

    def __init__(self):
        self.register_calls = []
        self.heartbeats = 0
        self.disconnects = 0
        self.fail_heartbeat = False

    def register_node(self, **kwargs):
        self.register_calls.append(kwargs)
        return {"ok": True, "node": {"node_id": self.device_id}}

    def heartbeat_node(self):
        self.heartbeats += 1
        if self.fail_heartbeat:
            self.fail_heartbeat = False
            raise KeyError("core restarted")
        return {"ok": True}

    def disconnect_node(self):
        self.disconnects += 1
        return {"ok": True}


class FakeIntegrations:
    def status(self):
        return [
            {"key": "photoshop", "available": True},
            {"key": "blender", "available": False},
        ]


class FakeBridge:
    def __init__(self):
        self.integrations = FakeIntegrations()
        self.creative_workspace = SimpleNamespace(configured=True)


class FakeApplication:
    def __init__(self):
        self.ecosystem = SimpleNamespace(search=SimpleNamespace(roots=["C:/private-alpha", "D:/private-beta"]))


def test_desktop_advertisement_is_path_free_and_permission_bounded(monkeypatch):
    monkeypatch.setattr(device_module, "_ollama_capability", lambda: None)
    items = desktop_capabilities(FakeApplication(), FakeBridge())
    by_name = {item.name: item.to_dict() for item in items}

    assert by_name["filesystem"]["private"] is True
    assert by_name["filesystem"]["metadata"] == {"search_root_count": 2}
    assert by_name["desktop_apps"]["metadata"] == {"available_app_count": 1}
    assert "C:/private-alpha" not in repr(by_name)
    assert "D:/private-beta" not in repr(by_name)


def test_desktop_agent_reregisters_after_core_restart(monkeypatch):
    monkeypatch.setattr(device_module, "_ollama_capability", lambda: None)
    gateway = FakeGateway()
    agent = DesktopCapabilityNodeAgent(
        gateway,
        application=FakeApplication(),
        bridge=FakeBridge(),
    )

    assert agent.register()["ok"] is True
    gateway.fail_heartbeat = True
    assert agent.heartbeat()["ok"] is True

    assert len(gateway.register_calls) == 2
    assert agent.status()["execution_authorized"] is False
    assert agent.disconnect()["ok"] is True
