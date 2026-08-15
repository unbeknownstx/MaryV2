"""
MaryV2 Memory Retrieval

Responsible for retrieving relevant memories from Mary's
different memory systems.

Retrieval does not own memory storage.

It interprets the user's query, retrieves candidates from
working, episodic, and semantic memory, and ranks those
candidates according to the meaning of the query.

Important distinction:

    Semantic memory:
        Durable facts such as:
            creator likes anime
            creator dislikes shrimp

    Episodic memory:
        Experiences such as:
            creator told Mary that he dislikes shrimp

Retrieval should prefer durable semantic knowledge when a
semantic fact directly answers the user's question.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


class MemoryRetriever:
    """
    Retrieves relevant memories from Mary's memory systems.

    The retriever does not own memory storage.

    Its responsibilities are:

        1. Interpret the query.
        2. Retrieve candidates.
        3. Apply query-specific relevance signals.
        4. Rank candidates.
        5. Remove duplicates.
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

        The query is first interpreted so that natural-language
        questions such as:

            "what do I like?"

        can target the semantic predicate:

            likes

        and:

            "what don't I like?"

        can target:

            dislikes
        """

        if not query or not str(query).strip():
            return []

        if limit <= 0:
            return []

        query = str(query).strip()

        query_intent = self._interpret_query(query)

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
            query=query,
            candidates=candidates,
            query_intent=query_intent,
        )

        return ranked[:limit]

    # ============================================================
    # QUERY INTERPRETATION
    # ============================================================

    def _interpret_query(
        self,
        query: str,
    ) -> Dict[str, Any]:
        """
        Interpret the broad semantic meaning of a memory query.

        This is intentionally deterministic for now.

        Later, this layer can be expanded or replaced with a
        more sophisticated query-understanding system.
        """

        normalized = self._normalize_query(query)

        result: Dict[str, Any] = {
            "type": "general",
            "predicate": None,
            "subject": None,
            "concepts": self._extract_concepts(query),
        }

        # --------------------------------------------------------
        # DISLIKE / NEGATIVE PREFERENCE
        # --------------------------------------------------------

        negative_patterns = (
            "what don't i like",
            "what do i dislike",
            "what i don't like",
            "what i dislike",
            "things i don't like",
            "things i dislike",
            "what are my dislikes",
            "what is something i don't like",
            "what is something i dislike",
        )

        if any(
            pattern in normalized
            for pattern in negative_patterns
        ):
            result["type"] = "preference"
            result["predicate"] = "dislikes"
            result["subject"] = "creator"

            return result

        # --------------------------------------------------------
        # LIKE / POSITIVE PREFERENCE
        # --------------------------------------------------------

        positive_patterns = (
            "what do i like",
            "what i like",
            "things i like",
            "what are my likes",
            "what do i love",
            "what i love",
            "things i love",
        )

        if any(
            pattern in normalized
            for pattern in positive_patterns
        ):
            result["type"] = "preference"
            result["predicate"] = "likes"
            result["subject"] = "creator"

            return result

        # --------------------------------------------------------
        # BROAD MEMORY RECALL
        # --------------------------------------------------------

        broad_patterns = (
            "what do you remember about me",
            "what do you remember about me",
            "what do you know about me",
            "what do you remember",
            "what do you know about me",
            "tell me what you remember",
            "tell me what you know about me",
        )

        if any(
            pattern in normalized
            for pattern in broad_patterns
        ):
            result["type"] = "general_recall"
            result["subject"] = "creator"

            return result

        # --------------------------------------------------------
        # DIRECT CONCEPT SEARCH
        # --------------------------------------------------------

        result["type"] = "concept"

        return result

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

            elif hasattr(self.working, "all"):

                results = self.working.all()

            elif hasattr(self.working, "get_all"):

                results = self.working.get_all()

            else:

                return []

            return self._normalize_results(
                results,
                "working",
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
        Retrieve relevant past experiences and events.
        """

        if self.episodic is None:
            return []

        try:

            if hasattr(self.episodic, "search"):

                results = self.episodic.search(query)

            elif hasattr(self.episodic, "retrieve"):

                results = self.episodic.retrieve(query)

            elif hasattr(self.episodic, "all"):

                results = self.episodic.all()

            elif hasattr(self.episodic, "get_all"):

                results = self.episodic.get_all()

            else:

                return []

            return self._normalize_results(
                results,
                "episodic",
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
        Retrieve relevant durable facts and knowledge.

        For preference questions, semantic memory is queried
        directly using the interpreted predicate whenever
        possible.
        """

        if self.semantic is None:
            return []

        try:

            query_intent = self._interpret_query(query)

            predicate = query_intent.get(
                "predicate"
            )

            subject = query_intent.get(
                "subject"
            )

            # ----------------------------------------------------
            # DIRECT SEMANTIC FACT RETRIEVAL
            # ----------------------------------------------------

            if (
                predicate is not None
                and hasattr(self.semantic, "find")
            ):

                results = self.semantic.find(
                    subject=subject,
                    predicate=predicate,
                )

                return self._normalize_results(
                    results,
                    "semantic",
                )

            # ----------------------------------------------------
            # NORMAL SEMANTIC SEARCH
            # ----------------------------------------------------

            if hasattr(self.semantic, "search"):

                results = self.semantic.search(query)

            elif hasattr(self.semantic, "retrieve"):

                results = self.semantic.retrieve(query)

            elif hasattr(self.semantic, "all"):

                results = self.semantic.all()

            elif hasattr(self.semantic, "get_all"):

                results = self.semantic.get_all()

            else:

                return []

            return self._normalize_results(
                results,
                "semantic",
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
        Convert different memory-system result formats
        into one consistent representation.
        """

        if results is None:
            return []

        if isinstance(results, dict):
            results = [results]

        if not isinstance(
            results,
            (list, tuple),
        ):
            return []

        normalized: List[Dict[str, Any]] = []

        for result in results:

            if isinstance(result, dict):

                item = dict(result)

            elif hasattr(result, "to_dict"):

                try:

                    item = result.to_dict()

                except Exception:

                    item = {
                        "content": str(result)
                    }

            else:

                item = {
                    "content": str(result)
                }

            item.setdefault(
                "memory_type",
                memory_type,
            )

            item.setdefault(
                "score",
                0.0,
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
        query_intent: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Rank memory candidates.

        Ranking considers:

            - existing memory-system score
            - lexical relevance
            - semantic predicate match
            - subject match
            - memory type
            - confidence

        Semantic facts receive a meaningful boost when they
        directly answer a preference question.
        """

        if query_intent is None:
            query_intent = self._interpret_query(query)

        query_words = self._tokenize(query)

        target_predicate = query_intent.get(
            "predicate"
        )

        target_subject = query_intent.get(
            "subject"
        )

        scored: List[Dict[str, Any]] = []

        for candidate in candidates:

            content = self._extract_search_text(
                candidate
            )

            content_words = self._tokenize(
                content
            )

            # ----------------------------------------------------
            # LEXICAL SCORE
            # ----------------------------------------------------

            lexical_score = 0.0

            if query_words and content_words:

                overlap = query_words.intersection(
                    content_words
                )

                lexical_score = (
                    len(overlap)
                    / len(query_words)
                )

            # ----------------------------------------------------
            # EXISTING SCORE
            # ----------------------------------------------------

            existing_score = self._safe_float(
                candidate.get(
                    "score",
                    0.0,
                )
            )

            # ----------------------------------------------------
            # SEMANTIC MATCH
            # ----------------------------------------------------

            predicate_score = 0.0
            subject_score = 0.0

            candidate_predicate = str(
                candidate.get(
                    "predicate",
                    "",
                )
            ).strip().lower()

            candidate_subject = str(
                candidate.get(
                    "subject",
                    "",
                )
            ).strip().lower()

            if (
                target_predicate
                and candidate_predicate
                == str(
                    target_predicate
                ).lower()
            ):
                predicate_score = 1.0

            if (
                target_subject
                and candidate_subject
                == str(
                    target_subject
                ).lower()
            ):
                subject_score = 1.0

            # ----------------------------------------------------
            # MEMORY TYPE
            # ----------------------------------------------------

            memory_type = str(
                candidate.get(
                    "memory_type",
                    "",
                )
            ).lower()

            semantic_bonus = 0.0

            if (
                query_intent.get("type")
                in {
                    "preference",
                    "general_recall",
                }
                and memory_type == "semantic"
            ):
                semantic_bonus = 0.35

            # ----------------------------------------------------
            # CONFIDENCE
            # ----------------------------------------------------

            confidence = self._safe_float(
                candidate.get(
                    "confidence",
                    0.0,
                )
            )

            confidence_bonus = (
                confidence * 0.15
            )

            # ----------------------------------------------------
            # COMBINED SCORE
            # ----------------------------------------------------

            combined_score = (
                existing_score * 0.55
                + lexical_score * 0.15
                + predicate_score * 1.50
                + subject_score * 0.25
                + semantic_bonus
                + confidence_bonus
            )

            item = dict(candidate)

            item["retrieval_score"] = (
                combined_score
            )

            scored.append(item)

        scored.sort(
            key=lambda item: item.get(
                "retrieval_score",
                0.0,
            ),
            reverse=True,
        )

        return self._remove_duplicates(
            scored
        )

    # ============================================================
    # SEARCH TEXT
    # ============================================================

    @staticmethod
    def _extract_search_text(
        item: Dict[str, Any],
    ) -> str:
        """
        Extract searchable text from a memory record.
        """

        fields = (
            "content",
            "text",
            "description",
            "summary",
            "message",
            "fact",
            "subject",
            "predicate",
            "value",
            "category",
            "source",
        )

        parts: List[str] = []

        for key in fields:

            value = item.get(key)

            if value is None:
                continue

            parts.append(
                str(value)
            )

        return " ".join(parts)

    # ============================================================
    # QUERY NORMALIZATION
    # ============================================================

    @staticmethod
    def _normalize_query(
        query: str,
    ) -> str:
        """
        Normalize a query for deterministic intent matching.
        """

        text = str(query).lower().strip()

        text = re.sub(
            r"[^\w\s']",
            " ",
            text,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # ============================================================
    # TOKENIZATION
    # ============================================================

    @staticmethod
    def _tokenize(
        text: str,
    ) -> set[str]:
        """
        Convert text into normalized lexical tokens.
        """

        normalized = MemoryRetriever._normalize_query(
            text
        )

        if not normalized:
            return set()

        return set(
            normalized.split()
        )

    # ============================================================
    # CONCEPT EXTRACTION
    # ============================================================

    @staticmethod
    def _extract_concepts(
        query: str,
    ) -> List[str]:
        """
        Extract useful concept words from a query.

        Common conversational filler is ignored.
        """

        stop_words = {
            "what",
            "do",
            "does",
            "did",
            "i",
            "you",
            "me",
            "my",
            "your",
            "about",
            "the",
            "a",
            "an",
            "is",
            "are",
            "am",
            "to",
            "of",
            "and",
            "or",
            "that",
            "this",
            "these",
            "those",
            "remember",
            "know",
            "tell",
            "please",
        }

        tokens = MemoryRetriever._tokenize(
            query
        )

        return [
            token
            for token in tokens
            if token not in stop_words
        ]

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

        unique: List[Dict[str, Any]] = []

        for result in results:

            memory_id = result.get(
                "id"
            )

            if memory_id is not None:

                key = (
                    result.get(
                        "memory_type"
                    ),
                    str(memory_id),
                )

            else:

                key = (
                    result.get(
                        "memory_type"
                    ),
                    MemoryRetriever._extract_search_text(
                        result
                    ).strip().lower(),
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

        except (
            TypeError,
            ValueError,
        ):

            return 0.0