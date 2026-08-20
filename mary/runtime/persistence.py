"""MaryV2 safe bounded persistence primitives.

Persistent state is valuable because it represents Mary's continuity.  V2 uses
atomic replacement plus a small rolling backup chain so a partial write or bad
shutdown does not turn one damaged JSON file into permanent data loss.

The helpers are intentionally generic and contain no Mary-specific semantics.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import uuid
from typing import Any


def backup_path(path: Path, generation: int) -> Path:
    return path.with_name(f"{path.name}.bak{int(generation)}")


def rotate_backups(path: str | Path, generations: int = 3) -> None:
    target = Path(path)
    generations = max(1, int(generations))

    oldest = backup_path(target, generations)
    try:
        oldest.unlink(missing_ok=True)
    except OSError:
        pass

    for generation in range(generations - 1, 0, -1):
        source = backup_path(target, generation)
        destination = backup_path(target, generation + 1)
        if not source.exists():
            continue
        try:
            os.replace(source, destination)
        except OSError:
            try:
                shutil.copy2(source, destination)
                source.unlink(missing_ok=True)
            except OSError:
                pass

    if target.exists():
        try:
            shutil.copy2(target, backup_path(target, 1))
        except OSError:
            # A backup failure must not prevent an otherwise safe atomic save.
            pass


def _fsync_directory(path: Path) -> None:
    """Best effort directory fsync on platforms that support it."""

    if os.name == "nt":
        return
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def atomic_write_json(
    path: str | Path,
    payload: Any,
    *,
    backup_generations: int = 3,
    indent: int = 2,
) -> bool:
    """Atomically save JSON and retain only a fixed number of backups."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(
        f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )

    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(
                payload,
                file,
                indent=indent,
                ensure_ascii=False,
                default=str,
            )
            file.flush()
            try:
                os.fsync(file.fileno())
            except OSError:
                pass

        if target.exists():
            rotate_backups(target, generations=backup_generations)

        os.replace(temporary, target)
        _fsync_directory(target.parent)
        return True

    except (OSError, TypeError, ValueError):
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def read_json(path: str | Path) -> Any | None:
    target = Path(path)
    if not target.exists():
        return None
    try:
        with target.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, UnicodeError):
        return None


def load_json_recovering(
    path: str | Path,
    *,
    backup_generations: int = 3,
    restore_primary: bool = False,
) -> tuple[Any | None, Path | None]:
    """Load primary JSON, falling back through a finite backup chain.

    Returns ``(payload, source_path)``.  If ``source_path`` differs from the
    requested primary path, recovery occurred.  Restoration is opt-in so merely
    inspecting state never overwrites the user's files.
    """

    target = Path(path)
    candidates = [target] + [
        backup_path(target, generation)
        for generation in range(1, max(1, int(backup_generations)) + 1)
    ]

    for candidate in candidates:
        payload = read_json(candidate)
        if payload is None:
            continue
        if restore_primary and candidate != target:
            atomic_write_json(
                target,
                payload,
                backup_generations=backup_generations,
            )
        return payload, candidate

    return None, None


def cleanup_stale_temps(path: str | Path) -> int:
    """Remove stale temp siblings left by interrupted atomic writes."""

    target = Path(path)
    if not target.parent.exists():
        return 0
    pattern = f".{target.name}.*.tmp"
    removed = 0
    for candidate in target.parent.glob(pattern):
        try:
            candidate.unlink()
            removed += 1
        except OSError:
            pass
    return removed
