"""Create a private backup of MaryV2 persistent state.

The archive contains only files below Mary's configured data directory. It never
includes .env files or source code. The command is intentionally separate from
normal runtime so backups happen only when the user asks for one.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

from mary.core.config import PathConfig


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(
    data_root: Path,
    output_dir: Path,
    *,
    timestamp: datetime | None = None,
) -> Path | None:
    root = Path(data_root).expanduser().resolve()
    destination = Path(output_dir).expanduser().resolve()

    if not root.exists():
        return None
    if root == destination or root in destination.parents:
        raise ValueError("Backup output directory must be outside Mary's data directory.")

    files = [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and not path.name.startswith(".env")
    ]
    if not files:
        return None

    destination.mkdir(parents=True, exist_ok=True)
    moment = timestamp or datetime.now(timezone.utc)
    stamp = moment.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    archive = destination / f"MaryV2-state-{stamp}.zip"
    temporary = archive.with_suffix(".zip.tmp")

    manifest_files = []
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            resolved = path.resolve()
            if root not in resolved.parents:
                continue
            relative = path.relative_to(root)
            arcname = Path("data") / relative
            bundle.write(path, arcname.as_posix())
            manifest_files.append(
                {
                    "path": arcname.as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )

        manifest = {
            "format": "maryv2-state-backup-v1",
            "created_at_utc": moment.astimezone(timezone.utc).isoformat(),
            "file_count": len(manifest_files),
            "files": manifest_files,
            "contains_environment_secrets": False,
        }
        bundle.writestr(
            "MARYV2_STATE_BACKUP_MANIFEST.json",
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        )

    temporary.replace(archive)
    return archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Back up MaryV2 persistent state without .env secrets")
    parser.add_argument("--data-dir", type=Path, default=None, help="Override Mary's configured data directory")
    parser.add_argument("--output-dir", type=Path, default=None, help="Backup destination directory")
    args = parser.parse_args(argv)

    data_root = (args.data_dir or PathConfig().data).expanduser().resolve()
    output_dir = (args.output_dir or (data_root.parent / "backups")).expanduser().resolve()

    archive = create_backup(data_root, output_dir)
    if archive is None:
        print(f"No persistent state files found under {data_root}; nothing to back up.")
        return 0

    print("MaryV2 state backup created.")
    print(f"Archive: {archive}")
    print("Included: persistent data only")
    print("Excluded: .env/provider secrets and source code")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
