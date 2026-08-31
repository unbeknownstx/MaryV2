from types import SimpleNamespace
from threading import Event, Thread
from time import sleep

import pytest

from mary.runtime.gateway import (
    LocalMaryGateway,
    RemoteMaryGateway,
    gateway_from_environment,
)


class FakeClient:
    def __init__(self):
        self.device_id = "iphone"
        self.actions = []
        self.surface_calls = []
        self.surface_active = False

    def state(self):
        return {"core": {"architecture": "13.2"}}

    def conversation_status(self):
        return {"engagement": {"mode": "adaptive"}}

    def workspace(self):
        return {"command": {"active": 1}}

    def workspace_action(self, action, args=None):
        self.actions.append((action, dict(args or {})))
        return {"ok": True}

    def runtime_action(self, action, args=None):
        self.actions.append((action, dict(args or {})))
        return {"ok": True}

    def surface_register(self, **payload):
        self.surface_calls.append(("register", dict(payload)))
        self.surface_active = True
        return {"state": "ACTIVE", "surface_id": payload["surface_id"]}

    def surface_renew(self, **payload):
        self.surface_calls.append(("renew", dict(payload)))
        if not self.surface_active:
            raise RuntimeError("lease missing")
        return {"state": "ACTIVE", "surface_id": payload["surface_id"]}

    def surface_wake(self, **payload):
        self.surface_calls.append(("wake", dict(payload)))
        if not self.surface_active:
            raise RuntimeError("Mary Core is sleeping")
        return {"state": "ACTIVE", "surface_id": payload["surface_id"]}

    def surface_disconnect(self, **payload):
        self.surface_calls.append(("disconnect", dict(payload)))
        self.surface_active = False
        return {"state": "SLEEPING", "surface_id": payload["surface_id"]}

    def turn(self, text, *, conversation_id=None, requested_mode=None, voice_input=False):
        self.surface_calls.append(("turn", {"text": text}))
        if not self.surface_active:
            raise RuntimeError("Mary Core is sleeping")
        return SimpleNamespace(
            response="hi",
            conversation_id=conversation_id,
            turn_id="turn-1",
            effective_mode=requested_mode or "adaptive",
            provenance={"provider": "fake"},
            state_changes={},
            conversation_state={"engagement": {"mode": requested_mode or "adaptive"}},
            display_hints={},
        )


def test_remote_gateway_uses_client_without_local_application():
    client = FakeClient()
    gateway = RemoteMaryGateway(client, surface="mobile")

    assert gateway.authority == "remote_mary_core"
    assert gateway.workspace()["command"]["active"] == 1
    assert gateway.workspace_action("focus.stop")["ok"] is True
    turn = gateway.turn("hello", conversation_id="creator-primary")
    assert turn.text == "hi"
    assert turn.conversation_id == "creator-primary"
    assert [name for name, _ in client.surface_calls[:3]] == [
        "register",
        "wake",
        "turn",
    ]
    surface_id = client.surface_calls[0][1]["surface_id"]
    assert 1 <= len(surface_id) <= 160
    assert client.surface_calls[1][1]["surface_id"] == surface_id

    gateway._renew_creator_surface()
    assert client.surface_calls[-1][0] == "renew"
    assert client.surface_calls[-1][1]["activity"] is False
    gateway.close()
    assert client.surface_calls[-1] == (
        "disconnect",
        {"surface_id": surface_id},
    )
    assert client.surface_active is False


def test_remote_gateway_close_waits_for_turn_then_disconnects_last():
    class BlockingClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.turn_started = Event()
            self.release_turn = Event()

        def turn(self, *args, **kwargs):
            self.surface_calls.append(("turn", {"text": args[0]}))
            self.turn_started.set()
            assert self.release_turn.wait(timeout=1)
            return SimpleNamespace(
                response="hi",
                conversation_id=kwargs["conversation_id"],
                turn_id="turn-1",
                effective_mode="adaptive",
                provenance={},
                state_changes={},
                conversation_state={},
                display_hints={},
            )

    client = BlockingClient()
    gateway = RemoteMaryGateway(client, surface="desktop")
    turn_thread = Thread(
        target=gateway.turn,
        args=("hello",),
        kwargs={"conversation_id": "creator-primary"},
    )
    close_thread = Thread(target=gateway.close)

    turn_thread.start()
    assert client.turn_started.wait(timeout=1)
    close_thread.start()
    sleep(0.02)
    assert close_thread.is_alive()
    assert all(name != "disconnect" for name, _ in client.surface_calls)

    client.release_turn.set()
    turn_thread.join(timeout=1)
    close_thread.join(timeout=1)
    assert not turn_thread.is_alive()
    assert not close_thread.is_alive()
    assert [name for name, _ in client.surface_calls][-2:] == [
        "turn",
        "disconnect",
    ]
    with pytest.raises(RuntimeError, match="closed"):
        gateway.turn("again", conversation_id="creator-primary")
    assert [name for name, _ in client.surface_calls][-1] == "disconnect"


def test_gateway_environment_refuses_ambiguous_remote_and_local(monkeypatch):
    monkeypatch.setenv("MARY_CORE_URL", "https://core.example")
    monkeypatch.setenv("MARY_CORE_TOKEN", "secret")

    with pytest.raises(RuntimeError, match="ambiguous authority"):
        gateway_from_environment(
            application=object(),
            device_id="pc",
            surface="desktop",
        )


def test_gateway_environment_never_implicitly_constructs_standalone(monkeypatch):
    monkeypatch.delenv("MARY_CORE_URL", raising=False)
    monkeypatch.delenv("MARY_CORE_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="will not create Mary implicitly"):
        gateway_from_environment(
            device_id="pc",
            surface="desktop",
        )


def test_node_only_gateway_requires_grant_and_suppresses_creator_token(monkeypatch):
    monkeypatch.setenv("MARY_CORE_URL", "https://core.example")
    monkeypatch.setenv("MARY_CORE_TOKEN", "creator-secret")
    monkeypatch.setenv("MARY_NODE_ENROLLMENT_GRANT", "node-grant")

    gateway = gateway_from_environment(
        device_id="pc",
        surface="windows_node",
        node_only=True,
    )
    assert gateway.client.token == ""
    assert gateway.client.enrollment_grant == "node-grant"
    assert gateway.creator_surface is False
