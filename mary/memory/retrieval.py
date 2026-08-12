"""
MaryV2 Memory Retrieval

Responsible for retrieving relevant memories from Mary's
different memory systems.

Retrieval does not own memory storage.
It asks memory systems for candidates and ranks them
for the cognition layer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class MemoryRetriever:
    """
    Retrieves relevant memories from Mary's memory systems.

    The retriever is intentionally lightweight. Storage and
    memory-specific behavior remain inside their respective
    memory modules.
    """

    def __init__(
        self,
        episodic=None,
        semantic=None,
        working=None,
    ):
        self.episodic = episodic
        self.semantic = semantic
        self.working = working

    # ============================================================
    # PUBLIC RETRIEVAL
    # ============================================================

    def retrieve(
        self,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the most relevant memories for a query.

        Results from working, episodic, and semantic memory
        are combined into a single ranked list.
        """

        if not query or not str(query).strip():
            return []

        query = str(query).strip()

        if limit <= 0:
            return []

        candidates: List[Dict[str, Any]] = []

        candidates.extend(
            self._retrieve_working(query)
        )

        candidates.extend(
            self._retrieve_episodic(query)
        )

        candidates.extend(
            self._retrieve_semantic(query)
        )

        ranked = self._rank_results(
            query,
            candidates
        )

        return ranked[:limit]

    # ============================================================
    # WORKING MEMORY
    # ============================================================

    def _retrieve_working(
        self,
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve information currently held in working memory.
        """

        if self.working is None:
            return []

        try:
            if hasattr(self.working, "search"):
                results = self.working.search(query)

            elif hasattr(self.working, "retrieve"):
                results = self.working.retrieve(query)

            elif hasattr(self.working, "get_context"):
                results = self.working.get_context()

            else:
                return []

            return self._normalize_results(
                results,
                "working"
            )

        except Exception as error:
            print(
                f"[RETRIEVAL] Working memory error: {error}"
            )
            return []

    # ============================================================
    # EPISODIC MEMORY
    # ============================================================

    def _retrieve_episodic(
        self,
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant past experiences/events.
        """

        if self.episodic is None:
            return []

        try:
            if hasattr(self.episodic, "search"):
                results = self.episodic.search(query)

            elif hasattr(self.episodic, "retrieve"):
                results = self.episodic.retrieve(query)

            elif hasattr(self.episodic, "get_all"):
                results = self.episodic.get_all()

            else:
                return []

            return self._normalize_results(
                results,
                "episodic"
            )

        except Exception as error:
            print(
                f"[RETRIEVAL] Episodic memory error: {error}"
            )
            return []

    # ============================================================
    # SEMANTIC MEMORY
    # ============================================================

    def _retrieve_semantic(
        self,
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant facts and knowledge.
        """

        if self.semantic is None:
            return []

        try:
            if hasattr(self.semantic, "search"):
                results = self.semantic.search(query)

            elif hasattr(self.semantic, "retrieve"):
                results = self.semantic.retrieve(query)

            elif hasattr(self.semantic, "get_all"):
                results = self.semantic.get_all()

            else:
                return []

            return self._normalize_results(
                results,
                "semantic"
            )

        except Exception as error:
            print(
                f"[RETRIEVAL] Semantic memory error: {error}"
            )
            return []

    # ============================================================
    # NORMALIZATION
    # ============================================================

    def _normalize_results(
        self,
        results: Any,
        memory_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Convert different memory-system result formats into
        one consistent representation.
        """

        if results is None:
            return []

        if isinstance(results, dict):
            results = [results]

        if not isinstance(results, list):
            return []

        normalized: List[Dict[str, Any]] = []

        for result in results:

            if isinstance(result, dict):
                item = dict(result)

            else:
                item = {
                    "content": str(result)
                }

            item.setdefault(
                "memory_type",
                memory_type
            )

            item.setdefault(
                "score",
                0.0
            )

            normalized.append(item)

        return normalized

    # ============================================================
    # RANKING
    # ============================================================

    def _rank_results(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Rank memory candidates.

        Existing similarity/relevance scores are respected.
        A small lexical relevance signal is added when possible.
        """

        query_words = set(
            query.lower().split()
        )

        scored = []

        for candidate in candidates:

            content = self._extract_content(
                candidate
            )

            content_words = set(
                content.lower().split()
            )

            lexical_score = 0.0

            if query_words and content_words:
                overlap = query_words.intersection(
                    content_words
                )

                lexical_score = (
                    len(overlap)
                    / len(query_words)
                )

            existing_score = self._safe_float(
                candidate.get("score", 0.0)
            )

            combined_score = (
                existing_score * 0.7
                + lexical_score * 0.3
            )

            item = dict(candidate)

            item["retrieval_score"] = combined_score

            scored.append(item)

        scored.sort(
            key=lambda item: item.get(
                "retrieval_score",
                0.0
            ),
            reverse=True
        )

        return self._remove_duplicates(
            scored
        )

    # ============================================================
    # CONTENT EXTRACTION
    # ============================================================

    @staticmethod
    def _extract_content(
        item: Dict[str, Any],
    ) -> str:
        """
        Extract searchable text from a memory record.
        """

        for key in (
            "content",
            "text",
            "description",
            "summary",
            "message",
            "fact",
        ):
            value = item.get(key)

            if value is not None:
                return str(value)

        return ""

    # ============================================================
    # DUPLICATE REMOVAL
    # ============================================================

    @staticmethod
    def _remove_duplicates(
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate memory records while preserving ranking.
        """

        seen = set()
        unique = []

        for result in results:

            memory_id = result.get("id")

            if memory_id is not None:
                key = (
                    result.get("memory_type"),
                    str(memory_id)
                )

            else:
                key = (
                    result.get("memory_type"),
                    MemoryRetriever._extract_content(
                        result
                    ).strip().lower()
                )

            if key in seen:
                continue

            seen.add(key)
            unique.append(result)

        return unique

    # ============================================================
    # UTILITIES
    # ============================================================

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> float:
        """
        Safely convert a value to float.
        """

        try:
            return float(value)

        except (TypeError, ValueError):
            return 0.0