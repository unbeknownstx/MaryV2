"""Portable recovery manifests and explicit safe snapshots for MaryV2."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any, Mapping

from mary.runtime.state_reconciliation import IGNORED_NAMES, IGNORED_PARTS


@dataclass(frozen=True)
class RecoveryFile:
    authority_root: str
    relative_path: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MaryRecovery:
    """Build/verify a recovery manifest without treating a cache as Mary."""

    VERSION = "1.0"
    MAX_FILES = 20000
    MAX_FILE_BYTES = 256 * 1024 * 1024

    @classmethod
    def manifest(cls, roots: Mapping[str, str | Path]) -> dict[str, Any]:
        files: list[RecoveryFile] = []
        unavailable: list[str] = []
        for root_name, raw in roots.items():
            root = Path(raw).expanduser().resolve()
            if not root.exists() or not root.is_dir():
                unavailable.append(str(root_name))
                continue
            for path in sorted(root.rglob("*")):
                if len(files) >= cls.MAX_FILES:
                    break
                if not path.is_file() or not cls._safe(path, root):
                    continue
                try:
                    size = path.stat().st_size
                    if size > cls.MAX_FILE_BYTES:
                        continue
                    digest = cls._hash(path)
                except OSError:
                    continue
                files.append(RecoveryFile(
                    authority_root=str(root_name),
                    relative_path=path.relative_to(root).as_posix(),
                    size=size,
                    sha256=digest,
                ))
        fingerprint = sha256(
            "\n".join(f"{x.authority_root}:{x.relative_path}:{x.sha256}" for x in files).encode("utf-8")
        ).hexdigest()
        return {
            "version": cls.VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "roots": {str(k): str(Path(v).expanduser()) for k, v in roots.items()},
            "unavailable_roots": unavailable,
            "files": [item.to_dict() for item in files],
            "file_count": len(files),
            "fingerprint": fingerprint,
            "policy": {
                "contains_secrets": False,
                "derived_indexes_required": False,
                "portable_identity_requires_repository_plus_authored_sources_plus_durable_state": True,
            },
        }

    @classmethod
    def create_snapshot(
        cls,
        roots: Mapping[str, str | Path],
        destination: str | Path,
        *,
        copy_files: bool = False,
    ) -> dict[str, Any]:
        """Write a recovery manifest and optionally copy its safe files.

        ``copy_files`` must be explicit.  This method never copies .env/secrets,
        caches, git internals, virtual environments, or node_modules.
        """
        manifest = cls.manifest(roots)
        destination = Path(destination).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        manifest_path = destination / "mary_recovery_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        copied = 0
        if copy_files:
            for item in manifest["files"]:
                source_root = Path(roots[item["authority_root"]]).expanduser().resolve()
                source = source_root / item["relative_path"]
                target = destination / "roots" / item["authority_root"] / item["relative_path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied += 1
        return {
            "manifest": str(manifest_path),
            "fingerprint": manifest["fingerprint"],
            "file_count": manifest["file_count"],
            "copied": copied,
            "copy_files": bool(copy_files),
        }

    @classmethod
    def verify(cls, manifest_path: str | Path, roots: Mapping[str, str | Path]) -> dict[str, Any]:
        expected = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        failures: list[str] = []
        checked = 0
        for item in expected.get("files", []):
            root_name = str(item.get("authority_root") or "")
            if root_name not in roots:
                failures.append(f"root unavailable: {root_name}")
                continue
            path = Path(roots[root_name]).expanduser().resolve() / str(item.get("relative_path") or "")
            if not path.is_file():
                failures.append(f"missing: {root_name}/{item.get('relative_path')}")
                continue
            checked += 1
            if cls._hash(path) != item.get("sha256"):
                failures.append(f"hash mismatch: {root_name}/{item.get('relative_path')}")
        return {"ok": not failures, "checked": checked, "failures": failures[:200]}

    @staticmethod
    def _safe(path: Path, root: Path) -> bool:
        relative = path.relative_to(root)
        name = path.name.lower()
        if name in IGNORED_NAMES or name.startswith(".env"):
            return False
        if any(part in IGNORED_PARTS for part in relative.parts):
            return False
        if name.endswith((".key", ".pem", ".p12", ".pfx")):
            return False
        return True

    @staticmethod
    def _hash(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
