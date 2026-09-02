"""Reviewed optional model/adapter candidate catalog.

The catalog is source metadata only. It never downloads weights, loads a model,
or grants a candidate any authority over Mary.  Its purpose is to make internet
experimentation reproducible: exact artifact, exact compatible base, license,
and hash where available.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelCandidate:
    candidate_id: str
    kind: str
    runtime: str
    repository: str
    filename: str
    sha256: str = ""
    license: str = "unknown"
    required_base: str | None = None
    roles: tuple[str, ...] = ()
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.candidate_id,
            "kind": self.kind,
            "runtime": self.runtime,
            "repository": self.repository,
            "filename": self.filename,
            "sha256": self.sha256,
            "license": self.license,
            "required_base": self.required_base,
            "roles": list(self.roles),
            "notes": self.notes[:500],
            "metadata": dict(self.metadata),
        }


class ModelCandidateCatalog:
    VERSION = "1"

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self.candidates: dict[str, ModelCandidate] = {}
        self.error: str | None = None
        if self.path is not None:
            self.load()

    def load(self) -> int:
        self.candidates.clear()
        self.error = None
        if self.path is None or not self.path.exists():
            return 0
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - status should degrade, not fail Mary boot
            self.error = f"{type(exc).__name__}: invalid candidate catalog"
            return 0
        for raw in list(payload.get("candidates") or [])[:100]:
            if not isinstance(raw, dict):
                continue
            candidate_id = str(raw.get("id") or "").strip()
            repository = str(raw.get("repository") or "").strip()
            filename = str(raw.get("filename") or "").strip()
            if not candidate_id or not repository or not filename:
                continue
            known = {
                "id", "kind", "runtime", "repository", "filename", "sha256",
                "license", "required_base", "role", "notes",
            }
            metadata = {str(k): v for k, v in raw.items() if k not in known}
            self.candidates[candidate_id] = ModelCandidate(
                candidate_id=candidate_id,
                kind=str(raw.get("kind") or "unknown")[:80],
                runtime=str(raw.get("runtime") or "unknown")[:80],
                repository=repository[:300],
                filename=filename[:300],
                sha256=str(raw.get("sha256") or "").strip().lower()[:128],
                license=str(raw.get("license") or "unknown")[:120],
                required_base=(str(raw.get("required_base"))[:300] if raw.get("required_base") else None),
                roles=tuple(str(item)[:100] for item in list(raw.get("role") or [])[:20]),
                notes=str(raw.get("notes") or "")[:1000],
                metadata=metadata,
            )
        return len(self.candidates)

    def get(self, candidate_id: str) -> ModelCandidate | None:
        return self.candidates.get(str(candidate_id or "").strip())

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "path_present": bool(self.path and self.path.exists()),
            "count": len(self.candidates),
            "candidates": [item.to_dict() for item in self.candidates.values()],
            "error": self.error,
            "policy": "reviewed optional assets only; no automatic download/load/authority",
        }
