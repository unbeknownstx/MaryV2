"""Preview or explicitly merge older local Mary continuity into canonical Core.

Default behavior is read-only. The command:
1. selects an explicit/bounded local continuity root;
2. sends only MemoryManager + RelationshipManager durable state to authenticated
   Mary Core;
3. receives a content-free deterministic merge plan.

Mutation requires BOTH --apply and the exact confirmation string. Core also
requires the preview fingerprint to remain current and creates a protected
durable backup before changing canonical state.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from mary.core.config import PathConfig
from mary.desktop.continuity_recovery import (
    best_continuity_candidate,
    load_continuity_payload,
)
from mary.protocol.client import MaryClient, MaryProtocolError
from mary.runtime.continuity_recovery import (
    normalize_recovery_payload,
    source_counts,
)


CONFIRMATION = "MERGE_LOCAL_CONTINUITY"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely preview/merge older local Mary continuity into Core."
    )
    parser.add_argument(
        "--root",
        help="Explicit older Mary data root. Defaults to the highest-record bounded candidate.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the reviewed merge after Core creates a protected backup.",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Required with --apply: {CONFIRMATION}",
    )
    return parser


def _client() -> MaryClient:
    core_url = os.getenv("MARY_CORE_URL", "").strip()
    core_token = os.getenv("MARY_CORE_TOKEN", "").strip()
    if not core_url or not core_token:
        raise RuntimeError(
            "MARY_CORE_URL and MARY_CORE_TOKEN must be configured in this shell/.env."
        )
    return MaryClient(
        core_url,
        token=core_token,
        device_id="continuity-recovery-cli",
        surface="recovery_cli",
        timeout=120.0,
    )


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    project_root = PathConfig().root

    if args.root:
        source_root = Path(args.root).expanduser().resolve()
    else:
        source_root = best_continuity_candidate(project_root)
        if source_root is None:
            print("No recoverable bounded local continuity candidate was found.")
            return 2

    try:
        continuity = normalize_recovery_payload(
            load_continuity_payload(source_root)
        )
        client = _client()
        preview = client.preview_continuity_recovery(continuity)
    except (FileNotFoundError, RuntimeError, ValueError, MaryProtocolError) as exc:
        print(f"Recovery preview failed safely: {type(exc).__name__}: {exc}")
        return 2

    report = {
        "source_root": str(source_root),
        "local_source_counts": source_counts(continuity),
        "core_instance_id": preview.get("core_instance_id"),
        "expected_durable_state_fingerprint": preview.get(
            "expected_durable_state_fingerprint"
        ),
        "backup_ready": bool(preview.get("backup_ready")),
        "plan": preview.get("plan", {}),
        "mutated": False,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if not args.apply:
        print(
            "\nPREVIEW ONLY — no state changed. "
            f"To apply this exact policy, rerun with --apply --confirm {CONFIRMATION}"
        )
        return 0

    if args.confirm != CONFIRMATION:
        print(
            "\nApply refused: exact confirmation is required: "
            f"--confirm {CONFIRMATION}"
        )
        return 3

    if not bool(preview.get("backup_ready")):
        print(
            "\nApply refused: canonical Core has no protected backup location. "
            "Configure MARY_BACKUP_DIR on Core, let it redeploy, then preview again."
        )
        return 4

    expected = str(
        preview.get("expected_durable_state_fingerprint") or ""
    ).strip()
    try:
        result = client.apply_continuity_recovery(
            continuity,
            expected_fingerprint=expected,
            confirmation=CONFIRMATION,
        )
    except (RuntimeError, ValueError, MaryProtocolError) as exc:
        print(f"\nRecovery apply failed safely: {type(exc).__name__}: {exc}")
        print("The old local source was not modified.")
        return 5

    public = {
        "ok": bool(result.get("ok")),
        "mutated": bool(result.get("mutated")),
        "core_instance_id": result.get("core_instance_id"),
        "merge": result.get("merge", {}),
        "backup": result.get("backup", {}),
        "before_durable_state_fingerprint": result.get(
            "before_durable_state_fingerprint"
        ),
        "after_durable_state_fingerprint": result.get(
            "after_durable_state_fingerprint"
        ),
        "local_source_modified": False,
    }
    print("\nRECOVERY APPLIED")
    print(json.dumps(public, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
