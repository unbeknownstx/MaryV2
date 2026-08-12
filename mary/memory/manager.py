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
            return self.episodic.create(
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

            return self.semantic.add(
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

        return self.episodic.create(
            content=content,
            importance=importance,
            source=source,
            event_type=event_type,
            participants=participants,
            emotional_context=emotional_context,
            metadata=metadata,
        )

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

        return self.semantic.add(
            subject=subject,
            predicate=predicate,
            value=value,
            confidence=confidence,
            source=source,
        )

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

        return self.consolidation.consolidate_and_promote()

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