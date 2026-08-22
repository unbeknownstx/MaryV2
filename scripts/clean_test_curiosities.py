"""Safely remove only pytest-origin curiosity records.

Default behavior is read-only. Pass ``--apply`` to perform the cleanup.
The command never prints curiosity descriptions or other private contents.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from mary.core.config import PathConfig
from mary.runtime.persistence import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    path = PathConfig().goals / "curiosities.json"
    if not path.exists():
        print(f"No curiosity file found at {path}")
        return 0

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        raw = payload.get("curiosities", [])
        items = raw if isinstance(raw, list) else []
    elif isinstance(payload, list):
        items = payload
        payload = {"curiosities": items}
    else:
        raise ValueError("curiosity file must contain a JSON object or list")

    records = [item for item in items if isinstance(item, dict)]
    kept = [
        item for item in records
        if str(item.get("source", "")).strip().lower() != "test"
    ]
    removed = len(records) - len(kept)

    print(f"Curiosity file: {path}")
    print(f"Test-origin records found: {removed}")
    print(f"Non-test records preserved: {len(kept)}")

    if not args.apply:
        print("DRY RUN ONLY - add --apply to remove only source='test' records.")
        return 0

    if removed == 0:
        print("Nothing to remove.")
        return 0

    backup = path.with_name(path.name + ".before_test_cleanup.bak")
    if not backup.exists():
        shutil.copy2(path, backup)
        print(f"Backup created: {backup}")

    payload["curiosities"] = kept
    atomic_write_json(path, payload, backup_generations=3, indent=2)
    print(f"Removed {removed} test-origin curiosity records.")
    print(f"Preserved {len(kept)} non-test curiosity records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
