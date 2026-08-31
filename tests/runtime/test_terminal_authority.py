from __future__ import annotations

from types import SimpleNamespace

import mary.runtime.terminal as terminal
from mary.runtime.gateway import RemoteMaryGateway


class _FakeClient:
    device_id = "terminal-test"


class _FakeRemoteGateway(RemoteMaryGateway):
    def __init__(self):
        self.device_id = "terminal-test"
        self.surface = "terminal"
        self.client = _FakeClient()
        self.connect_count = 0
        self.close_count = 0

    def state(self):
        return {"core": {"service": "mary-core", "architecture": "13.2"}, "mary": {"name": "Mary"}}

    def conversation(self):
        return {"realtime": {"phase": "idle"}}

    def dashboard(self):
        return {}

    def workspace(self):
        return {}

    def nodes(self):
        return {"nodes": []}

    def turn(self, text, *, conversation_id, requested_mode=None, voice_input=False):
        return SimpleNamespace(
            text="remote reply",
            turn_id="turn-1",
            effective_mode="adaptive",
            provenance={"authority": "remote_mary_core"},
        )

    def connect_surface(self):
        self.connect_count += 1
        return {"state": "ACTIVE", "surface_id": "terminal-test-surface"}

    def close(self):
        self.close_count += 1


def test_terminal_remote_core_never_constructs_local_mary(monkeypatch):
    gateway = _FakeRemoteGateway()
    monkeypatch.setenv("MARY_CORE_URL", "https://core.example")
    monkeypatch.setenv("MARY_CORE_TOKEN", "token")
    monkeypatch.setattr(terminal, "gateway_from_environment", lambda **_: gateway)
    monkeypatch.setattr(
        terminal,
        "create_application",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not construct local Mary")),
    )
    seen = {}
    monkeypatch.setattr(terminal, "run_remote_interactive", lambda value: seen.setdefault("gateway", value))

    terminal.run_terminal()

    assert seen["gateway"] is gateway


def test_terminal_standalone_constructs_one_local_application_when_core_absent(monkeypatch):
    monkeypatch.delenv("MARY_CORE_URL", raising=False)
    app = object()
    monkeypatch.setattr(terminal, "create_application", lambda **_: app)
    seen = {}
    monkeypatch.setattr(terminal, "run_interactive", lambda value: seen.setdefault("application", value))

    terminal.run_terminal()

    assert seen["application"] is app


def test_terminal_remote_session_connects_and_disconnects_surface(monkeypatch):
    gateway = _FakeRemoteGateway()
    monkeypatch.setattr("builtins.input", lambda _prompt: "exit")

    terminal.run_remote_interactive(gateway)

    assert gateway.connect_count == 1
    assert gateway.close_count == 1
