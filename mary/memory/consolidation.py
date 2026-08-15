"""
MaryV2 - Memory Consolidation

Memory consolidation converts experiences into durable knowledge.

Architecture:

    Episodic / Working Memory
              |
              v
       Memory Consolidator
              |
              v
        Semantic Memory

The consolidator does NOT own memory storage.

Its responsibilities are:

    1. Find memories worth preserving.
    2. Normalize memory content.
    3. Extract durable semantic structure when possible.
    4. Create consolidation candidates.
    5. Promote candidates into semantic memory.
    6. Prevent duplicate semantic promotion.

V2 intentionally uses deterministic rules.

Future versions can add:

    - repetition analysis
    - emotional significance
    - relationship significance
    - goal relevance
    - novelty
    - contradiction detection
    - temporal reasoning
    - LLM-assisted semantic extraction
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class MemoryConsolidator:
    """
    Coordinates conversion of temporary/episodic experience
    into durable semantic knowledge.
    """

    def __init__(
        self,
        episodic_memory=None,
        semantic_memory=None,
        working_memory=None,
        retrieval=None,
    ) -> None:

        self.episodic_memory = episodic_memory
        self.semantic_memory = semantic_memory
        self.working_memory = working_memory
        self.retrieval = retrieval

    # ============================================================
    # PUBLIC API
    # ============================================================

    def consolidate(self) -> list[dict[str, Any]]:
        """
        Review available memories and return consolidation candidates.

        Memories are never removed or modified here.
        """

        memories = self._collect_memories()

        if not memories:
            return []

        candidates: list[dict[str, Any]] = []

        for memory in memories:

            if not isinstance(memory, dict):
                continue

            if not self._should_consolidate(memory):
                continue

            candidate = self._create_candidate(memory)

            if candidate is not None:
                candidates.append(candidate)

        return candidates

    def consolidate_memory(
        self,
        memory: Any,
    ) -> dict[str, Any] | None:
        """
        Evaluate one memory and create a consolidation candidate.
        """

        normalized = self._normalize_memory(memory)

        if normalized is None:
            return None

        if not self._should_consolidate(normalized):
            return None

        return self._create_candidate(normalized)

    # ============================================================
    # PROMOTION
    # ============================================================

    def promote(
        self,
        candidate: dict[str, Any],
    ) -> bool:
        """
        Promote one consolidation candidate into semantic memory.

        Duplicate semantic facts are not inserted again.
        """

        if not isinstance(candidate, dict):
            return False

        if self.semantic_memory is None:
            return False

        content = candidate.get("content")

        if not content:
            return False

        metadata = candidate.get(
            "metadata",
            {},
        )

        if not isinstance(metadata, dict):
            metadata = {}

        subject = candidate.get(
            "subject",
            metadata.get(
                "subject",
                "mary",
            ),
        )

        predicate = candidate.get(
            "predicate",
            metadata.get(
                "predicate",
                "remembers",
            ),
        )

        value = candidate.get(
            "value",
            metadata.get(
                "value",
                content,
            ),
        )

        confidence = self._safe_float(
            metadata.get(
                "confidence",
                metadata.get(
                    "importance",
                    0.5,
                ),
            )
        )

        source = metadata.get(
            "source",
            "memory_consolidation",
        )

        # --------------------------------------------------------
        # DUPLICATE PROTECTION
        # --------------------------------------------------------

        if self._semantic_exists(
            subject=subject,
            predicate=predicate,
            value=value,
        ):
            return False

        try:

            self.semantic_memory.add(
                subject=str(subject),
                predicate=str(predicate),
                value=value,
                confidence=confidence,
                source=source,
            )

            return True

        except Exception as error:

            print(
                f"[CONSOLIDATION] Promotion error: {error}"
            )

            return False

    def consolidate_and_promote(self) -> int:
        """
        Consolidate eligible memories and promote them.

        Returns the number of newly promoted memories.
        """

        candidates = self.consolidate()

        promoted = 0

        for candidate in candidates:

            if self.promote(candidate):
                promoted += 1

        return promoted

    # ============================================================
    # COLLECTION
    # ============================================================

    def _collect_memories(
        self,
    ) -> list[dict[str, Any]]:
        """
        Collect memories from episodic and working memory.
        """

        memories: list[dict[str, Any]] = []

        if self.episodic_memory is not None:

            memories.extend(
                self._extract_memories(
                    self.episodic_memory,
                    "episodic",
                )
            )

        if self.working_memory is not None:

            memories.extend(
                self._extract_memories(
                    self.working_memory,
                    "working",
                )
            )

        return memories

    def _extract_memories(
        self,
        memory_system: Any,
        memory_type: str,
    ) -> list[dict[str, Any]]:
        """
        Extract memories from a memory system.

        Supports list-returning memory APIs and object/dataclass
        memory representations.
        """

        methods = (
            "all",
            "get_all",
            "get_memories",
            "list_memories",
        )

        for method_name in methods:

            method = getattr(
                memory_system,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method()

            except Exception as error:

                print(
                    f"[CONSOLIDATION] "
                    f"{memory_type} collection error: {error}"
                )

                return []

            if result is None:
                return []

            if not isinstance(
                result,
                (list, tuple),
            ):
                result = [result]

            normalized: list[
                dict[str, Any]
            ] = []

            for item in result:

                memory = self._normalize_memory(
                    item,
                    memory_type=memory_type,
                )

                if memory is not None:
                    normalized.append(memory)

            return normalized

        return []

    # ============================================================
    # NORMALIZATION
    # ============================================================

    def _normalize_memory(
        self,
        memory: Any,
        memory_type: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Convert a memory object into a dictionary representation.
        """

        if memory is None:
            return None

        if isinstance(memory, dict):

            result = dict(memory)

        elif hasattr(memory, "to_dict"):

            try:

                result = memory.to_dict()

            except Exception:
                return None

            if not isinstance(
                result,
                dict,
            ):
                return None

        elif hasattr(memory, "__dict__"):

            try:

                result = dict(
                    vars(memory)
                )

            except Exception:
                return None

        else:
            return None

        if memory_type is not None:

            result.setdefault(
                "type",
                memory_type,
            )

            result.setdefault(
                "memory_type",
                memory_type,
            )

        # Normalize content where possible.
        if "content" in result:

            result["content"] = self._normalize_content(
                result["content"]
            )

        return result

    # ============================================================
    # CONTENT NORMALIZATION
    # ============================================================

    @staticmethod
    def _normalize_content(
        content: Any,
    ) -> str:
        """
        Normalize remembered text.

        Examples:

            "that I love anime"
                -> "I love anime"

            "That I love anime"
                -> "I love anime"

            "I love anime"
                -> "I love anime"
        """

        if content is None:
            return ""

        text = str(content).strip()

        if not text:
            return ""

        lowered = text.lower()

        if lowered.startswith("that "):

            text = text[5:].strip()

        return text

    # ============================================================
    # CONSOLIDATION DECISION
    # ============================================================

    def _should_consolidate(
        self,
        memory: dict[str, Any],
    ) -> bool:
        """
        Determine whether a memory is important enough
        to become durable knowledge.
        """

        content = memory.get(
            "content"
        )

        if content is None:
            return False

        if not str(content).strip():
            return False

        # Explicit request.
        if memory.get(
            "consolidate"
        ) is True:

            return True

        # Explicit importance.
        if memory.get(
            "important"
        ) is True:

            return True

        # Importance score.
        importance = self._safe_float(
            memory.get(
                "importance",
                0.0,
            )
        )

        if importance >= 0.7:
            return True

        # Emotional significance.
        emotional_weight = self._safe_float(
            memory.get(
                "emotional_weight",
                memory.get(
                    "emotional_importance",
                    0.0,
                ),
            )
        )

        if emotional_weight >= 0.7:
            return True

        # Repetition/access frequency.
        repetition = self._safe_int(
            memory.get(
                "repetition",
                memory.get(
                    "access_count",
                    0,
                ),
            )
        )

        if repetition >= 3:
            return True

        return False

    # ============================================================
    # CANDIDATE CREATION
    # ============================================================

    def _create_candidate(
        self,
        memory: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Convert an eligible memory into a consolidation candidate.
        """

        raw_content = memory.get(
            "content"
        )

        if raw_content is None:
            return None

        content = self._normalize_content(
            raw_content
        )

        if not content:
            return None

        memory_type = memory.get(
            "memory_type",
            memory.get(
                "type",
                "episodic",
            ),
        )

        importance = self._safe_float(
            memory.get(
                "importance",
                0.0,
            )
        )

        emotional_weight = self._safe_float(
            memory.get(
                "emotional_weight",
                memory.get(
                    "emotional_importance",
                    0.0,
                ),
            )
        )

        metadata = {
            "source": "memory_consolidation",
            "memory_type": memory_type,
            "importance": importance,
            "emotional_weight": emotional_weight,
            "tags": memory.get(
                "tags",
                [],
            ),
        }

        # --------------------------------------------------------
        # SEMANTIC EXTRACTION
        # --------------------------------------------------------

        semantic = self._extract_semantic_fact(
            content
        )

        if semantic is not None:

            subject = semantic["subject"]
            predicate = semantic["predicate"]
            value = semantic["value"]

            metadata.update(
                {
                    "subject": subject,
                    "predicate": predicate,
                    "value": value,
                    "semantic_extraction": "deterministic_v2",
                }
            )

        else:

            # Preserve explicit semantic structure if the source
            # memory already contains one.
            for key in (
                "subject",
                "predicate",
                "value",
                "confidence",
            ):

                if key in memory:
                    metadata[key] = memory[key]

        confidence = self._safe_float(
            memory.get(
                "confidence",
                importance,
            )
        )

        metadata.setdefault(
            "confidence",
            confidence,
        )

        candidate = {
            "type": "consolidation_candidate",
            "content": content,
            "source_memory_id": memory.get(
                "id"
            ),
            "created_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "metadata": metadata,
        }

        # --------------------------------------------------------
        # EXPOSE SEMANTIC FIELDS
        # --------------------------------------------------------

        if "subject" in metadata:

            candidate["subject"] = metadata[
                "subject"
            ]

        if "predicate" in metadata:

            candidate["predicate"] = metadata[
                "predicate"
            ]

        if "value" in metadata:

            candidate["value"] = metadata[
                "value"
            ]

        return candidate

    # ============================================================
    # SEMANTIC EXTRACTION
    # ============================================================

    def _extract_semantic_fact(
        self,
        content: str,
    ) -> dict[str, Any] | None:
        """
        Extract a simple durable fact from natural-language memory.

        V2 deliberately uses deterministic patterns.

        Examples:

            "I don't like shrimp"
                -> creator / dislikes / shrimp

            "I love anime"
                -> creator / likes / anime

            "I like pizza"
                -> creator / likes / pizza

            "I hate spiders"
                -> creator / dislikes / spiders

        Returns None when no safe deterministic interpretation
        can be made.
        """

        text = content.strip()

        if not text:
            return None

        lowered = text.lower()

        # --------------------------------------------------------
        # NEGATIVE PREFERENCE
        # --------------------------------------------------------

        negative_prefixes = (
            "i don't like ",
            "i do not like ",
            "i dislike ",
            "i hate ",
            "i can't stand ",
            "i cannot stand ",
        )

        for prefix in negative_prefixes:

            if lowered.startswith(prefix):

                value = text[len(prefix):].strip()

                if not value:
                    return None

                return {
                    "subject": "creator",
                    "predicate": "dislikes",
                    "value": value,
                }

        # --------------------------------------------------------
        # POSITIVE PREFERENCE
        # --------------------------------------------------------

        positive_prefixes = (
            "i like ",
            "i love ",
            "i enjoy ",
            "i prefer ",
        )

        for prefix in positive_prefixes:

            if lowered.startswith(prefix):

                value = text[len(prefix):].strip()

                if not value:
                    return None

                return {
                    "subject": "creator",
                    "predicate": "likes",
                    "value": value,
                }

        return None

    # ============================================================
    # DUPLICATE DETECTION
    # ============================================================

    def _semantic_exists(
        self,
        subject: Any,
        predicate: Any,
        value: Any,
    ) -> bool:
        """
        Determine whether an equivalent semantic fact already exists.
        """

        if self.semantic_memory is None:
            return False

        try:

            existing = self.semantic_memory.all()

        except Exception:
            return False

        if not existing:
            return False

        normalized_subject = str(
            subject
        ).strip().lower()

        normalized_predicate = str(
            predicate
        ).strip().lower()

        normalized_value = str(
            value
        ).strip().lower()

        for item in existing:

            if not isinstance(item, dict):
                continue

            existing_subject = str(
                item.get(
                    "subject",
                    "",
                )
            ).strip().lower()

            existing_predicate = str(
                item.get(
                    "predicate",
                    "",
                )
            ).strip().lower()

            existing_value = str(
                item.get(
                    "value",
                    "",
                )
            ).strip().lower()

            if (
                existing_subject
                == normalized_subject
                and existing_predicate
                == normalized_predicate
                and existing_value
                == normalized_value
            ):

                return True

        return False

    # ============================================================
    # CANDIDATE COUNT
    # ============================================================

    def count_candidates(
        self,
    ) -> int:
        """
        Return the number of memories currently eligible
        for consolidation.
        """

        return len(
            self.consolidate()
        )

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

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

    @staticmethod
    def _safe_int(
        value: Any,
    ) -> int:
        """
        Safely convert a value to integer.
        """

        try:

            return int(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0