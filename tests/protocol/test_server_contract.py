import os

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from mary.core.service import MaryCoreService
from mary.protocol.server import create_app
from tests.protocol.test_core_service import FakeApplication


def test_http_contract_requires_creator_auth(monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "test-secret")
    app = create_app(MaryCoreService(FakeApplication(), instance_id="server-test"))
    with TestClient(app) as client:
        assert client.get("/v1/health").status_code == 200
        assert client.get("/v1/state").status_code == 401
        headers = {"Authorization": "Bearer test-secret"}
        assert client.get("/v1/state", headers=headers).status_code == 200
        assert client.get("/v1/creator-surfaces/status").status_code == 401
        registered = client.post(
            "/v1/creator-surfaces/register",
            headers=headers,
            json={
                "surface_id": "iphone",
                "visible": True,
                "foreground": True,
            },
        )
        assert registered.status_code == 200
        assert registered.json()["state"] == "ACTIVE"
        response = client.post(
            "/v1/turn",
            headers=headers,
            json={"text": "hello", "conversation_id": "c1", "device_id": "iphone"},
        )
        assert response.status_code == 200
        assert response.json()["response"] == "hi"
        assert response.json()["conversation_id"] == "c1"


def test_websocket_contract_first_frame_auth(monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "test-secret")
    app = create_app(MaryCoreService(FakeApplication(), instance_id="server-test"))
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer test-secret"}
        registered = client.post(
            "/v1/creator-surfaces/register",
            headers=headers,
            json={"surface_id": "iphone"},
        )
        assert registered.status_code == 200
        with client.websocket_connect("/v1/realtime") as websocket:
            websocket.send_json({"type": "auth", "token": "test-secret"})
            ready = websocket.receive_json()
            assert ready["type"] == "ready"
            websocket.send_json({
                "type": "turn",
                "payload": {"text": "hello", "conversation_id": "c1", "device_id": "iphone"},
            })
            completed = websocket.receive_json()
            assert completed["type"] == "turn.completed"
            assert completed["payload"]["response"] == "hi"
