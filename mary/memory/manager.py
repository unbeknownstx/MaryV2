"""MaryV2 memory manager with bounded storage, retrieval, and recovery."""

from __future__ import annotations

from pathlib import Path
import hashlib
from typing import Any, Dict, List, Optional

from mary.governance.limits import RuntimeLimits
from mary.memory.consolidation import MemoryConsolidator
from mary.memory.episodic import EpisodicMemoryStore
from mary.memory.retrieval import MemoryRetriever
from mary.memory.semantic import SemanticMemory
from mary.memory.working import WorkingMemory
from mary.runtime.persistence import (
    atomic_write_json,
    cleanup_stale_temps,
    load_json_recovering,
)


class MemoryManager:
    """Unified public interface for Mary's bounded memory architecture."""

    def __init__(
        self,
        episodic_memory: Optional[EpisodicMemoryStore] = None,
        semantic_memory: Optional[SemanticMemory] = None,
        working_memory: Optional[WorkingMemory] = None,
        retrieval: Optional[MemoryRetriever] = None,
        consolidation: Optional[MemoryConsolidator] = None,
        storage_path: str | Path | None = None,
        auto_load: bool = False,
        auto_save: bool = False,
        limits: RuntimeLimits | None = None,
    ) -> None:
        self.limits = limits or RuntimeLimits()
        self.episodic = episodic_memory or EpisodicMemoryStore(
            capacity=self.limits.episodic_capacity,
            content_limit=self.limits.memory_content_characters,
        )
        self.semantic = semantic_memory or SemanticMemory(
            capacity=self.limits.semantic_capacity,
            content_limit=self.limits.memory_content_characters,
        )
        self.working = working_memory or WorkingMemory(
            capacity=self.limits.working_memory_capacity,
        )
        self.retrieval = retrieval or MemoryRetriever(
            episodic=self.episodic,
            semantic=self.semantic,
            working=self.working,
        )
        self.consolidation = consolidation or MemoryConsolidator(
            episodic_memory=self.episodic,
            semantic_memory=self.semantic,
            working_memory=self.working,
            retrieval=self.retrieval,
        )
        self.storage_path = Path(storage_path) if storage_path is not None else None
        self.auto_save = bool(auto_save)
        self.last_load_source: str | None = None
        self.recovered_from_backup = False
        self.stale_temps_removed = 0
        # Revision of the primary persistence file last loaded or written by
        # this MemoryManager. This prevents a stale long-lived process from
        # overwriting a newer canonical file installed by another authority
        # during deployment/migration.
        self._storage_revision: tuple[int, int, str] | None = None
        self.last_lifecycle_event: Dict[str, Any] = {
            "operation": "startup",
            "stored": False,
            "reason": "no_memory_operation_yet",
        }
        if auto_load and self.storage_path is not None:
            self.load()

    def remember(
        self,
        content: str,
        *,
        memory_type: str = "episodic",
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not content or not str(content).strip():
            return None
        content = str(content).strip()
        metadata = metadata or {}
        if memory_type == "episodic":
            result = self.episodic.create(
                content=content,
                importance=importance,
                source=metadata.get("source", "interaction"),
                event_type=metadata.get("event_type", "general"),
                participants=metadata.get("participants", []),
                emotional_context=metadata.get("emotional_context", {}),
                metadata=metadata,
            )
            self.record_lifecycle_event({
                "operation": "remember",
                "stored": result is not None,
                "memory_type": "episodic",
                "memory_id": getattr(result, "id", None),
                "importance": importance,
                "source": metadata.get("source", "interaction"),
            })
            self._persist_if_enabled()
            return result
        if memory_type == "working":
            result = self.working.add(
                content=content,
                category=metadata.get("category", "general"),
                importance=importance,
                source=metadata.get("source"),
            )
            self.record_lifecycle_event({
                "operation": "remember",
                "stored": result is not None,
                "memory_type": "working",
                "importance": importance,
                "source": metadata.get("source"),
            })
            return result
        if memory_type == "semantic":
            subject = metadata.get("subject")
            predicate = metadata.get("predicate")
            value = metadata.get("value")
            if subject is None:
                raise ValueError("Semantic memory requires metadata['subject'].")
            if predicate is None:
                raise ValueError("Semantic memory requires metadata['predicate'].")
            result = self.semantic.add(
                subject=subject,
                predicate=predicate,
                value=content if value is None else value,
                confidence=metadata.get("confidence", 1.0),
                source=metadata.get("source"),
            )
            self.record_lifecycle_event({
                "operation": "remember",
                "stored": result is not None,
                "memory_type": "semantic",
                "memory_id": result.get("id") if isinstance(result, dict) else None,
                "importance": importance,
                "source": metadata.get("source"),
            })
            self._persist_if_enabled()
            return result
        raise ValueError(f"Unknown memory type: {memory_type}")

    def remember_event(
        self,
        content: str,
        *,
        importance: float = 0.5,
        source: str = "interaction",
        event_type: str = "general",
        participants: Optional[List[str]] = None,
        emotional_context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        result = self.episodic.create(
            content=content,
            importance=importance,
            source=source,
            event_type=event_type,
            participants=participants,
            emotional_context=emotional_context,
            metadata=metadata,
        )
        self._persist_if_enabled()
        return result

    def remember_fact(
        self,
        subject: str,
        predicate: str,
        value: Any,
        *,
        confidence: float = 1.0,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = self.semantic.add(
            subject=subject,
            predicate=predicate,
            value=value,
            confidence=confidence,
            source=source,
        )
        self._persist_if_enabled()
        return result

    def remember_working(
        self,
        content: Any,
        *,
        category: str = "general",
        importance: float = 0.5,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.working.add(
            content=content,
            category=category,
            importance=importance,
            source=source,
        )

    def recall(self, query: str, *, limit: int = 5) -> List[Dict[str, Any]]:
        if not query or not str(query).strip():
            return []
        bounded_limit = max(1, min(int(limit), int(self.limits.memory_recall_limit)))
        return self.retrieval.retrieve(str(query).strip(), limit=bounded_limit)

    def build_context(self, query: str, *, limit: int = 5) -> Dict[str, Any]:
        return {
            "query": query,
            "relevant_memories": self.recall(query, limit=limit),
            "working_memory": self.working.recent(
                max(1, int(self.limits.memory_context_working_limit))
            ),
        }

    def consolidate(self) -> int:
        # Safe default: high importance creates a candidate, but only
        # structured/deterministic facts cross into semantic memory.
        promoted = self.consolidation.consolidate_and_promote()
        # Semantic/episodic stores enforce their own hard capacities.
        if promoted:
            self._persist_if_enabled()
        return promoted


    def consolidation_candidates(self) -> List[Dict[str, Any]]:
        """Return candidates with non-mutating semantic-promotion review data."""

        reviewed: List[Dict[str, Any]] = []
        for candidate in self.consolidation.consolidate():
            item = dict(candidate)
            item["review"] = self.consolidation.review_candidate(candidate)
            reviewed.append(item)
        return reviewed

    def configure_persistence(
        self,
        storage_path: str | Path,
        *,
        auto_save: bool = True,
        load: bool = True,
    ) -> bool:
        self.storage_path = Path(storage_path)
        self.auto_save = bool(auto_save)
        if load:
            return self.load()
        return True

    @staticmethod
    def _file_revision(path: Path) -> tuple[int, int, str] | None:
        try:
            data = path.read_bytes()
            stat = path.stat()
        except OSError:
            return None
        return (
            int(stat.st_mtime_ns),
            len(data),
            hashlib.sha256(data).hexdigest(),
        )

    def save(self) -> bool:
        if self.storage_path is None:
            return False

        current_revision = self._file_revision(self.storage_path)

        # If this process loaded/wrote a specific primary file and another
        # authority has replaced that file since, this process is stale.
        # Never destroy newer canonical state during autosave or shutdown.
        if (
            self._storage_revision is not None
            and current_revision != self._storage_revision
        ):
            return False

        payload = {
            "version": 2,
            "policy": "bounded_selective_persistence",
            "episodic": self.episodic.export(),
            "semantic": [dict(memory) for memory in self.semantic.all()],
        }
        saved = atomic_write_json(
            self.storage_path,
            payload,
            backup_generations=self.limits.backup_generations,
            indent=2,
        )
        if saved:
            self._storage_revision = self._file_revision(self.storage_path)
        return saved

    def load(self) -> bool:
        if self.storage_path is None:
            return False
        self.stale_temps_removed += cleanup_stale_temps(self.storage_path)
        payload, source = load_json_recovering(
            self.storage_path,
            backup_generations=self.limits.backup_generations,
            restore_primary=False,
        )
        if not isinstance(payload, dict) or source is None:
            return False

        episodic_data = payload.get("episodic", [])
        semantic_data = payload.get("semantic", [])
        if not isinstance(episodic_data, list):
            episodic_data = []
        if not isinstance(semantic_data, list):
            semantic_data = []

        self.episodic.import_data(episodic_data)
        self.semantic.clear()
        for item in semantic_data:
            if not isinstance(item, dict):
                continue
            subject = item.get("subject")
            predicate = item.get("predicate")
            if subject is None or predicate is None:
                continue
            restored = self.semantic.add(
                subject=str(subject),
                predicate=str(predicate),
                value=item.get("value"),
                confidence=item.get("confidence", 1.0),
                source=item.get("source"),
            )
            for field in ("id", "created_at", "updated_at"):
                if item.get(field) is not None:
                    restored[field] = item[field]

        self.last_load_source = str(source)
        self.recovered_from_backup = source != self.storage_path

        # Track the primary file itself, even when recovery loaded a backup.
        # A subsequent unchanged shutdown may safely persist recovered state,
        # while an externally replaced primary is protected from stale writes.
        self._storage_revision = self._file_revision(self.storage_path)
        return True

    def restore_recovered_primary(self) -> bool:
        """If a backup was loaded, explicitly rewrite the healthy state as primary."""
        if not self.recovered_from_backup:
            return True
        ok = self.save()
        if ok:
            self.recovered_from_backup = False
            self.last_load_source = str(self.storage_path) if self.storage_path else None
        return ok

    def record_lifecycle_event(self, event: Dict[str, Any] | None) -> None:
        """Record a compact, display-safe explanation of the latest memory action."""
        if not isinstance(event, dict):
            return
        allowed = {
            "operation", "detected", "learned", "stored", "already_known",
            "memory_type", "memory_id", "importance", "category", "label",
            "reason", "source", "relationship_committed", "shared_work_recorded",
        }
        self.last_lifecycle_event = {
            key: event.get(key)
            for key in allowed
            if key in event
        }

    def lifecycle_status(self) -> Dict[str, Any]:
        """Return read-only observability for storage and semantic consolidation."""
        try:
            candidates = self.consolidation_candidates()
        except Exception:
            candidates = []
        promotable = sum(1 for item in candidates if item.get("review", {}).get("promotable"))
        review_required = sum(
            1
            for item in candidates
            if item.get("review", {}).get("classification") == "review_required"
        )
        blocked = max(0, len(candidates) - promotable - review_required)
        semantic_count = self.semantic.count()
        return {
            "policy": "bounded_selective_persistence",
            "last_event": dict(self.last_lifecycle_event),
            "consolidation": {
                "automatic": False,
                "eligible_candidates": len(candidates),
                "promotable_candidates": promotable,
                "review_required_candidates": review_required,
                "blocked_candidates": blocked,
                "semantic_count": semantic_count,
                "reason": (
                    "semantic promotion is selective and not automatic during normal conversation"
                    if semantic_count == 0
                    else "semantic memory contains promoted durable facts; normal conversation still does not auto-promote every episode"
                ),
            },
        }

    def _persist_if_enabled(self) -> None:
        if self.auto_save and self.storage_path is not None:
            self.save()

    def status(self) -> Dict[str, Any]:
        file_size = 0
        if self.storage_path is not None:
            try:
                file_size = self.storage_path.stat().st_size
            except OSError:
                file_size = 0
        return {
            "episodic": True,
            "semantic": True,
            "working": True,
            "retrieval": True,
            "consolidation": True,
            "policy": "bounded_selective_persistence",
            "counts": {
                "episodic": self.episodic.count(),
                "semantic": self.semantic.count(),
                "working": self.working.count(),
            },
            "capacities": {
                "episodic": int(getattr(self.episodic, "capacity", self.limits.episodic_capacity)),
                "semantic": int(getattr(self.semantic, "capacity", self.limits.semantic_capacity)),
                "working": int(getattr(self.working, "capacity", self.limits.working_memory_capacity)),
                "recall_limit": int(self.limits.memory_recall_limit),
                "working_context_limit": int(self.limits.memory_context_working_limit),
            },
            "evicted": {
                "episodic": int(getattr(self.episodic, "evicted_count", 0)),
                "semantic": int(getattr(self.semantic, "evicted_count", 0)),
            },
            "persistence": {
                "path": str(self.storage_path) if self.storage_path else None,
                "backup_generations": int(self.limits.backup_generations),
                "last_load_source": self.last_load_source,
                "recovered_from_backup": self.recovered_from_backup,
                "stale_temps_removed": self.stale_temps_removed,
                "file_size_bytes": file_size,
                "soft_limit_bytes": int(self.limits.state_file_soft_limit_bytes),
                "over_soft_limit": file_size > int(self.limits.state_file_soft_limit_bytes),
            },
        }