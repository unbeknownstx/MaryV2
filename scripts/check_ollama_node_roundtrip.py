"""Live Mary Core -> Windows capability node -> Ollama round-trip check.

This diagnostic uses the existing authenticated Mary Protocol task broker.  It
never calls Ollama directly from the diagnostic process and never prints Core
tokens or other secrets.
"""
from __future__ import annotations

import os
from time import monotonic, sleep

from dotenv import load_dotenv

from mary.protocol.client import MaryClient, MaryProtocolError


def main() -> int:
    load_dotenv()
    core_url = str(os.getenv("MARY_CORE_URL", "")).strip().rstrip("/")
    token = str(os.getenv("MARY_CORE_TOKEN", "")).strip()

    print("MARYV2 WINDOWS OLLAMA NODE ROUND-TRIP")
    print("=" * 64)
    print(f"MARY_CORE_URL:    {'CONFIGURED' if core_url else 'NOT CONFIGURED'}")
    print(f"MARY_CORE_TOKEN:  {'CONFIGURED' if token else 'NOT CONFIGURED'}")

    if not core_url:
        print("result:           FAIL · MARY_CORE_URL is not configured")
        return 2
    if not token:
        print("result:           FAIL · MARY_CORE_TOKEN is not configured")
        return 2

    client = MaryClient(
        core_url,
        token=token,
        device_id="windows-ollama-roundtrip-check",
        surface="diagnostic",
        timeout=8.0,
    )

    try:
        route = client.route_capability("llm.ollama")
    except (MaryProtocolError, OSError, ValueError) as exc:
        print(f"route check:      FAIL · {type(exc).__name__}: {exc}")
        return 3

    if not bool(route.get("available")):
        print("route check:      FAIL · no connected llm.ollama capability node")
        return 4

    selected = dict(route.get("selected") or route.get("node") or {})
    selected_node_id = (
        selected.get("display_name")
        or selected.get("node_id")
        or route.get("selected_node_id")
        or "connected Windows node"
    )
    print("route check:      PASS")
    print(f"selected node:    {selected_node_id}")

    try:
        dispatched = client.dispatch_capability_task(
            "llm.ollama",
            "Verify one bounded Mary Core to Windows Ollama capability round trip.",
            {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are responding to a MaryV2 infrastructure diagnostic. Be concise.",
                    },
                    {
                        "role": "user",
                        "content": "Reply with exactly: MARY OLLAMA NODE OK",
                    },
                ],
                "temperature": 0.0,
                "max_tokens": 32,
            },
        )
    except (MaryProtocolError, OSError, ValueError) as exc:
        print(f"dispatch:         FAIL · {type(exc).__name__}: {exc}")
        return 5

    task = dict(dispatched.get("task") or {})
    task_id = str(task.get("task_id") or "").strip()
    if not task_id:
        print("dispatch:         FAIL · Core returned no task id")
        return 5

    print("dispatch:         PASS")
    print(f"task id:          {task_id}")
    print("waiting:          desktop node poll + local Ollama generation")

    deadline = monotonic() + 90.0
    last_status = "queued"
    while monotonic() < deadline:
        try:
            current = client.capability_task_status(task_id)
        except (MaryProtocolError, OSError, ValueError) as exc:
            print(f"status:           FAIL · {type(exc).__name__}: {exc}")
            return 6

        task = dict(current.get("task") or {})
        status = str(task.get("status") or "").strip().lower()
        if status and status != last_status:
            print(f"status:           {status}")
            last_status = status

        if status == "completed":
            result = dict(task.get("result") or {})
            content = str(result.get("content") or "").strip()
            print("round trip:       PASS")
            print(f"provider:         {result.get('provider') or 'unknown'}")
            print(f"model:            {result.get('model') or 'unknown'}")
            print(f"response:         {content or '[empty]'}")
            print(f"privacy:          {result.get('privacy') or 'bounded device result'}")
            print("secrets printed:  no")
            return 0 if content else 7

        if status in {"rejected", "failed", "expired"}:
            print(f"round trip:       FAIL · {status}")
            print(f"error:            {task.get('error') or 'no error detail returned'}")
            return 7

        sleep(1.0)

    print("round trip:       FAIL · timed out waiting for capability task")
    print("hint:             keep Mary Desktop running so its node agent can poll Core")
    return 8


if __name__ == "__main__":
    raise SystemExit(main())
