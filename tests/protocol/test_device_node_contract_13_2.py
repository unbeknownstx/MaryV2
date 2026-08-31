from types import SimpleNamespace

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from mary.core.service import MaryCoreService
from mary.distributed import NodeRegistry
from mary.protocol.server import create_app


class FakeMary:
    def __init__(self):
        self.node_registry = NodeRegistry()
        self.engagement = SimpleNamespace(status=lambda: {}, set_mode=lambda mode: {})
        self.realtime = SimpleNamespace(status=lambda: {})
        self.memory = SimpleNamespace(status=lambda: {})
        self.relationship = SimpleNamespace(governance_status=lambda: {})
        self.growth = SimpleNamespace(status=lambda: {})
        self.runtime_environment = SimpleNamespace(snapshot=lambda: {})

    def live_state(self, runtime_status=None):
        return {"name": "Mary"}


class FakeApplication:
    def __init__(self):
        self.mary = FakeMary()
        self.state = SimpleNamespace(to_dict=lambda: {})
        self.ecosystem = SimpleNamespace()

    def save(self):
        return True

    def close(self):
        return True


def test_protocol_register_heartbeat_route_preview_and_disconnect(monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "node-secret")
    service = MaryCoreService(FakeApplication(), instance_id="node-core")
    app = create_app(service)
    headers = {"Authorization": "Bearer node-secret"}

    with TestClient(app) as client:
        registered = client.post(
            "/v1/nodes/register",
            headers=headers,
            json={
                "node_id": "windows-pc",
                "display_name": "Windows PC",
                "host_type": "desktop",
                "platform": "windows",
                "surface": "desktop",
                "local": True,
                "capabilities": [
                    {
                        "name": "personal_search",
                        "private": True,
                        "local": True,
                        "metadata": {"root_count": 2, "api_key": "must-not-leak"},
                    }
                ],
            },
        )
        assert registered.status_code == 200
        node_headers = {"X-Mary-Node-Token": registered.json()["node_token"]}
        node = registered.json()["node"]
        assert node["node_id"] == "windows-pc"
        assert node["ownership"]["character_identity"] is False
        assert node["execution"]["authorized"] is False
        assert "api_key" not in node["capabilities"]["personal_search"]["metadata"]

        heartbeat = client.post(
            "/v1/nodes/heartbeat",
            headers=node_headers,
            json={"node_id": "windows-pc"},
        )
        assert heartbeat.status_code == 200
        assert heartbeat.json()["node"]["connected"] is True

        route = client.post(
            "/v1/nodes/route",
            headers=headers,
            json={"capability": "personal_search"},
        )
        assert route.status_code == 200
        assert route.json()["selected_node_id"] == "windows-pc"
        assert route.json()["execution"] == "not_authorized"

        preview = client.post(
            "/v1/nodes/task/preview",
            headers=headers,
            json={
                "capability": "personal_search",
                "intent": "Find the newest manuscript",
                "device_id": "iphone",
            },
        )
        assert preview.status_code == 200
        body = preview.json()
        assert body["plan"]["selected_node_id"] == "windows-pc"
        assert body["plan"]["execution_authorized"] is False
        assert body["plan"]["execution_endpoint"] is None
        assert body["execution"]["authorized"] is False

        routes = {route.path for route in app.routes}
        assert "/v1/nodes/task/execute" not in routes

        disconnected = client.post(
            "/v1/nodes/disconnect",
            headers=node_headers,
            json={"node_id": "windows-pc"},
        )
        assert disconnected.status_code == 200
        assert service.node_status()["connected"] == 0


def test_node_contract_rejects_unbounded_or_invalid_advertisements(monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "node-secret")
    app = create_app(MaryCoreService(FakeApplication(), instance_id="node-core"))
    headers = {"Authorization": "Bearer node-secret"}

    with TestClient(app) as client:
        bad = client.post(
            "/v1/nodes/register",
            headers=headers,
            json={
                "node_id": "windows pc with spaces",
                "capabilities": [{"name": "shell command"}],
            },
        )
        assert bad.status_code == 422
