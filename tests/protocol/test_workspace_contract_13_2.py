from types import SimpleNamespace

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from mary.core.service import MaryCoreService
from mary.ecosystem import MaryEcosystem
from mary.protocol.models import WorkspaceActionRequest
from mary.protocol.server import MAX_WORKSPACE_ACTION_BYTES, create_app


class FakeConfig:
    def __init__(self, tmp_path):
        self.paths = SimpleNamespace(
            data=tmp_path,
            workspace=tmp_path / "workspace",
            root=tmp_path,
        )


class FakePresenceAttention:
    def publish(self, *args, **kwargs):
        return None

    def snapshot(self):
        return {"events": []}


class FakeRealtime:
    def __init__(self):
        self.attention = FakePresenceAttention()

    def status(self):
        return {"phase": "idle"}


class FakeEngagement:
    def status(self):
        return {"mode": "adaptive", "last_plan": {}, "active_session": {}}


class FakeMemory:
    def status(self):
        return {"episodic": {"count": 0}}


class FakeGrowth:
    def status(self):
        return {"journal": {"records": 0}}


class FakeRelationship:
    def governance_status(self):
        return {"ok": True}


class FakeMary:
    def __init__(self, tmp_path):
        self.config = FakeConfig(tmp_path)
        self.realtime = FakeRealtime()
        self.engagement = FakeEngagement()
        self.memory = FakeMemory()
        self.growth = FakeGrowth()
        self.relationship = FakeRelationship()
        self.runtime_environment = SimpleNamespace(snapshot=lambda: {})
        self.node_registry = SimpleNamespace(snapshot=lambda: {"nodes": []})
        self.agency = SimpleNamespace(curiosities=SimpleNamespace(snapshot=lambda: {}))

    def live_state(self, runtime_status=None):
        return {"character": {"name": "Mary"}, "runtime_status": runtime_status}


class FakeApplication:
    def __init__(self, tmp_path):
        self.mary = FakeMary(tmp_path)
        self.ecosystem = MaryEcosystem(self.mary)
        self.state = SimpleNamespace(to_dict=lambda: {"status": "ready"})

    def save(self):
        return True

    def close(self):
        return True


def test_workspace_snapshot_excludes_device_local_capabilities(tmp_path):
    app = FakeApplication(tmp_path)
    snapshot = app.ecosystem.workspace_snapshot()

    assert snapshot["semantics"]["authority"] == "canonical_workspace"
    assert snapshot["semantics"]["device_local_capabilities_included"] is False
    assert "paths" not in snapshot
    assert "external" not in snapshot
    assert "foreground_window" not in snapshot.get("presence", {})
    assert [game["key"] for game in snapshot["arcade"]["games"]] == [
        "coin",
        "number",
        "prompt",
    ]


def test_workspace_action_request_rejects_device_local_operations():
    with pytest.raises(ValueError, match="Unsupported workspace action"):
        WorkspaceActionRequest.from_dict(
            {
                "action": "filesystem.search",
                "args": {"query": "secret"},
                "device_id": "pc",
            }
        )


@pytest.mark.parametrize(
    ("game", "payload"),
    [
        ("filesystem", ""),
        ("number", "11"),
        ("number", "private guess"),
        ("coin", "unexpected"),
        ("number", {"guess": 7}),
        (["number"], ""),
    ],
)
def test_workspace_action_request_rejects_unbounded_arcade_arguments(
    game,
    payload,
):
    with pytest.raises(ValueError):
        WorkspaceActionRequest.from_dict(
            {
                "action": "arcade.play",
                "args": {
                    "game": game,
                    "payload": payload,
                },
                "device_id": "iphone",
            }
        )


def test_core_workspace_action_updates_one_canonical_ecosystem(tmp_path):
    app = FakeApplication(tmp_path)
    core = MaryCoreService(app, instance_id="workspace-core")

    result = core.workspace_action(
        {
            "action": "command.add",
            "args": {"title": "Reconcile Mary", "kind": "project"},
            "device_id": "pc",
        }
    )

    assert result["ok"] is True
    assert result["item"]["title"] == "Reconcile Mary"
    assert result["workspace"]["command"]["projects"] == 1
    assert app.ecosystem.command.items[0].title == "Reconcile Mary"


def test_core_workspace_action_plays_arcade_inside_canonical_ecosystem(tmp_path):
    app = FakeApplication(tmp_path)
    core = MaryCoreService(app, instance_id="workspace-core")

    result = core.workspace_action(
        {
            "action": "arcade.play",
            "args": {"game": "coin", "payload": ""},
            "device_id": "iphone",
        }
    )

    assert result["ok"] is True
    assert result["game"] == "coin"
    assert result["result"] in {"Heads", "Tails"}
    assert len(result["workspace"]["arcade"]["games"]) == 3

    started = core.workspace_action(
        {
            "action": "arcade.play",
            "args": {"game": "number", "payload": ""},
            "device_id": "iphone",
        }
    )
    app.ecosystem.arcade._number = 7
    won = core.workspace_action(
        {
            "action": "arcade.play",
            "args": {"game": "number", "payload": "7"},
            "device_id": "iphone",
        }
    )

    assert started["state"] == "started"
    assert won["state"] == "won"
    assert app.ecosystem.arcade._number is None


def test_http_workspace_contract_is_authenticated_and_mutates_core(tmp_path, monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "test-secret")
    app = FakeApplication(tmp_path)
    api = create_app(MaryCoreService(app, instance_id="workspace-core"))
    headers = {"Authorization": "Bearer test-secret"}

    with TestClient(api) as client:
        assert client.get("/v1/workspace").status_code == 401
        workspace = client.get("/v1/workspace", headers=headers)
        assert workspace.status_code == 200
        assert workspace.json()["semantics"]["authority"] == "canonical_workspace"

        response = client.post(
            "/v1/workspace/action",
            headers=headers,
            json={
                "action": "focus.start",
                "args": {"minutes": 25, "task": "MaryV2"},
                "device_id": "windows-pc",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["focus"]["active"] is True
        assert payload["workspace"]["focus"]["task"] == "MaryV2"


def test_http_workspace_action_rejects_body_before_oversize_json_parsing(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("MARY_CORE_TOKEN", "test-secret")
    api = create_app(
        MaryCoreService(
            FakeApplication(tmp_path),
            instance_id="workspace-core",
        )
    )

    body = (
        '{"action":"arcade.play","args":{"game":"number","payload":"'
        + ("7" * MAX_WORKSPACE_ACTION_BYTES)
        + '"},"device_id":"iphone"}'
    )
    with TestClient(api) as client:
        response = client.post(
            "/v1/workspace/action",
            headers={
                "Authorization": "Bearer test-secret",
                "Content-Type": "application/json",
            },
            content=body,
        )

    assert response.status_code == 413
    assert response.json()["detail"] == "Request body too large."
