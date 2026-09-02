"""Issue and consume a one-time durable capability-node enrollment grant.

This is the cross-platform creator-side helper for Mac/Linux capability nodes.
It intentionally keeps the raw enrollment grant process-local, never prints it,
and does not pass the creator Core token into the node-only child process.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


def _node_id() -> str:
    return (
        os.getenv("MARY_NODE_ID", "").strip()
        or os.getenv("COMPUTERNAME", "").strip()
        or socket.gethostname().strip()
        or "mary-capability-node"
    )


def _issue_grant(*, core_url: str, creator_token: str, node_id: str) -> str:
    payload = json.dumps(
        {
            "node_id": node_id,
            "expires_in_seconds": 300,
            "max_uses": 1,
        }
    ).encode("utf-8")
    request = Request(
        core_url.rstrip("/") + "/v1/nodes/enrollment-grants",
        data=payload,
        headers={
            "Authorization": f"Bearer {creator_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        result = json.loads(response.read().decode("utf-8"))
    grant = str(result.get("enrollment_grant") or "").strip()
    if not grant:
        raise RuntimeError("Core did not return an enrollment grant.")
    return grant


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Securely enroll this machine as a durable Mary capability node."
    )
    parser.parse_args(argv)

    load_dotenv(".env")
    core_url = os.getenv("MARY_CORE_URL", "").strip()
    creator_token = os.getenv("MARY_CORE_TOKEN", "").strip()
    if not core_url:
        print("MARY_CORE_URL is not configured.")
        return 2
    if not creator_token:
        print("MARY_CORE_TOKEN is not configured for creator-authorized enrollment.")
        return 2

    node_id = _node_id()
    print("=== MARY CAPABILITY NODE ENROLLMENT ===")
    print(f"Core: {core_url}")
    print(f"Node ID: {node_id}")

    try:
        grant = _issue_grant(
            core_url=core_url,
            creator_token=creator_token,
            node_id=node_id,
        )
    except HTTPError as exc:
        print(f"Could not issue enrollment grant: HTTP {exc.code}")
        return 1
    except URLError:
        print("Could not reach Mary Core.")
        return 1
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc))
        return 1

    print("One-time enrollment grant issued securely (not displayed).")
    child_env = os.environ.copy()
    # Keep an explicit empty value so the child process cannot reload the
    # creator token from .env via python-dotenv. Node-only authority receives
    # only the one-time grant (and later its own durable credential).
    child_env["MARY_CORE_TOKEN"] = ""
    child_env["MARY_NODE_ENROLLMENT_GRANT"] = grant
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "scripts.run_capability_node", "--enroll-only"],
            env=child_env,
            check=False,
        )
        return int(completed.returncode)
    finally:
        child_env.pop("MARY_NODE_ENROLLMENT_GRANT", None)
        grant = ""


if __name__ == "__main__":
    raise SystemExit(main())
