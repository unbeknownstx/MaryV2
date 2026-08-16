"""
MaryV2 Semantic Memory

Stores durable facts, concepts, and knowledge that Mary has learned.

Semantic memory is different from episodic memory:

    Episodic:
        "The creator told me yesterday that he likes X."

    Semantic:
        "The creator likes X."

Semantic memory is responsible for:
    - storing durable facts
    - preventing exact duplicates
    - finding exact facts
    - semantic-aware natural-language retrieval
    - confidence-aware ranking

Higher-level decisions about what should become semantic memory
belong to the memory-management / consolidation layer.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional


class SemanticMemory:
    """
    In-memory representation of durable semantic knowledge.

    Persistence can be handled by the MemoryManager/storage layer.
    """

    def __init__(self) -> None:
        self.memories: list[dict[str, Any]] = []

    # ============================================================
    # ADD
    # ============================================================

    def add(
        self,
        subject: str,
        predicate: str,
        value: Any,
        *,
        confidence: float = 1.0,
        source: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Add a semantic fact.

        Exact duplicate facts are not stored twice.
        """

        if not subject or not str(subject).strip():
            raise ValueError("subject cannot be empty")

        if not predicate or not str(predicate).strip():
            raise ValueError("predicate cannot be empty")

        subject = str(subject).strip()
        predicate = str(predicate).strip()

        confidence = self._clamp_confidence(
            confidence
        )

        existing = self._find_exact(
            subject=subject,
            predicate=predicate,
            value=value,
        )

        if existing is not None:
            existing["confidence"] = max(
                self._clamp_confidence(
                    existing.get(
                        "confidence",
                        0.0,
                    )
                ),
                confidence,
            )

            if source is not None:
                existing["source"] = source

            existing["updated_at"] = (
                datetime.now().isoformat()
            )

            return existing

        now = datetime.now().isoformat()

        memory = {
            "id": self._next_id(),
            "subject": subject,
            "predicate": predicate,
            "value": value,
            "confidence": confidence,
            "source": source,
            "created_at": now,
            "updated_at": now,
        }

        self.memories.append(memory)

        return memory

    # ============================================================
    # FIND
    # ============================================================

    def find(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        value: Any = None,
    ) -> list[dict[str, Any]]:
        """
        Find semantic memories matching supplied fields.
        """

        results: list[dict[str, Any]] = []

        for memory in self.memories:
            if subject is not None:
                if not self._text_equal(
                    memory.get("subject"),
                    subject,
                ):
                    continue

            if predicate is not None:
                if not self._text_equal(
                    memory.get("predicate"),
                    predicate,
                ):
                    continue

            if value is not None:
                if memory.get("value") != value:
                    continue

            results.append(memory)

        return results

    # ============================================================
    # SEARCH
    # ============================================================

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search semantic memory using natural language.

        Results contain a score field used by MemoryRetriever.
        """

        if not query or not str(query).strip():
            return []

        if limit <= 0:
            return []

        query = str(query).strip()
        query_lower = query.lower()

        query_words = self._tokenize(
            query_lower
        )

        requested_predicates = (
            self._detect_predicates(
                query_lower
            )
        )

        requested_subjects = (
            self._detect_subjects(
                query_lower
            )
        )

        scored: list[dict[str, Any]] = []

        for memory in self.memories:
            score = self._score_memory(
                memory=memory,
                query=query_lower,
                query_words=query_words,
                requested_predicates=requested_predicates,
                requested_subjects=requested_subjects,
            )

            if score <= 0.0:
                continue

            result = dict(memory)
            result["score"] = score

            scored.append(result)

        scored.sort(
            key=lambda item: (
                item.get(
                    "score",
                    0.0,
                ),
                item.get(
                    "confidence",
                    0.0,
                ),
            ),
            reverse=True,
        )

        return scored[:limit]

    # ============================================================
    # RETRIEVE
    # ============================================================

    def retrieve(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Alias for search().
        """

        return self.search(
            query=query,
            limit=limit,
        )

    # ============================================================
    # GET
    # ============================================================

    def get(
        self,
        memory_id: str,
    ) -> Optional[dict[str, Any]]:
        """
        Return one semantic memory by ID.
        """

        for memory in self.memories:
            if memory.get("id") == memory_id:
                return memory

        return None

    # ============================================================
    # UPDATE
    # ============================================================

    def update(
        self,
        memory_id: str,
        **changes: Any,
    ) -> Optional[dict[str, Any]]:
        """
        Update an existing semantic memory.
        """

        memory = self.get(
            memory_id
        )

        if memory is None:
            return None

        allowed_fields = {
            "subject",
            "predicate",
            "value",
            "confidence",
            "source",
        }

        for key, value in changes.items():
            if key not in allowed_fields:
                continue

            if key in {
                "subject",
                "predicate",
            }:
                if value is None:
                    continue

                value = str(
                    value
                ).strip()

                if not value:
                    continue

            if key == "confidence":
                value = (
                    self._clamp_confidence(
                        value
                    )
                )

            memory[key] = value

        memory["updated_at"] = (
            datetime.now().isoformat()
        )

        return memory

    # ============================================================
    # REMOVE
    # ============================================================

    def remove(
        self,
        memory_id: str,
    ) -> bool:
        """
        Remove a semantic memory by ID.
        """

        for index, memory in enumerate(
            self.memories
        ):
            if memory.get("id") == memory_id:
                del self.memories[index]
                return True

        return False

    # ============================================================
    # ALL
    # ============================================================

    def all(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return all semantic memories.
        """

        return list(
            self.memories
        )

    # ============================================================
    # COUNT
    # ============================================================

    def count(self) -> int:
        """
        Return number of semantic memories.
        """

        return len(
            self.memories
        )

    # ============================================================
    # CLEAR
    # ============================================================

    def clear(self) -> None:
        """
        Clear all semantic memories.
        """

        self.memories.clear()

    # ============================================================
    # SCORING
    # ============================================================

    def _score_memory(
        self,
        memory: dict[str, Any],
        query: str,
        query_words: set[str],
        requested_predicates: set[str],
        requested_subjects: set[str],
    ) -> float:
        """
        Calculate semantic relevance.

        Predicate meaning is intentionally weighted heavily.
        """

        subject = str(
            memory.get(
                "subject",
                "",
            )
        ).lower()

        predicate = str(
            memory.get(
                "predicate",
                "",
            )
        ).lower()

        value = str(
            memory.get(
                "value",
                "",
            )
        ).lower()

        searchable_text = " ".join(
            [
                subject,
                predicate,
                value,
            ]
        )

        content_words = self._tokenize(
            searchable_text
        )

        score = 0.0

        # --------------------------------------------------------
        # VALUE MATCH
        # --------------------------------------------------------

        if value and value in query:
            score += 0.75

        # --------------------------------------------------------
        # PREDICATE MATCH
        # --------------------------------------------------------

        if requested_predicates:
            if predicate in requested_predicates:
                score += 1.50
            else:
                score -= 0.75

        # --------------------------------------------------------
        # SUBJECT MATCH
        # --------------------------------------------------------

        if requested_subjects:
            if subject in requested_subjects:
                score += 0.50

        # --------------------------------------------------------
        # LEXICAL OVERLAP
        # --------------------------------------------------------

        if (
            query_words
            and content_words
        ):
            overlap = (
                query_words
                .intersection(
                    content_words
                )
            )

            if overlap:
                lexical_score = (
                    len(overlap)
                    / max(
                        len(query_words),
                        1,
                    )
                )

                score += (
                    lexical_score
                    * 0.50
                )

        # --------------------------------------------------------
        # NEGATIVE PREFERENCE
        # --------------------------------------------------------

        if self._is_dislike_query(
            query
        ):
            if predicate == "dislikes":
                score += 1.50

            elif predicate in {
                "likes",
                "loves",
                "enjoys",
                "prefers",
            }:
                score -= 1.25

        # --------------------------------------------------------
        # POSITIVE PREFERENCE
        # --------------------------------------------------------

        elif self._is_like_query(
            query
        ):
            if predicate in {
                "likes",
                "loves",
                "enjoys",
                "prefers",
            }:
                score += 1.50

            elif predicate == "dislikes":
                score -= 1.25

        # --------------------------------------------------------
        # CONFIDENCE
        # --------------------------------------------------------

        confidence = (
            self._clamp_confidence(
                memory.get(
                    "confidence",
                    0.0,
                )
            )
        )

        if score > 0:
            score *= (
                0.75
                + (
                    0.25
                    * confidence
                )
            )

        return max(
            0.0,
            min(
                3.0,
                score,
            ),
        )

    # ============================================================
    # QUERY INTERPRETATION
    # ============================================================

    @staticmethod
    def _detect_predicates(
        query: str,
    ) -> set[str]:
        """
        Detect semantic predicates from natural language.

        Negative preference queries are checked first.
        """

        query = str(
            query
        ).strip().lower()

        negative_patterns = (
            r"\bdon't\b.*\blike\b",
            r"\bdo not\b.*\blike\b",
            r"\bdoesn't\b.*\blike\b",
            r"\bdoes not\b.*\blike\b",
            r"\bdislike\b",
            r"\bdislikes\b",
            r"\bhate\b",
            r"\bhates\b",
        )

        if any(
            re.search(
                pattern,
                query,
            )
            for pattern in negative_patterns
        ):
            return {
                "dislikes"
            }

        positive_patterns = (
            r"\bwhat do i like\b",
            r"\bwhat i like\b",
            r"\bwhat does the creator like\b",
            r"\bwhat does he like\b",
            r"\bwhat does she like\b",
            r"\bwhat do you like\b",
        )

        if any(
            re.search(
                pattern,
                query,
            )
            for pattern in positive_patterns
        ):
            return {
                "likes",
                "loves",
                "enjoys",
                "prefers",
            }

        love_patterns = (
            r"\bwhat do i love\b",
            r"\bwhat does the creator love\b",
            r"\bwhat does he love\b",
            r"\bwhat does she love\b",
        )

        if any(
            re.search(
                pattern,
                query,
            )
            for pattern in love_patterns
        ):
            return {
                "loves"
            }

        return set()

    @staticmethod
    def _detect_subjects(
        query: str,
    ) -> set[str]:
        """
        Detect likely semantic subjects.
        """

        query = str(
            query
        ).strip().lower()

        subjects: set[str] = set()

        if (
            "creator" in query
            or "my creator" in query
        ):
            subjects.add(
                "creator"
            )

        if "mary" in query:
            subjects.add(
                "mary"
            )

        return subjects

    @staticmethod
    def _is_dislike_query(
        query: str,
    ) -> bool:
        """
        Determine whether the query asks about dislikes.
        """

        query = str(
            query
        ).strip().lower()

        patterns = (
            r"\bdon't\b.*\blike\b",
            r"\bdo not\b.*\blike\b",
            r"\bdoesn't\b.*\blike\b",
            r"\bdoes not\b.*\blike\b",
            r"\bdislike\b",
            r"\bdislikes\b",
            r"\bhate\b",
            r"\bhates\b",
        )

        return any(
            re.search(
                pattern,
                query,
            )
            for pattern in patterns
        )

    @staticmethod
    def _is_like_query(
        query: str,
    ) -> bool:
        """
        Determine whether the query asks about positive preferences.
        """

        query = str(
            query
        ).lower()

        return (
            "what do i like" in query
            or "what i like" in query
            or "what does the creator like" in query
            or "what do you like" in query
        )

    # ============================================================
    # EXACT MATCH
    # ============================================================

    def _find_exact(
        self,
        subject: str,
        predicate: str,
        value: Any,
    ) -> Optional[dict[str, Any]]:
        """
        Find an existing fact with the same semantic identity.
        """

        for memory in self.memories:
            if not self._text_equal(
                memory.get("subject"),
                subject,
            ):
                continue

            if not self._text_equal(
                memory.get("predicate"),
                predicate,
            ):
                continue

            if memory.get("value") != value:
                continue

            return memory

        return None

    # ============================================================
    # TOKENIZATION
    # ============================================================

    @staticmethod
    def _tokenize(
        text: str,
    ) -> set[str]:
        """
        Normalize text into searchable tokens.
        """

        if not text:
            return set()

        return {
            token.lower()
            for token in re.findall(
                r"[a-zA-Z0-9']+",
                str(text),
            )
            if token.strip()
        }

    # ============================================================
    # TEXT COMPARISON
    # ============================================================

    @staticmethod
    def _text_equal(
        left: Any,
        right: Any,
    ) -> bool:
        """
        Case-insensitive text comparison.
        """

        if left is None or right is None:
            return False

        return (
            str(left)
            .strip()
            .lower()
            ==
            str(right)
            .strip()
            .lower()
        )

    # ============================================================
    # ID GENERATION
    # ============================================================

    def _next_id(
        self,
    ) -> str:
        """
        Generate the next semantic memory ID.
        """

        highest = 0

        for memory in self.memories:
            memory_id = str(
                memory.get(
                    "id",
                    "",
                )
            )

            if not memory_id.startswith(
                "semantic_"
            ):
                continue

            try:
                number = int(
                    memory_id.split(
                        "_"
                    )[-1]
                )

                highest = max(
                    highest,
                    number,
                )

            except ValueError:
                continue

        return (
            f"semantic_{highest + 1}"
        )

    # ============================================================
    # CONFIDENCE
    # ============================================================

    @staticmethod
    def _clamp_confidence(
        value: float,
    ) -> float:
        """
        Keep confidence between 0.0 and 1.0.
        """

        try:
            value = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            value = 1.0

        return max(
            0.0,
            min(
                1.0,
                value,
            ),
        )