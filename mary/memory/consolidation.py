"""
MaryV2 - Memory Consolidation

Consolidation is responsible for reviewing memories and identifying
information that should be promoted, summarized, or retained as
long-term knowledge.

It does NOT own memory storage.
It coordinates consolidation between memory components.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


class MemoryConsolidator:
    """
    Converts useful experiences into durable memory candidates.

    The consolidator intentionally remains independent from the
    storage implementation. This allows V2 to evolve from simple
    JSON-backed memory into databases/vector stores later.
    """

    def __init__(
        self,
        episodic_memory=None,
        semantic_memory=None,
        working_memory=None,
        retrieval=None,
    ):
        self.episodic_memory = episodic_memory
        self.semantic_memory = semantic_memory
        self.working_memory = working_memory
        self.retrieval = retrieval

    # ============================================================
    # PUBLIC API
    # ============================================================

    def consolidate(self) -> List[Dict[str, Any]]:
        """
        Review available memories and return consolidation candidates.

        This method does not automatically destroy or rewrite memories.
        It identifies memories that appear important enough to preserve.
        """

        memories = self._collect_memories()

        if not memories:
            return []

        candidates = []

        for memory in memories:
            if not isinstance(memory, dict):
                continue

            if self._should_consolidate(memory):
                candidate = self._create_candidate(memory)

                if candidate is not None:
                    candidates.append(candidate)

        return candidates

    def consolidate_memory(
        self,
        memory: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate one memory and return a consolidation candidate.
        """

        if not isinstance(memory, dict):
            return None

        if not self._should_consolidate(memory):
            return None

        return self._create_candidate(memory)

    def promote(
        self,
        candidate: Dict[str, Any],
    ) -> bool:
        """
        Promote a consolidation candidate into semantic memory.

        Returns True when promotion succeeds.
        """

        if not isinstance(candidate, dict):
            return False

        if self.semantic_memory is None:
            return False

        content = candidate.get("content")

        if not content:
            return False

        # Support multiple possible semantic-memory APIs so the
        # consolidation layer remains loosely coupled.
        if hasattr(self.semantic_memory, "add"):
            self.semantic_memory.add(
                content=content,
                metadata=candidate.get("metadata", {}),
            )
            return True

        if hasattr(self.semantic_memory, "add_memory"):
            self.semantic_memory.add_memory(
                content,
                metadata=candidate.get("metadata", {}),
            )
            return True

        if hasattr(self.semantic_memory, "store"):
            self.semantic_memory.store(
                content,
                metadata=candidate.get("metadata", {}),
            )
            return True

        return False

    def consolidate_and_promote(self) -> int:
        """
        Consolidate available memories and promote successful candidates.

        Returns the number of memories successfully promoted.
        """

        candidates = self.consolidate()

        promoted = 0

        for candidate in candidates:
            if self.promote(candidate):
                promoted += 1

        return promoted

    # ============================================================
    # MEMORY COLLECTION
    # ============================================================

    def _collect_memories(self) -> List[Dict[str, Any]]:
        """
        Collect candidate memories from available memory systems.
        """

        memories: List[Dict[str, Any]] = []

        if self.episodic_memory is not None:
            memories.extend(
                self._extract_memories(
                    self.episodic_memory
                )
            )

        if self.working_memory is not None:
            memories.extend(
                self._extract_memories(
                    self.working_memory
                )
            )

        return memories

    def _extract_memories(
        self,
        memory_system,
    ) -> List[Dict[str, Any]]:
        """
        Extract memories without requiring a specific storage backend.
        """

        methods = (
            "get_all",
            "get_memories",
            "all",
            "list_memories",
        )

        for method_name in methods:
            method = getattr(
                memory_system,
                method_name,
                None,
            )

            if callable(method):
                try:
                    result = method()

                    if result is None:
                        return []

                    if isinstance(result, list):
                        return [
                            item
                            for item in result
                            if isinstance(item, dict)
                        ]

                except Exception:
                    return []

        return []

    # ============================================================
    # CONSOLIDATION DECISION
    # ============================================================

    def _should_consolidate(
        self,
        memory: Dict[str, Any],
    ) -> bool:
        """
        Determine whether a memory is important enough to preserve.

        V2 currently uses simple deterministic heuristics.

        Later this can be expanded with:
        - LLM evaluation
        - importance scoring
        - repetition detection
        - emotional significance
        - relationship significance
        - goal relevance
        - novelty
        - contradiction detection
        """

        content = memory.get("content")

        if not content:
            return False

        # Explicitly marked important memories should always qualify.
        if memory.get("important") is True:
            return True

        if memory.get("consolidate") is True:
            return True

        importance = memory.get("importance", 0)

        try:
            importance = float(importance)
        except (TypeError, ValueError):
            importance = 0

        if importance >= 0.7:
            return True

        # Emotional significance can make an experience worth keeping.
        emotional_weight = memory.get(
            "emotional_weight",
            memory.get("emotional_importance", 0),
        )

        try:
            emotional_weight = float(
                emotional_weight
            )
        except (TypeError, ValueError):
            emotional_weight = 0

        if emotional_weight >= 0.7:
            return True

        # Repeated memories are candidates for consolidation.
        repetition = memory.get(
            "repetition",
            memory.get("access_count", 0),
        )

        try:
            repetition = int(repetition)
        except (TypeError, ValueError):
            repetition = 0

        if repetition >= 3:
            return True

        return False

    # ============================================================
    # CANDIDATE CREATION
    # ============================================================

    def _create_candidate(
        self,
        memory: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Convert an episodic memory into a semantic-memory candidate.
        """

        content = memory.get("content")

        if not content:
            return None

        return {
            "type": "consolidation_candidate",
            "content": str(content).strip(),
            "source_memory_id": memory.get("id"),
            "created_at": datetime.now().isoformat(),
            "metadata": {
                "source": "memory_consolidation",
                "memory_type": memory.get(
                    "type",
                    "episodic",
                ),
                "importance": memory.get(
                    "importance",
                    0,
                ),
                "emotional_weight": memory.get(
                    "emotional_weight",
                    memory.get(
                        "emotional_importance",
                        0,
                    ),
                ),
                "tags": memory.get(
                    "tags",
                    [],
                ),
            },
        }

    # ============================================================
    # UTILITY
    # ============================================================

    def count_candidates(self) -> int:
        """
        Return the number of memories currently eligible
        for consolidation.
        """

        return len(
            self.consolidate()
        )