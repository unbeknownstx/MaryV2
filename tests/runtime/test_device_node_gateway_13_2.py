from types import SimpleNamespace

from mary.distributed import NodeRegistry
from mary.runtime.gateway import LocalMaryGateway, RemoteMaryGateway


class FakeRemoteClient:
    def __init__(self):
        self.device_id = "windows-pc"
        self.calls = []

    def register_node(self, **kwargs):
        self.calls.append(("register", kwargs))
        return {"ok": True, "node": {"node_id": self.device_id}}

    def heartbeat_node(self):
        self.calls.append(("heartbeat", {}))
        return {"ok": True}

    def disconnect_node(self):
        self.calls.append(("disconnect", {}))
        return {"ok": True}

    def nodes(self):
        return {"nodes": []}

    def route_capability(self, capability, *, prefer_private=True, prefer_local=True):
        self.calls.append(("route", {"capability": capability}))
        return {"selected_node_id": self.device_id, "execution": "not_authorized"}

    def preview_capability_task(self, capability, intent):
        self.calls.append(("preview", {"capability": capability, "intent": intent}))
        return {"plan": {"selected_node_id": self.device_id, "execution_authorized": False}}


class FakeLocalMary:
    def __init__(self):
        self.node_registry = NodeRegistry()


class FakeLocalApplication:
    def __init__(self):
        self.mary = FakeLocalMary()


def test_remote_gateway_exposes_node_control_without_execution():
    client = FakeRemoteClient()
    gateway = RemoteMaryGateway(client, surface="desktop")

    result = gateway.register_node(
        display_name="Windows PC",
        host_type="desktop",
        platform="windows",
        surface="desktop",
        capabilities=[{"name": "filesystem", "private": True}],
    )
    assert result["ok"] is True
    assert gateway.route_capability("filesystem")["execution"] == "not_authorized"
    assert gateway.preview_capability_task("filesystem", "Find file")["plan"]["execution_authorized"] is False
    assert [name for name, _ in client.calls] == ["register", "route", "preview"]


def test_local_gateway_uses_same_non_executing_node_contract():
    app = FakeLocalApplication()
    gateway = LocalMaryGateway(app, device_id="local-pc", surface="desktop")

    gateway.register_node(
        display_name="Local PC",
        host_type="desktop",
        platform="windows",
        surface="desktop",
        capabilities=[{"name": "filesystem", "private": True, "local": True}],
    )
    route = gateway.route_capability("filesystem")
    preview = gateway.preview_capability_task("filesystem", "Find manuscript")

    assert route["selected_node_id"] == "local-pc"
    assert route["execution"] == "not_authorized"
    assert preview["plan"]["selected_node_id"] == "local-pc"
    assert preview["execution"]["authorized"] is False
