
"""
MaryV2 - Memory Manager

The MemoryManager is the public interface for Mary's memory system.

It coordinates:
- Episodic memory
- Semantic memory
- Working memory
- Retrieval
- Consolidation

The manager does not implement internal storage logic.
Each subsystem remains responsible for its own behavior.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class MemoryManager:
    """
    Unified interface for Mary's memory architecture.

    The manager provides a stable boundary between cognition
    and the individual memory subsystems.
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

            initializer = getattr(
                system,
                "initialize",
                None,
            )

            if callable(initializer):
                initializer()

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

        if content is None:
            return None

        content = str(content).strip()

        if not content:
            return None

        metadata = dict(metadata or {})

        memory_type = str(
            memory_type
        ).strip().lower()

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

        add = getattr(
            self.episodic,
            "add",
            None,
        )

        if callable(add):
            try:
                return add(
                    content=content,
                    importance=importance,
                    metadata=metadata,
                )
            except TypeError:
                return add(content)

        add_memory = getattr(
            self.episodic,
            "add_memory",
            None,
        )

        if callable(add_memory):
            try:
                return add_memory(
                    content,
                    importance=importance,
                    metadata=metadata,
                )
            except TypeError:
                return add_memory(content)

        store = getattr(
            self.episodic,
            "store",
            None,
        )

        if callable(store):
            try:
                return store(
                    content,
                    importance=importance,
                    metadata=metadata,
                )
            except TypeError:
                return store(
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
        Store durable factual or semantic information.
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

        add = getattr(
            self.semantic,
            "add",
            None,
        )

        if callable(add):
            try:
                return add(
                    content=content,
                    metadata=metadata,
                )
            except TypeError:
                return add(content)

        add_memory = getattr(
            self.semantic,
            "add_memory",
            None,
        )

        if callable(add_memory):
            try:
                return add_memory(
                    content,
                    metadata=metadata,
                )
            except TypeError:
                return add_memory(content)

        store = getattr(
            self.semantic,
            "store",
            None,
        )

        if callable(store):
            try:
                return store(
                    content,
                    metadata=metadata,
                )
            except TypeError:
                return store(content)

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

        add = getattr(
            self.working,
            "add",
            None,
        )

        if callable(add):
            try:
                return add(
                    content=content,
                    metadata=metadata,
                )
            except TypeError:
                return add(content)

        add_memory = getattr(
            self.working,
            "add_memory",
            None,
        )

        if callable(add_memory):
            try:
                return add_memory(
                    content,
                    metadata=metadata,
                )
            except TypeError:
                return add_memory(content)

        store = getattr(
            self.working,
            "store",
            None,
        )

        if callable(store):
            try:
                return store(
                    content,
                    metadata=metadata,
                )
            except TypeError:
                return store(content)

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
        """

        if query is None:
            return []

        query = str(query).strip()

        if not query or limit <= 0:
            return []

        if self.retrieval is not None:

            search = getattr(
                self.retrieval,
                "search",
                None,
            )

            if callable(search):
                try:
                    result = search(
                        query,
                        limit=limit,
                    )
                except TypeError:
                    result = search(query)

                return self._normalize_results(
                    result
                )

            retrieve = getattr(
                self.retrieval,
                "retrieve",
                None,
            )

            if callable(retrieve):
                try:
                    result = retrieve(
                        query,
                        limit=limit,
                    )
                except TypeError:
                    result = retrieve(query)

                return self._normalize_results(
                    result
                )

        # Fallback to semantic memory.
        if self.semantic is not None:

            search = getattr(
                self.semantic,
                "search",
                None,
            )

            if callable(search):
                try:
                    result = search(
                        query,
                        limit=limit,
                    )
                except TypeError:
                    result = search(query)

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

        consolidate = getattr(
            self.consolidation,
            "consolidate_and_promote",
            None,
        )

        if not callable(consolidate):
            return 0

        try:
            return int(
                consolidate()
            )
        except (TypeError, ValueError):
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
        Build structured memory context for cognition.
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
        Safely retrieve current working-memory contents.
        """

        if self.working is None:
            return []

        for method_name in (
            "all",
            "get_all",
            "get_memories",
            "list_memories",
        ):
            method = getattr(
                self.working,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                result = method()

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

            except Exception:
                return []

        # Direct access fallback for the current WorkingMemory
        # implementation.
        items = getattr(
            self.working,
            "items",
            None,
        )

        if isinstance(items, list):
            return list(items)

        return []

    # ============================================================
    # UTILITY
    # ============================================================

    @staticmethod
    def _normalize_results(
        result: Any,
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
