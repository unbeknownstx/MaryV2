"""Persistence adapter for Mary's evaluated learning and long-term knowledge.

The knowledge models intentionally remain storage-agnostic. This adapter owns
only serialization I/O; it does not decide what Mary should believe.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mary.runtime.persistence import atomic_write_json, load_json_recovering


class KnowledgeStateStore:
    """Persist LearningKnowledge candidates and KnowledgeManager state together."""

    SCHEMA_VERSION = 1

    def __init__(self, *, candidates: Any, knowledge: Any) -> None:
        self.candidates = candidates
        self.knowledge = knowledge
        self.path: Path | None = None
        self.auto_save = False
        self.last_error: str | None = None

    def configure(
        self,
        path: str | Path,
        *,
        auto_save: bool = True,
        load: bool = True,
    ) -> bool:
        self.path = Path(path)
        self.auto_save = bool(auto_save)
        if load:
            return self.load()
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "learning_candidates": self.candidates.to_dict(),
            "knowledge": self.knowledge.to_dict(),
        }

    def save(self) -> bool:
        if self.path is None:
            return True
        try:
            ok = atomic_write_json(
                self.path,
                self.to_dict(),
                backup_generations=3,
                indent=2,
            )
            self.last_error = None if ok else "write_failed"
            return bool(ok)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return False

    def load(self) -> bool:
        if self.path is None:
            return True
        try:
            payload, _ = load_json_recovering(
                self.path,
                backup_generations=3,
                restore_primary=False,
            )
            if payload is None:
                self.last_error = None
                return True
            if not isinstance(payload, dict):
                self.last_error = "invalid_payload"
                return False

            self.candidates.from_dict(
                payload.get("learning_candidates", [])
            )
            self.knowledge.from_dict(
                payload.get("knowledge", {})
            )
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return False

    def changed(self) -> bool:
        if not self.auto_save:
            return True
        return self.save()

    def status(self) -> dict[str, Any]:
        concepts = list(self.knowledge.get_all_concepts())
        candidates = list(self.candidates.get_all())
        return {
            "configured": self.path is not None,
            "path": str(self.path) if self.path is not None else None,
            "auto_save": self.auto_save,
            "concepts": len(concepts),
            "candidates": len(candidates),
            "last_error": self.last_error,
        }
