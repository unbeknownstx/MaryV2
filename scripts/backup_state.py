"""Create an allowlisted private backup of MaryV2 durable state."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from mary.character.sourcebook import CharacterSourcebook
from mary.core.config import PathConfig
from mary.runtime.backup import create_backup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Back up MaryV2 persistent state without .env secrets")
    parser.add_argument("--data-dir", type=Path, default=None, help="Override Mary's configured data directory")
    parser.add_argument("--output-dir", type=Path, default=None, help="Backup destination directory")
    args = parser.parse_args(argv)

    data_root = (args.data_dir or PathConfig().data).expanduser().resolve()
    output_dir = (args.output_dir or (data_root.parent / "backups")).expanduser().resolve()

    sourcebook = CharacterSourcebook.from_environment(root=PathConfig().root)
    archive = create_backup(data_root, output_dir, sourcebook=sourcebook)
    if archive is None:
        print(f"No persistent state files found under {data_root}; nothing to back up.")
        return 0

    print("MaryV2 state backup created.")
    print(f"Archive: {archive}")
    print("Included: explicitly registered canonical durable state only")
    print("Excluded: secrets, sessions, leases, queues, traces, and rebuildable state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
