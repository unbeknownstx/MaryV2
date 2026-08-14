"""
MaryV2 - Memory Consolidation

Consolidation reviews Mary's temporary and episodic experiences and
identifies information that is important enough to become durable knowledge.

Consolidation does not own memory storage.

It coordinates:
    - episodic memory
    - working memory
    - semantic memory

The actual storage behavior remains inside each memory system.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class MemoryConsolidator:
    """
    Reviews memories and creates candidates for long-term retention.

    V2 uses deterministic rules for now.

    Future versions can incorporate:
        - repetition
        - emotional significance
        - relationship significance
        - goal relevance
        - novelty
        - contradiction detection
        - LLM evaluation
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

        Memories are not removed or modified by this operation.
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

            candidate = self._create_candidate(
                memory
            )

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

        normalized = self._normalize_memory(
            memory
        )

        if normalized is None:
            return None

        if not self._should_consolidate(
            normalized
        ):
            return None

        return self._create_candidate(
            normalized
        )

    # ============================================================
    # PROMOTION
    # ============================================================

    def promote(
        self,
        candidate: dict[str, Any],
    ) -> bool:
        """
        Promote a consolidation candidate into semantic memory.

        Semantic memory stores facts as:

            subject
            predicate
            value

        When a candidate does not contain an explicit semantic
        structure, Mary stores the experience as a durable fact
        describing that Mary remembers the information.
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

        confidence = metadata.get(
            "confidence",
            metadata.get(
                "importance",
                0.5,
            ),
        )

        source = metadata.get(
            "source",
            "memory_consolidation",
        )

        try:

            self.semantic_memory.add(
                subject=str(subject),
                predicate=str(predicate),
                value=value,
                confidence=float(confidence),
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

        Returns the number of successfully promoted memories.
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

        Supports both dictionary-based memory and dataclass/object
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
                    normalized.append(
                        memory
                    )

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
        Convert a memory object into the dictionary representation
        used internally by the consolidation system.
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

        return result

    # ============================================================
    # CONSOLIDATION DECISION
    # ============================================================

    def _should_consolidate(
        self,
        memory: dict[str, Any],
    ) -> bool:
        """
        Determine whether a memory is important enough to preserve.
        """

        content = memory.get(
            "content"
        )

        if content is None:
            return False

        if not str(content).strip():
            return False

        # Explicit request to consolidate.
        if memory.get(
            "consolidate"
        ) is True:

            return True

        # Explicitly marked important.
        if memory.get(
            "important"
        ) is True:

            return True

        # Standard importance score.
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

        # Repeated/accessed memories.
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
        Convert a memory into a consolidation candidate.
        """

        content = memory.get(
            "content"
        )

        if content is None:
            return None

        content = str(
            content
        ).strip()

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

        # Preserve semantic structure if the source memory
        # already contains it.
        for key in (
            "subject",
            "predicate",
            "value",
            "confidence",
        ):

            if key in memory:

                metadata[key] = memory[key]

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

        # Expose semantic fields at the candidate level as well.
        if "subject" in memory:
            candidate["subject"] = memory[
                "subject"
            ]

        if "predicate" in memory:
            candidate["predicate"] = memory[
                "predicate"
            ]

        if "value" in memory:
            candidate["value"] = memory[
                "value"
            ]

        return candidate

    # ============================================================
    # UTILITY
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

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> float:
        """Safely convert a value to float."""

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
        """Safely convert a value to integer."""

        try:

            return int(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0