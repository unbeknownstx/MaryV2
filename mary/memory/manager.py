"""
MaryV2 - Memory Manager

The MemoryManager is the public interface for Mary's memory system.

It coordinates:
    - Episodic memory
    - Semantic memory
    - Working memory
    - Retrieval
    - Consolidation

The manager does not implement the internal storage logic of those
systems. Each subsystem remains responsible for its own behavior.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class MemoryManager:
    """
    Unified interface for Mary's memory architecture.
    """

    def __init__(
        self,
        episodic_memory=None,
        semantic_memory=None,
        working_memory=None,
        retrieval=None,
        consolidation=None,
    ):
        self.episodic = episodic_memory
        self.semantic = semantic_memory
        self.working = working_memory
        self.retrieval = retrieval
        self.consolidation = consolidation

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def initialize(self) -> None:
        """
        Initialize available memory subsystems.

        Subsystems are intentionally optional so Mary can be
        constructed incrementally during development.
        """

        systems = (
            self.episodic,
            self.semantic,
            self.working,
            self.retrieval,
            self.consolidation,
        )

        for system in systems:
            if system is None:
                continue

            initialize = getattr(
                system,
                "initialize",
                None,
            )

            if callable(initialize):
                initialize()

    # ============================================================
    # REMEMBER
    # ============================================================

    def remember(
        self,
        content: str,
        *,
        memory_type: str = "episodic",
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Store a new memory in the appropriate subsystem.
        """

        if not content:
            return None

        metadata = metadata or {}

        if memory_type == "episodic":
            return self._store_episodic(
                content,
                importance,
                metadata,
            )

        if memory_type == "semantic":
            return self._store_semantic(
                content,
                metadata,
            )

        if memory_type == "working":
            return self._store_working(
                content,
                metadata,
            )

        raise ValueError(
            f"Unknown memory type: {memory_type}"
        )

    # ============================================================
    # EPISODIC
    # ============================================================

    def remember_event(
        self,
        content: str,
        *,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Store an experience as episodic memory.
        """

        return self.remember(
            content,
            memory_type="episodic",
            importance=importance,
            metadata=metadata,
        )

    def _store_episodic(
        self,
        content: str,
        importance: float,
        metadata: Dict[str, Any],
    ) -> Any:

        if self.episodic is None:
            return None

        # Support the current implementation while keeping
        # the manager independent from its exact API.
        if hasattr(self.episodic, "add"):
            try:
                return self.episodic.add(
                    content=content,
                    importance=importance,
                    metadata=metadata,
                )
            except TypeError:
                return self.episodic.add(
                    content
                )

        if hasattr(self.episodic, "add_memory"):
            try:
                return self.episodic.add_memory(
                    content,
                    importance=importance,
                    metadata=metadata,
                )
            except TypeError:
                return self.episodic.add_memory(
                    content
                )

        if hasattr(self.episodic, "store"):
            return self.episodic.store(
                content,
                metadata=metadata,
            )

        return None

    # ============================================================
    # SEMANTIC
    # ============================================================

    def remember_fact(
        self,
        content: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Store durable factual/semantic information.
        """

        return self.remember(
            content,
            memory_type="semantic",
            metadata=metadata,
        )

    def _store_semantic(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> Any:

        if self.semantic is None:
            return None

        if hasattr(self.semantic, "add"):
            try:
                return self.semantic.add(
                    content=content,
                    metadata=metadata,
                )
            except TypeError:
                return self.semantic.add(
                    content
                )

        if hasattr(self.semantic, "add_memory"):
            try:
                return self.semantic.add_memory(
                    content,
                    metadata=metadata,
                )
            except TypeError:
                return self.semantic.add_memory(
                    content
                )

        if hasattr(self.semantic, "store"):
            return self.semantic.store(
                content,
                metadata=metadata,
            )

        return None

    # ============================================================
    # WORKING MEMORY
    # ============================================================

    def remember_working(
        self,
        content: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Add information to working memory.
        """

        return self.remember(
            content,
            memory_type="working",
            metadata=metadata,
        )

    def _store_working(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> Any:

        if self.working is None:
            return None

        if hasattr(self.working, "add"):
            try:
                return self.working.add(
                    content=content,
                    metadata=metadata,
                )
            except TypeError:
                return self.working.add(
                    content
                )

        if hasattr(self.working, "add_memory"):
            try:
                return self.working.add_memory(
                    content,
                    metadata=metadata,
                )
            except TypeError:
                return self.working.add_memory(
                    content
                )

        if hasattr(self.working, "store"):
            return self.working.store(
                content,
                metadata=metadata,
            )

        return None

    # ============================================================
    # RETRIEVAL
    # ============================================================

    def recall(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> List[Any]:
        """
        Retrieve relevant memories.

        Retrieval owns the search strategy. The manager simply
        provides the unified interface.
        """

        if not query:
            return []

        if self.retrieval is not None:

            if hasattr(self.retrieval, "search"):
                result = self.retrieval.search(
                    query,
                    limit=limit,
                )

                return self._normalize_results(
                    result
                )

            if hasattr(self.retrieval, "retrieve"):
                result = self.retrieval.retrieve(
                    query,
                    limit=limit,
                )

                return self._normalize_results(
                    result
                )

        # Fallback to semantic memory if a retrieval layer
        # has not been connected yet.
        if self.semantic is not None:

            if hasattr(self.semantic, "search"):
                result = self.semantic.search(
                    query,
                    limit=limit,
                )

                return self._normalize_results(
                    result
                )

        return []

    # ============================================================
    # CONSOLIDATION
    # ============================================================

    def consolidate(self) -> int:
        """
        Run the memory consolidation process.

        Returns the number of memories successfully promoted.
        """

        if self.consolidation is None:
            return 0

        if hasattr(
            self.consolidation,
            "consolidate_and_promote",
        ):
            return int(
                self.consolidation.consolidate_and_promote()
            )

        return 0

    # ============================================================
    # CONTEXT
    # ============================================================

    def build_context(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Build a structured memory context for cognition.

        This gives the cognition layer a stable interface without
        requiring it to know how memories are stored.
        """

        recalled = self.recall(
            query,
            limit=limit,
        )

        working = self._get_working_memory()

        return {
            "query": query,
            "relevant_memories": recalled,
            "working_memory": working,
        }

    def _get_working_memory(self) -> List[Any]:
        """
        Safely retrieve the current working-memory contents.
        """

        if self.working is None:
            return []

        methods = (
            "get_all",
            "get_memories",
            "all",
            "list_memories",
        )

        for method_name in methods:

            method = getattr(
                self.working,
                method_name,
                None,
            )

            if callable(method):

                try:
                    result = method()

                    if result is None:
                        return []

                    if isinstance(
                        result,
                        list,
                    ):
                        return result

                except Exception:
                    return []

        return []

    # ============================================================
    # UTILITY
    # ============================================================

    @staticmethod
    def _normalize_results(
        result,
    ) -> List[Any]:
        """
        Normalize retrieval results into a list.
        """

        if result is None:
            return []

        if isinstance(
            result,
            list,
        ):
            return result

        if isinstance(
            result,
            tuple,
        ):
            return list(result)

        return [result]

    def status(self) -> Dict[str, bool]:
        """
        Return the availability of each memory subsystem.
        """

        return {
            "episodic": self.episodic is not None,
            "semantic": self.semantic is not None,
            "working": self.working is not None,
            "retrieval": self.retrieval is not None,
            "consolidation": self.consolidation is not None,
        }