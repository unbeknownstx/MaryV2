"""Read-only integrity check for MaryV2 persistent JSON state.

The checker never prints stored values. It validates JSON structure and reports
only relative file names/counts plus whether a valid finite backup exists for a
corrupt current file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from mary.core.config import PathConfig


def _load_json(path: Path) -> tuple[bool, str]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return False, exc.__class__.__name__
    if not isinstance(payload, (dict, list)):
        return False, "invalid_top_level_type"
    return True, "ok"


def inspect_state(data_root: Path, *, backup_generations: int = 5) -> dict[str, Any]:
    root = Path(data_root).expanduser().resolve()
    current_files = sorted(path for path in root.rglob("*.json") if path.is_file()) if root.exists() else []

    valid: list[str] = []
    invalid: list[dict[str, Any]] = []
    backup_files = 0

    for path in current_files:
        ok, reason = _load_json(path)
        relative = str(path.relative_to(root))
        if ok:
            valid.append(relative)
            continue

        recoverable = False
        valid_backup: str | None = None
        for generation in range(1, max(1, int(backup_generations)) + 1):
            backup = path.with_name(f"{path.name}.bak{generation}")
            if not backup.exists():
                continue
            backup_files += 1
            backup_ok, _ = _load_json(backup)
            if backup_ok and not recoverable:
                recoverable = True
                valid_backup = str(backup.relative_to(root))
        invalid.append(
            {
                "path": relative,
                "reason": reason,
                "recoverable": recoverable,
                "valid_backup": valid_backup,
            }
        )

    # Count backups for valid current files too, without opening them again.
    seen_backup_paths: set[Path] = set()
    if root.exists():
        for path in root.rglob("*.json.bak*"):
            if path.is_file():
                seen_backup_paths.add(path)
    backup_files = max(backup_files, len(seen_backup_paths))

    return {
        "data_root": root,
        "exists": root.exists(),
        "current_files": len(current_files),
        "valid_files": len(valid),
        "invalid_files": invalid,
        "backup_files": backup_files,
        "healthy": not invalid,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only MaryV2 state integrity check")
    parser.add_argument("--data-dir", type=Path, default=None, help="Override Mary's configured data directory")
    args = parser.parse_args(argv)

    data_root = args.data_dir or PathConfig().data
    report = inspect_state(data_root)

    print("=" * 72)
    print("MARYV2 PERSISTENT STATE INTEGRITY")
    print("=" * 72)
    print(f"Data root: {report['data_root']}")

    if not report["exists"]:
        print("PASS  No persistent data directory exists yet (fresh/private-state-free install).")
        print("=" * 72)
        return 0

    print(f"Current JSON files: {report['current_files']}")
    print(f"Valid JSON files:   {report['valid_files']}")
    print(f"Backup generations: {report['backup_files']}")

    invalid = report["invalid_files"]
    for item in invalid:
        status = "RECOVERABLE" if item["recoverable"] else "FAIL"
        detail = f"{item['path']} ({item['reason']})"
        if item["valid_backup"]:
            detail += f"; valid backup: {item['valid_backup']}"
        print(f"{status:11} {detail}")

    if invalid:
        print("State integrity FAILED: one or more current JSON files are invalid.")
        return 1

    print("PASS  All current persistent JSON files are structurally readable.")
    print("No stored values were displayed or modified.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
