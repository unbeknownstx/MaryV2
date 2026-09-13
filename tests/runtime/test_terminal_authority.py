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
        return {
            "core": {"ok": True, "service": "mary-core", "architecture": "13.3"},
            "mary": {
                "name": "Mary",
                "memory": {
                    "episodic": 0,
                    "semantic": 0,
                    "working": 0,
                },
                "continuity": {
                    "relationship_events": 8,
                    "durable_shared_work_events": 3,
                    "shared_work_authority": "relationship_history",
                    "current_work_authority": "derived_current_work_projection",
                },
                "current_work": {
                    "active": True,
                    "project": "MaryV2",
                    "recent": [
                        {"source": "relationship.shared_work"},
                        {"source": "relationship.milestone"},
                    ],
                    "sources": [
                        "relationship.shared_work",
                        "relationship.milestone",
                    ],
                    "authority": "derived_current_work_projection",
                    "persistence": "projection_only",
                },
            },
            "runtime": {
                "status": "created",
                "initialized": False,
                "running": False,
            },
            "creator_lifecycle": {
                "state": "ACTIVE",
                "surface_count": 1,
            },
            "mind": {
                "reservoir": {
                    "persistent": True,
                    "records": 33,
                    "fts5": True,
                },
            },
            "performance_hardening": {
                "deliberation_execution": {"version": "13.33"},
                "strategy_advisor": {"version": "13.33"},
            },
            "compute_fabric": {
                "routing": {
                    "strategy": "free_first",
                    "session_override": {"provider": None, "route": "private"},
                    "routes": {"private": ["ollama"]},
                },
                "capability_routes": {
                    "llm.ollama": {
                        "available": True,
                        "selected_node_id": "terminal-test",
                    },
                },
                "private_route_ready": True,
                "authority": "mary_core",
                "policy": "nodes compute; Core owns Mary state",
            },
        }

    def conversation(self):
        return {"realtime": {"phase": "idle"}}

    def dashboard(self):
        return {}

    def workspace(self):
        return {}

    def nodes(self):
        return {"nodes": []}

    def runtime_action(self, action, args=None):
        assert action == "llm.probe"
        return {
            "ok": True,
            "status": "ok",
            "provider": "ollama",
            "model": "qwen3:4b-instruct",
            "canonical_state_changed": False,
        }

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


def test_remote_contract_distinguishes_core_service_from_passive_application_runtime():
    gateway = _FakeRemoteGateway()

    rendered = terminal._remote_command(gateway, "/contract", None)

    assert rendered is not None
    assert '"core_available": true' in rendered
    assert '"deliberation_execution_version": "13.33"' in rendered
    assert '"strategy_advisor_version": "13.33"' in rendered
    assert '"status": "created"' in rendered
    assert "unified Core/service boundary version" in rendered


def test_remote_memory_status_reports_continuity_beyond_memorymanager_counts():
    gateway = _FakeRemoteGateway()

    rendered = terminal._remote_command(gateway, "/memory-status", None)

    assert rendered is not None
    assert '"canonical_memory_store"' in rendered
    assert '"recent_count": 2' in rendered
    assert '"durable_shared_work_events": 3' in rendered
    assert '"authority": "relationship_history"' in rendered
    assert '"records": 33' in rendered
    assert '"persistent": true' in rendered
    assert "only one continuity owner" in rendered


def test_remote_route_reports_core_routing_and_local_capability():
    gateway = _FakeRemoteGateway()

    rendered = terminal._remote_command(gateway, "/route", None)

    assert rendered is not None
    assert '"strategy": "free_first"' in rendered
    assert '"route": "private"' in rendered
    assert '"selected_node_id": "terminal-test"' in rendered
    assert '"private_route_ready": true' in rendered


def test_remote_probe_ollama_uses_non_mutating_core_diagnostic():
    gateway = _FakeRemoteGateway()

    rendered = terminal._remote_command(gateway, "/probe-ollama", None)

    assert rendered is not None
    assert '"provider": "ollama"' in rendered
    assert '"status": "ok"' in rendered
    assert '"canonical_state_changed": false' in rendered
