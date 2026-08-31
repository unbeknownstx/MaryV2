from __future__ import annotations

from pathlib import Path

import pytest

from mary.desktop.remote_application import RemoteMaryApplicationView
from mary.desktop import authority as desktop_authority
from mary.protocol.models import TurnResponse
from mary.runtime.gateway import RemoteMaryGateway


class FakeClient:
    def __init__(self):
        self.device_id = "windows-node"
        self.turns = []
        self.actions = []
        self.workspace_actions = []
        self.surface_calls = []

    def surface_register(self, **payload):
        self.surface_calls.append(("register", dict(payload)))
        return {"state": "ACTIVE", "surface_id": payload["surface_id"]}

    def surface_renew(self, **payload):
        self.surface_calls.append(("renew", dict(payload)))
        return {"state": "ACTIVE", "surface_id": payload["surface_id"]}

    def surface_wake(self, **payload):
        self.surface_calls.append(("wake", dict(payload)))
        return {"state": "ACTIVE", "surface_id": payload["surface_id"]}

    def surface_disconnect(self, **payload):
        self.surface_calls.append(("disconnect", dict(payload)))
        return {"state": "SLEEPING", "surface_id": payload["surface_id"]}

    def turn(self, text, *, conversation_id=None, requested_mode=None, voice_input=False):
        self.turns.append(
            {
                "text": text,
                "conversation_id": conversation_id,
                "requested_mode": requested_mode,
                "voice_input": voice_input,
            }
        )
        return TurnResponse(
            response="Remote Mary response",
            conversation_id=str(conversation_id or "creator-primary"),
            turn_id="turn-remote-1",
            effective_mode="adaptive",
            provenance={"provider": "fake", "model": "remote-test"},
            state_changes={},
            conversation_state={},
            display_hints={
                "delivery_plan": {"pace": "normal"},
                "emotion": {"primary": "curiosity", "intensity": 0.5},
                "realtime": {},
            },
        )

    def state(self):
        return {
            "mary": {
                "character": {"name": "Mary", "status": "idle"},
                "model": {"provider": "fake", "model": "remote-test"},
            },
            "runtime": {"turn_count": 1},
            "nodes": {"nodes": []},
            "mind": {"enabled": True},
            "retrieval": {"enabled": True},
            "perception": {"enabled": True},
        }

    def conversation_status(self):
        return {"engagement": {}, "dialogue": {}, "realtime": {"phase": "idle"}}

    def workspace(self):
        return {
            "command": {"items": []},
            "focus": {"active": False},
            "inbox": {"items": []},
            "study": {},
            "research": {},
            "presence": {},
            "semantics": {"authority": "canonical_workspace"},
        }

    def dashboard(self):
        return {
            "live": self.state()["mary"],
            "mind": {"enabled": True},
            "realtime": {"phase": "idle"},
            "nodes": {"nodes": []},
            "retrieval": {"enabled": True},
            "perception": {"enabled": True},
        }

    def workspace_action(self, action, args=None):
        self.workspace_actions.append((action, dict(args or {})))
        if action == "command.add":
            return {"ok": True, "item": {"id": "c1", "title": args["title"]}}
        return {"ok": True}

    def runtime_action(self, action, args=None):
        self.actions.append((action, dict(args or {})))
        if action == "mind.rebuild_reservoir":
            return {"ok": True, "records": 12, "status": {"enabled": True}}
        return {"phase": "idle"}


def test_remote_desktop_application_routes_turn_without_local_mary(tmp_path):
    gateway = RemoteMaryGateway(FakeClient(), surface="desktop")
    view = RemoteMaryApplicationView(
        gateway,
        project_root=tmp_path,
        conversation_id="creator-primary",
    )

    assert view.authority == "remote_mary_core"
    assert view.device_id == "windows-node"

    result = view.run(
        "hello",
        metadata={
            "surface": "desktop",
            "conversation_id": "creator-primary",
            "device_id": "windows-node",
        },
    )

    assert result.success is True
    assert result.output == "Remote Mary response"
    assert result.turn_id == "turn-remote-1"
    assert [name for name, _ in gateway.client.surface_calls[:3]] == [
        "register",
        "register",
        "wake",
    ]
    assert gateway.client.turns[0]["conversation_id"] == "creator-primary"
    assert view.mary.live_state()["character"]["name"] == "Mary"
    view.close()


def test_remote_desktop_workspace_routes_to_core(tmp_path):
    gateway = RemoteMaryGateway(FakeClient(), surface="desktop")
    view = RemoteMaryApplicationView(gateway, project_root=tmp_path)

    item = view.ecosystem.command.add("Ship Mary")

    assert item["title"] == "Ship Mary"
    assert gateway.client.workspace_actions[0][0] == "command.add"
    assert view.ecosystem.workspace_snapshot()["semantics"]["authority"] == "canonical_workspace"


def test_remote_desktop_close_does_not_close_core(tmp_path):
    gateway = RemoteMaryGateway(FakeClient(), surface="desktop")
    view = RemoteMaryApplicationView(gateway, project_root=tmp_path)

    assert view.close() is None
    assert gateway.client.actions == []
    assert [name for name, _ in gateway.client.surface_calls] == [
        "register",
        "disconnect",
    ]


def test_desktop_resolver_prefers_remote_core_without_constructing_local_mary(
    tmp_path,
    monkeypatch,
):
    gateway = RemoteMaryGateway(FakeClient(), surface="desktop")

    monkeypatch.setenv("MARY_CORE_URL", "https://mary.example")
    monkeypatch.setenv("MARY_CORE_TOKEN", "test-token")
    monkeypatch.setenv("MARY_NODE_ID", "windows-node")
    monkeypatch.setattr(
        desktop_authority,
        "gateway_from_environment",
        lambda **kwargs: gateway,
    )
    monkeypatch.setattr(
        desktop_authority,
        "create_application",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("remote Desktop must not create MaryApplication")
        ),
    )

    application, root = desktop_authority.resolve_desktop_application(project_root=tmp_path)

    assert isinstance(application, RemoteMaryApplicationView)
    assert application.authority == "remote_mary_core"
    assert root == tmp_path.resolve()


def test_desktop_resolver_rejects_ambiguous_local_plus_remote(monkeypatch):
    monkeypatch.setenv("MARY_CORE_URL", "https://mary.example")

    with pytest.raises(RuntimeError, match="two authorities"):
        desktop_authority.resolve_desktop_application(application=object())
