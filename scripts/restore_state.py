"""Safely restore a MaryV2 state backup created by scripts.backup_state.

Dry-run is the default. ``--apply`` restores only into a missing/empty target
data directory, validates every manifest hash, rejects path traversal, and
never restores environment-secret files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

from mary.core.config import PathConfig

MANIFEST_NAME = "MARYV2_STATE_BACKUP_MANIFEST.json"


def _safe_data_member(name: str) -> PurePosixPath | None:
    member = PurePosixPath(name)
    if member.is_absolute() or ".." in member.parts:
        return None
    if not member.parts or member.parts[0] != "data" or len(member.parts) < 2:
        return None
    if any(part.startswith(".env") for part in member.parts):
        return None
    return member


def inspect_backup(archive: Path) -> dict:
    path = Path(archive).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)

    with zipfile.ZipFile(path) as bundle:
        names = set(bundle.namelist())
        if MANIFEST_NAME not in names:
            raise ValueError("MaryV2 backup manifest is missing.")
        try:
            manifest = json.loads(bundle.read(MANIFEST_NAME).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError, KeyError) as exc:
            raise ValueError("MaryV2 backup manifest is invalid.") from exc

        if not isinstance(manifest, dict) or manifest.get("format") != "maryv2-state-backup-v1":
            raise ValueError("Unsupported MaryV2 state backup format.")
        records = manifest.get("files", [])
        if not isinstance(records, list):
            raise ValueError("MaryV2 backup file manifest is invalid.")

        validated: list[dict[str, str | int]] = []
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("MaryV2 backup contains an invalid file record.")
            name = str(record.get("path", ""))
            safe = _safe_data_member(name)
            if safe is None or name not in names:
                raise ValueError(f"Unsafe or missing backup member: {name!r}")
            payload = bundle.read(name)
            digest = hashlib.sha256(payload).hexdigest()
            expected = str(record.get("sha256", "")).strip().lower()
            if not expected or digest != expected:
                raise ValueError(f"Backup hash mismatch: {name}")
            expected_size = int(record.get("size", len(payload)))
            if len(payload) != expected_size:
                raise ValueError(f"Backup size mismatch: {name}")
            validated.append({"path": name, "size": len(payload), "sha256": digest})

        unexpected_data = [
            name for name in names
            if name.startswith("data/") and name != "data/"
            and name not in {str(item["path"]) for item in validated}
        ]
        if unexpected_data:
            raise ValueError("Backup contains unmanifested data files.")

    return {
        "archive": path,
        "created_at_utc": manifest.get("created_at_utc"),
        "files": validated,
        "file_count": len(validated),
    }


def restore_backup(archive: Path, data_root: Path, *, apply: bool = False) -> dict:
    report = inspect_backup(archive)
    target = Path(data_root).expanduser().resolve()

    existing_files = [path for path in target.rglob("*") if path.is_file()] if target.exists() else []
    if existing_files:
        raise FileExistsError(
            f"Target data directory is not empty: {target}. Move/back it up first; restore will not overwrite Mary state."
        )

    report["target"] = target
    report["applied"] = False
    if not apply:
        return report

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="maryv2_restore_", dir=str(target.parent)) as directory:
        staging = Path(directory) / "data"
        staging.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(report["archive"]) as bundle:
            for item in report["files"]:
                member = PurePosixPath(str(item["path"]))
                relative = Path(*member.parts[1:])
                destination = staging / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(str(item["path"]), "r") as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)
        if target.exists():
            try:
                target.rmdir()
            except OSError:
                pass
        staging.replace(target)

    report["applied"] = True
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate/restore a MaryV2 private-state backup")
    parser.add_argument("archive", type=Path, help="MaryV2-state-*.zip created by scripts.backup_state")
    parser.add_argument("--data-dir", type=Path, default=None, help="Restore target; defaults to Mary's configured data directory")
    parser.add_argument("--apply", action="store_true", help="Actually restore after validation")
    args = parser.parse_args(argv)

    target = args.data_dir or PathConfig().data
    try:
        report = restore_backup(args.archive, target, apply=args.apply)
    except (FileNotFoundError, FileExistsError, ValueError, zipfile.BadZipFile) as exc:
        print(f"FAIL  {exc}")
        return 1

    print("=" * 72)
    print("MARYV2 STATE RESTORE")
    print("=" * 72)
    print(f"Archive: {report['archive']}")
    print(f"Validated files: {report['file_count']}")
    print(f"Target data root: {report['target']}")
    if report["applied"]:
        print("PASS  State restored. No .env/provider secrets were restored.")
    else:
        print("DRY RUN ONLY - backup is valid. Add --apply to restore into the empty target.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
