"""Read-only reconciliation planning for MaryV2 state roots.

Mary accumulated legitimate local/cloud development state during the migration to
13.x.  This module compares candidate roots without deciding that newest wins,
without copying files, and without mutating any Mary state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping


SAFE_SUFFIXES = {".json", ".jsonl", ".db", ".sqlite", ".sqlite3", ".md", ".txt"}
IGNORED_NAMES = {".env", "secrets.json", "credentials.json", "token.json", "tokens.json"}
IGNORED_PARTS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "cache", "caches"}


@dataclass(frozen=True)
class StateFileFingerprint:
    root_name: str
    relative_path: str
    size: int
    modified_ns: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StateReconciliationItem:
    relative_path: str
    classification: str
    copies: tuple[StateFileFingerprint, ...]
    recommended_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "classification": self.classification,
            "copies": [item.to_dict() for item in self.copies],
            "recommended_action": self.recommended_action,
        }


class StateReconciler:
    VERSION = "1.0"
    MAX_FILES_PER_ROOT = 8000
    MAX_HASH_BYTES = 64 * 1024 * 1024

    @classmethod
    def inventory(cls, roots: Mapping[str, str | Path]) -> dict[str, list[StateFileFingerprint]]:
        result: dict[str, list[StateFileFingerprint]] = {}
        for name, raw_root in roots.items():
            root = Path(raw_root).expanduser().resolve()
            rows: list[StateFileFingerprint] = []
            if not root.exists() or not root.is_dir():
                result[str(name)] = rows
                continue
            for path in sorted(root.rglob("*")):
                if len(rows) >= cls.MAX_FILES_PER_ROOT:
                    break
                if not path.is_file() or not cls._safe(path, root):
                    continue
                try:
                    stat = path.stat()
                    digest = cls._hash(path, stat.st_size)
                except OSError:
                    continue
                rows.append(StateFileFingerprint(
                    root_name=str(name),
                    relative_path=path.relative_to(root).as_posix(),
                    size=int(stat.st_size),
                    modified_ns=int(stat.st_mtime_ns),
                    sha256=digest,
                ))
            result[str(name)] = rows
        return result

    @classmethod
    def plan(cls, roots: Mapping[str, str | Path]) -> dict[str, Any]:
        inventory = cls.inventory(roots)
        grouped: dict[str, list[StateFileFingerprint]] = {}
        for rows in inventory.values():
            for item in rows:
                grouped.setdefault(item.relative_path, []).append(item)

        items: list[StateReconciliationItem] = []
        root_count = len(roots)
        for relative_path in sorted(grouped):
            copies = tuple(sorted(grouped[relative_path], key=lambda x: x.root_name))
            hashes = {item.sha256 for item in copies}
            if len(copies) == root_count and len(hashes) == 1:
                classification = "identical"
                action = "keep one canonical copy; retain other copies as recovery redundancy if desired"
            elif len(copies) > 1 and len(hashes) == 1:
                classification = "identical_partial"
                action = "same content exists in multiple roots; determine why other roots omit it"
            elif len(copies) > 1:
                classification = "conflict"
                action = "manual semantic reconciliation required; do not choose by timestamp alone"
            else:
                classification = "unique_candidate"
                action = "inspect provenance and owner before promoting, archiving, or discarding"
            items.append(StateReconciliationItem(relative_path, classification, copies, action))

        counts: dict[str, int] = {}
        for item in items:
            counts[item.classification] = counts.get(item.classification, 0) + 1
        return {
            "version": cls.VERSION,
            "read_only": True,
            "roots": {str(k): str(Path(v).expanduser()) for k, v in roots.items()},
            "inventory_counts": {name: len(rows) for name, rows in inventory.items()},
            "classifications": counts,
            "items": [item.to_dict() for item in items],
            "policy": [
                "No file is merged, copied, deleted, or promoted by this planner.",
                "Timestamp alone never establishes canonical Mary state.",
                "State ownership/provenance must be resolved before promotion.",
                "Test/probe residue should be classified separately from creator-grounded continuity.",
            ],
        }

    @staticmethod
    def _safe(path: Path, root: Path) -> bool:
        relative = path.relative_to(root)
        if path.name.lower() in IGNORED_NAMES or path.name.lower().startswith(".env"):
            return False
        if any(part in IGNORED_PARTS for part in relative.parts):
            return False
        return path.suffix.lower() in SAFE_SUFFIXES

    @classmethod
    def _hash(cls, path: Path, size: int) -> str:
        if size > cls.MAX_HASH_BYTES:
            return f"large:{size}"
        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
