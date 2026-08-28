"""Live low-latency Mary Core -> capability node -> Ollama round-trip check.

Uses the authenticated Mary Protocol task broker. It never calls Ollama directly
from this diagnostic and never prints Core tokens or other secrets.
"""
from __future__ import annotations

import argparse
import os
from time import monotonic, sleep

from dotenv import load_dotenv

from mary.protocol.client import MaryClient, MaryProtocolError


_ROLES = ("general", "conversation", "fast", "utility")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=_ROLES, default="general")
    parser.add_argument("--timeout", type=float, default=210.0)
    return parser


def main() -> int:
    args = _parser().parse_args()
    load_dotenv()
    core_url = str(os.getenv("MARY_CORE_URL", "")).strip().rstrip("/")
    token = str(os.getenv("MARY_CORE_TOKEN", "")).strip()

    print("MARYV2 WINDOWS OLLAMA NODE ROUND-TRIP")
    print("=" * 64)
    print(f"role:             {args.role}")
    print(f"MARY_CORE_URL:    {'CONFIGURED' if core_url else 'NOT CONFIGURED'}")
    print(f"MARY_CORE_TOKEN:  {'CONFIGURED' if token else 'NOT CONFIGURED'}")

    if not core_url or not token:
        print("result:           FAIL · Core URL/token is not configured")
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

    print("route check:      PASS")
    print(f"selected node:    {route.get('selected_node_id') or 'connected node'}")

    started = monotonic()
    try:
        dispatched = client.dispatch_capability_task(
            "llm.ollama",
            f"Verify low-latency Mary Core to Windows Ollama role {args.role}.",
            {
                "messages": [
                    {"role": "system", "content": "MaryV2 infrastructure diagnostic. Be concise."},
                    {"role": "user", "content": "Reply with exactly: MARY OLLAMA NODE OK"},
                ],
                "role": args.role,
                "temperature": 0.0,
                "max_tokens": 32,
            },
        )
    except (MaryProtocolError, OSError, ValueError) as exc:
        print(f"dispatch:         FAIL · {type(exc).__name__}: {exc}")
        return 5

    dispatch_ms = (monotonic() - started) * 1000.0
    task = dict(dispatched.get("task") or {})
    task_id = str(task.get("task_id") or "").strip()
    if not task_id:
        print("dispatch:         FAIL · Core returned no task id")
        return 5
    print("dispatch:         PASS")
    print(f"dispatch ms:      {dispatch_ms:.1f}")
    print(f"task id:          {task_id}")

    deadline = monotonic() + max(10.0, min(240.0, float(args.timeout)))
    last_status = "queued"
    first_claim_ms = None
    while monotonic() < deadline:
        try:
            current = client.capability_task_status(task_id)
        except (MaryProtocolError, OSError, ValueError) as exc:
            print(f"status:           FAIL · {type(exc).__name__}: {exc}")
            return 6

        task = dict(current.get("task") or {})
        status = str(task.get("status") or "").strip().lower()
        elapsed_ms = (monotonic() - started) * 1000.0
        if status in {"claimed", "completed"} and first_claim_ms is None:
            first_claim_ms = elapsed_ms
        if status and status != last_status:
            print(f"status:           {status} @ {elapsed_ms:.1f} ms")
            last_status = status

        if status == "completed":
            result = dict(task.get("result") or {})
            content = str(result.get("content") or "").strip()
            print("round trip:       PASS")
            print(f"claim observed:   {first_claim_ms:.1f} ms" if first_claim_ms is not None else "claim observed:   completed before sample")
            print(f"total ms:         {elapsed_ms:.1f}")
            print(f"provider:         {result.get('provider') or 'unknown'}")
            print(f"model:            {result.get('model') or 'unknown'}")
            print(f"response:         {content or '[empty]'}")
            print("secrets printed:  no")
            return 0 if content else 7

        if status in {"rejected", "failed", "expired"}:
            print(f"round trip:       FAIL · {status}")
            print(f"error:            {task.get('error') or 'no error detail returned'}")
            return 7

        sleep(0.2)

    print("round trip:       FAIL · timed out waiting for capability task")
    return 8


if __name__ == "__main__":
    raise SystemExit(main())
