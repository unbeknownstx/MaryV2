"""
MaryV2 - Memory Manager

Public interface for Mary's memory architecture.

The MemoryManager coordinates:
- episodic memory
- semantic memory
- working memory
- retrieval
- consolidation

Individual memory systems remain responsible for their own
storage and behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from mary.memory.episodic import EpisodicMemoryStore
from mary.memory.semantic import SemanticMemory
from mary.memory.working import WorkingMemory
from mary.memory.retrieval import MemoryRetriever
from mary.memory.consolidation import MemoryConsolidator


class MemoryManager:
    """
    Unified public interface for Mary's memory architecture.
    """

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
    ) -> None:

        self.episodic = (
            episodic_memory
            if episodic_memory is not None
            else EpisodicMemoryStore()
        )

        self.semantic = (
            semantic_memory
            if semantic_memory is not None
            else SemanticMemory()
        )

        self.working = (
            working_memory
            if working_memory is not None
            else WorkingMemory()
        )

        self.retrieval = (
            retrieval
            if retrieval is not None
            else MemoryRetriever(
                episodic=self.episodic,
                semantic=self.semantic,
                working=self.working,
            )
        )

        self.consolidation = (
            consolidation
            if consolidation is not None
            else MemoryConsolidator(
                episodic_memory=self.episodic,
                semantic_memory=self.semantic,
                working_memory=self.working,
                retrieval=self.retrieval,
            )
        )

        self.storage_path = (
            Path(storage_path)
            if storage_path is not None
            else None
        )

        self.auto_save = bool(auto_save)

        if auto_load and self.storage_path is not None:
            self.load()

    # ========================================================
    # REMEMBER
    # ========================================================

    def remember(
        self,
        content: str,
        *,
        memory_type: str = "episodic",
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Store information in the requested memory system.
        """

        if not content or not str(content).strip():
            return None

        content = str(content).strip()
        metadata = metadata or {}

        if memory_type == "episodic":
            result = self.episodic.create(
                content=content,
                importance=importance,
                source=metadata.get(
                    "source",
                    "interaction",
                ),
                event_type=metadata.get(
                    "event_type",
                    "general",
                ),
                participants=metadata.get(
                    "participants",
                    [],
                ),
                emotional_context=metadata.get(
                    "emotional_context",
                    {},
                ),
                metadata=metadata,
            )

            self._persist_if_enabled()
            return result

        if memory_type == "working":
            return self.working.add(
                content=content,
                category=metadata.get(
                    "category",
                    "general",
                ),
                importance=importance,
                source=metadata.get(
                    "source",
                ),
            )

        if memory_type == "semantic":
            subject = metadata.get("subject")
            predicate = metadata.get("predicate")
            value = metadata.get("value")

            if subject is None:
                raise ValueError(
                    "Semantic memory requires metadata['subject']."
                )

            if predicate is None:
                raise ValueError(
                    "Semantic memory requires metadata['predicate']."
                )

            result = self.semantic.add(
                subject=subject,
                predicate=predicate,
                value=(
                    content
                    if value is None
                    else value
                ),
                confidence=metadata.get(
                    "confidence",
                    1.0,
                ),
                source=metadata.get(
                    "source",
                ),
            )

            self._persist_if_enabled()
            return result

        raise ValueError(
            f"Unknown memory type: {memory_type}"
        )

    # ========================================================
    # SPECIALIZED REMEMBER METHODS
    # ========================================================

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
        """
        Store an episodic experience.
        """

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
        """
        Store durable semantic knowledge.
        """

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
        """
        Store temporary working-memory information.
        """

        return self.working.add(
            content=content,
            category=category,
            importance=importance,
            source=source,
        )

    # ========================================================
    # RECALL
    # ========================================================

    def recall(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories.
        """

        if not query or not str(query).strip():
            return []

        return self.retrieval.retrieve(
            str(query).strip(),
            limit=limit,
        )

    # ========================================================
    # CONTEXT
    # ========================================================

    def build_context(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Build structured memory context for cognition.
        """

        return {
            "query": query,
            "relevant_memories": self.recall(
                query,
                limit=limit,
            ),
            "working_memory": self.working.all(),
        }

    # ========================================================
    # CONSOLIDATION
    # ========================================================

    def consolidate(self) -> int:
        """
        Consolidate eligible memories into semantic memory.
        """

        promoted = self.consolidation.consolidate_and_promote()

        if promoted:
            self._persist_if_enabled()

        return promoted

    # ========================================================
    # PERSISTENCE
    # ========================================================

    def configure_persistence(
        self,
        storage_path: str | Path,
        *,
        auto_save: bool = True,
        load: bool = True,
    ) -> bool:
        """
        Configure durable episodic/semantic memory storage.

        Working memory is intentionally not persisted.
        """

        self.storage_path = Path(storage_path)
        self.auto_save = bool(auto_save)

        if load:
            return self.load()

        return True

    def save(self) -> bool:
        """Persist durable memory to disk using an atomic replace."""

        if self.storage_path is None:
            return False

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "version": 1,
            "episodic": self.episodic.export(),
            "semantic": [
                dict(memory)
                for memory in self.semantic.all()
            ],
        }

        temporary_path = self.storage_path.with_suffix(
            self.storage_path.suffix + ".tmp"
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    payload,
                    file,
                    indent=4,
                    ensure_ascii=False,
                    default=str,
                )

            temporary_path.replace(
                self.storage_path
            )

        except OSError:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            return False

        return True

    def load(self) -> bool:
        """Load durable episodic/semantic memory from disk."""

        if self.storage_path is None:
            return False

        if not self.storage_path.exists():
            return False

        try:
            with self.storage_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                payload = json.load(file)

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            return False

        if not isinstance(payload, dict):
            return False

        episodic_data = payload.get(
            "episodic",
            [],
        )

        semantic_data = payload.get(
            "semantic",
            [],
        )

        if not isinstance(episodic_data, list):
            episodic_data = []

        if not isinstance(semantic_data, list):
            semantic_data = []

        self.episodic.import_data(
            episodic_data
        )

        self.semantic.clear()

        for item in semantic_data:
            if not isinstance(item, dict):
                continue

            subject = item.get(
                "subject"
            )
            predicate = item.get(
                "predicate"
            )

            if subject is None or predicate is None:
                continue

            restored = self.semantic.add(
                subject=str(subject),
                predicate=str(predicate),
                value=item.get(
                    "value"
                ),
                confidence=item.get(
                    "confidence",
                    1.0,
                ),
                source=item.get(
                    "source"
                ),
            )

            for field in (
                "id",
                "created_at",
                "updated_at",
            ):
                if item.get(field) is not None:
                    restored[field] = item[field]

        return True

    def _persist_if_enabled(self) -> None:
        if (
            self.auto_save
            and self.storage_path is not None
        ):
            self.save()

    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> Dict[str, Any]:
        """
        Return memory-system status.
        """

        return {
            "episodic": True,
            "semantic": True,
            "working": True,
            "retrieval": True,
            "consolidation": True,
            "counts": {
                "episodic": self.episodic.count(),
                "semantic": self.semantic.count(),
                "working": self.working.count(),
            },
        }