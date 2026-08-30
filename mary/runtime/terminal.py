"""Canonical MaryV2 terminal surface.

The terminal is a *surface*, never a state authority.  When ``MARY_CORE_URL``
is configured it talks to the canonical remote Mary Core and must not construct
a local ``MaryApplication``.  Explicit standalone development remains available
when no remote Core is configured.
"""
from __future__ import annotations

import json
import os
import socket
from typing import Any

from mary.runtime.application import create_application, run_interactive
from mary.runtime.gateway import MaryRuntimeGateway, RemoteMaryGateway, gateway_from_environment


def _pretty(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _remote_command(gateway: MaryRuntimeGateway, command: str, last: dict[str, Any] | None) -> str | None:
    """Render bounded remote-Core diagnostics without creating local Mary state."""

    state = gateway.state
    conversation = gateway.conversation
    dashboard = gateway.dashboard
    workspace = gateway.workspace

    if command in {"/help", "/h"}:
        return (
            "MARYV2 REMOTE TERMINAL COMMANDS\n"
            "/state /resources /memory-status /route /conversation /growth "
            "/realtime /nodes /retrieval /environment /contract /pending /last /dashboard /help"
        )
    if command == "/state":
        return _pretty(state().get("mary", {}))
    if command == "/resources":
        return _pretty(dict(state().get("mary", {}) or {}).get("resources", {}))
    if command == "/memory-status":
        return _pretty(dict(state().get("mary", {}) or {}).get("memory", {}))
    if command == "/route":
        return _pretty(dict(state().get("mary", {}) or {}).get("cognition", {}))
    if command == "/conversation":
        return _pretty(conversation())
    if command == "/growth":
        return _pretty(dict(dashboard() or {}).get("growth", {}))
    if command == "/realtime":
        return _pretty(dict(conversation() or {}).get("realtime", {}))
    if command == "/nodes":
        return _pretty(gateway.nodes())
    if command == "/retrieval":
        return _pretty(dict(dashboard() or {}).get("retrieval", {}))
    if command == "/environment":
        return _pretty(dict(state() or {}).get("environment", {}))
    if command == "/contract":
        payload = state()
        return _pretty({
            "authority": "remote_mary_core",
            "core": payload.get("core", {}),
            "runtime": payload.get("runtime", {}),
        })
    if command == "/pending":
        return _pretty(dict(workspace() or {}).get("command", {}))
    if command == "/last":
        return _pretty(last or {"status": "no completed remote turn yet"})
    if command == "/dashboard":
        return _pretty(dashboard())
    if command == "/audit":
        return "Remote Mary Core owns persistent state; this terminal performs no local state audit or mutation."
    return None


def run_remote_interactive(gateway: MaryRuntimeGateway) -> None:
    """Run terminal chat against canonical remote Mary Core."""

    conversation_id = os.getenv("MARY_CONVERSATION_ID", "creator-primary").strip() or "creator-primary"
    try:
        initial = gateway.state()
        core = dict(initial.get("core", {}) or {})
        mary = dict(initial.get("mary", {}) or {})
        print("=" * 64)
        print("MaryV2 — REMOTE CORE")
        print("=" * 64)
        print(f"Authority: remote_mary_core")
        print(f"Core:      {core.get('service', 'mary-core')} / {core.get('architecture', 'unknown')}")
        print(f"Mary:      {mary.get('name', 'Mary')}")
        print(f"Thread:    {conversation_id}")
        print("Type /help for bounded remote diagnostics, or exit to close this client.")
        print("=" * 64)
    except Exception as exc:
        print(f"Mary Core connection failed: {type(exc).__name__}: {exc}")
        return

    last: dict[str, Any] | None = None
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in {"exit", "quit"}:
            break
        if text.startswith("/"):
            rendered = _remote_command(gateway, text.lower(), last)
            print(rendered if rendered is not None else "Unknown remote command. Type /help.")
            continue
        try:
            response = gateway.turn(
                text,
                conversation_id=conversation_id,
                requested_mode=None,
                voice_input=False,
            )
            last = {
                "turn_id": response.turn_id,
                "effective_mode": response.effective_mode,
                "provenance": dict(response.provenance or {}),
            }
            print(f"Mary: {response.text}")
        except Exception as exc:
            print(f"[Mary Core Error] {type(exc).__name__}: {exc}")


def run_terminal() -> None:
    """Resolve one-Mary authority and launch the terminal surface."""

    if os.getenv("MARY_CORE_URL", "").strip():
        device_id = (
            os.getenv("MARY_DEVICE_ID", "").strip()
            or os.getenv("COMPUTERNAME", "").strip()
            or socket.gethostname().strip()
            or "terminal"
        )
        gateway = gateway_from_environment(
            application=None,
            device_id=device_id,
            surface="terminal",
        )
        if not isinstance(gateway, RemoteMaryGateway):
            raise RuntimeError("Terminal remote mode did not resolve remote Mary Core authority.")
        run_remote_interactive(gateway)
        return

    application = create_application(name="mary-terminal")
    run_interactive(application)
