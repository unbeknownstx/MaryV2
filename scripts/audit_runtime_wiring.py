"""Audit MaryV2 runtime wiring without executing external capabilities.

With MARY_CORE_URL set, this reads the authenticated live Core state and reports
its executable wiring audit. Without a Core URL it builds an isolated ephemeral
Core composition so the repository can self-audit without touching creator
state.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile


def _remote() -> dict:
    from mary.protocol.client import MaryClient

    url = os.getenv("MARY_CORE_URL", "").strip()
    token = os.getenv("MARY_CORE_TOKEN", "").strip()
    if not url:
        raise RuntimeError("MARY_CORE_URL is not configured.")
    if not token:
        raise RuntimeError("MARY_CORE_TOKEN is required for the live Core audit.")
    client = MaryClient(
        url,
        token=token,
        device_id="runtime-wiring-audit",
        surface="diagnostic",
        timeout=12.0,
    )
    state = client.state()
    return dict(state.get("integration", {}) or {})


def _ephemeral() -> dict:
    # Set the writable root before importing Mary's composition modules. The
    # audit may create normal empty state directories, but they live only inside
    # this temporary directory and are removed on exit.
    with tempfile.TemporaryDirectory(prefix="maryv2-wiring-") as directory:
        os.environ["MARY_DATA_DIR"] = str(Path(directory) / "data")
        os.environ["MARY_WORKSPACE_ROOT"] = str(Path(directory) / "workspace")

        from mary.core.service import MaryCoreService
        from mary.runtime.application import create_application

        app = create_application(
            memory_path=Path(directory) / "memory" / "memory.json",
            developed_self_path=Path(directory) / "personality" / "developed_self.json",
            preference_promotion_path=Path(directory) / "personality" / "preferences.json",
            knowledge_path=Path(directory) / "knowledge" / "knowledge.json",
            auto_save=False,
            load_memory=False,
            load_developed_self=False,
            load_preference_promotion=False,
            load_knowledge=False,
            name="wiring-audit",
        )
        service = MaryCoreService(app, instance_id="wiring-audit-core")
        try:
            return service.integration_status()
        finally:
            app.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-operational",
        action="store_true",
        help="Fail when no live conversation provider is currently available.",
    )
    args = parser.parse_args()

    live = bool(os.getenv("MARY_CORE_URL", "").strip())
    report = _remote() if live else _ephemeral()
    runtime = dict(report.get("runtime", {}) or {})
    payload = {
        "source": "live_remote_core" if live else "ephemeral_repository_boot",
        "healthy": bool(report.get("healthy")),
        "operational": bool(report.get("operational", runtime.get("operational"))),
        "required_failures": list(runtime.get("required_failures", []) or []),
        "degraded": list(runtime.get("degraded", []) or []),
        "runtime": runtime,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    if not payload["healthy"]:
        return 1
    if args.require_operational and not payload["operational"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
