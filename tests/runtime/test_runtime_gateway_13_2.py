from types import SimpleNamespace

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

    def turn(self, text, *, conversation_id=None, requested_mode=None, voice_input=False):
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
