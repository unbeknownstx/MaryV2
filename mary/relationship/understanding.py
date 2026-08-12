"""
MaryV2 - Relationship Understanding

Maintains Mary's evolving understanding of her creator.

Important distinction:

    UserModel
        Stores structured information Mary currently believes
        about her creator.

    RelationshipUnderstanding
        Stores observations, inferences, patterns, confidence,
        and supporting evidence used to develop that model.

Understanding should be allowed to change as Mary receives new
evidence. It should not blindly turn every observation into a fact.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


class RelationshipUnderstanding:
    """
    Maintains evolving knowledge and inferences about Mary's creator.
    """

    def __init__(
        self,
        user_model=None,
        history=None,
    ):
        self.user_model = user_model
        self.history = history

        self.observations: List[Dict[str, Any]] = []
        self.inferences: List[Dict[str, Any]] = []
        self.patterns: List[Dict[str, Any]] = []

        self.updated_at = datetime.now().isoformat()

    # ============================================================
    # OBSERVATIONS
    # ============================================================

    def add_observation(
        self,
        observation: str,
        *,
        category: str = "general",
        source: str = "conversation",
        confidence: float = 0.5,
        evidence: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record something Mary observed about her creator.

        Observations are not automatically treated as permanent facts.
        """

        if not observation:
            raise ValueError(
                "Observation cannot be empty."
            )

        confidence = self._clamp_confidence(
            confidence
        )

        item = {
            "id": self._new_id("observation"),
            "observation": str(
                observation
            ).strip(),
            "category": str(category),
            "source": str(source),
            "confidence": confidence,
            "evidence": evidence,
            "created_at": datetime.now().isoformat(),
        }

        self.observations.append(
            item
        )

        self._touch()

        return item

    def get_observations(
        self,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return observations, optionally filtered by category.
        """

        if category is None:
            return list(
                self.observations
            )

        return [
            item
            for item in self.observations
            if item.get("category") == category
        ]

    # ============================================================
    # INFERENCES
    # ============================================================

    def add_inference(
        self,
        statement: str,
        *,
        category: str = "general",
        confidence: float = 0.5,
        evidence_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Record an inference Mary has made from observations.

        Inferences are explicitly separate from facts because they
        may be wrong and should remain revisable.
        """

        if not statement:
            raise ValueError(
                "Inference cannot be empty."
            )

        confidence = self._clamp_confidence(
            confidence
        )

        item = {
            "id": self._new_id("inference"),
            "statement": str(
                statement
            ).strip(),
            "category": str(category),
            "confidence": confidence,
            "evidence_ids": list(
                evidence_ids or []
            ),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        self.inferences.append(
            item
        )

        self._touch()

        return item

    def update_inference(
        self,
        inference_id: str,
        *,
        statement: Optional[str] = None,
        confidence: Optional[float] = None,
        evidence_ids: Optional[List[str]] = None,
    ) -> bool:
        """
        Update an existing inference.
        """

        inference = self.get_inference(
            inference_id
        )

        if inference is None:
            return False

        if statement is not None:
            if not str(statement).strip():
                return False

            inference["statement"] = str(
                statement
            ).strip()

        if confidence is not None:
            inference["confidence"] = (
                self._clamp_confidence(
                    confidence
                )
            )

        if evidence_ids is not None:
            inference["evidence_ids"] = list(
                evidence_ids
            )

        inference["updated_at"] = (
            datetime.now().isoformat()
        )

        self._touch()

        return True

    def get_inference(
        self,
        inference_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find an inference by ID.
        """

        for item in self.inferences:
            if item.get("id") == inference_id:
                return item

        return None

    def get_inferences(
        self,
        category: Optional[str] = None,
        *,
        minimum_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Return inferences meeting the requested confidence level.
        """

        minimum_confidence = self._clamp_confidence(
            minimum_confidence
        )

        results = []

        for item in self.inferences:

            if category is not None:
                if item.get("category") != category:
                    continue

            if item.get(
                "confidence",
                0.0,
            ) < minimum_confidence:
                continue

            results.append(
                item
            )

        return results

    # ============================================================
    # PATTERNS
    # ============================================================

    def add_pattern(
        self,
        pattern: str,
        *,
        category: str = "general",
        confidence: float = 0.5,
        frequency: int = 1,
    ) -> Dict[str, Any]:
        """
        Record a recurring pattern in the creator's behavior,
        preferences, communication, or interests.
        """

        if not pattern:
            raise ValueError(
                "Pattern cannot be empty."
            )

        confidence = self._clamp_confidence(
            confidence
        )

        item = {
            "id": self._new_id("pattern"),
            "pattern": str(
                pattern
            ).strip(),
            "category": str(category),
            "confidence": confidence,
            "frequency": max(
                1,
                int(frequency),
            ),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        self.patterns.append(
            item
        )

        self._touch()

        return item

    def reinforce_pattern(
        self,
        pattern_id: str,
        *,
        confidence_delta: float = 0.05,
    ) -> bool:
        """
        Increase the strength of an existing pattern.

        Confidence is capped at 1.0.
        """

        for item in self.patterns:

            if item.get("id") != pattern_id:
                continue

            item["frequency"] = (
                int(
                    item.get(
                        "frequency",
                        1,
                    )
                ) + 1
            )

            current = float(
                item.get(
                    "confidence",
                    0.0,
                )
            )

            item["confidence"] = (
                self._clamp_confidence(
                    current + confidence_delta
                )
            )

            item["updated_at"] = (
                datetime.now().isoformat()
            )

            self._touch()

            return True

        return False

    def get_patterns(
        self,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return known recurring patterns.
        """

        if category is None:
            return list(
                self.patterns
            )

        return [
            item
            for item in self.patterns
            if item.get("category") == category
        ]

    # ============================================================
    # USER MODEL INTEGRATION
    # ============================================================

    def promote_fact(
        self,
        key: str,
        value: Any,
        *,
        confidence: float = 1.0,
        minimum_confidence: float = 0.7,
    ) -> bool:
        """
        Promote information into the structured UserModel.

        This creates a deliberate boundary between:

            observation → inference → structured understanding

        Low-confidence information is not automatically promoted.
        """

        confidence = self._clamp_confidence(
            confidence
        )

        if confidence < minimum_confidence:
            return False

        if self.user_model is None:
            return False

        setter = getattr(
            self.user_model,
            "set_fact",
            None,
        )

        if not callable(setter):
            return False

        setter(
            key,
            value,
        )

        self._touch()

        return True

    def promote_interest(
        self,
        interest: str,
        *,
        confidence: float = 1.0,
        minimum_confidence: float = 0.7,
    ) -> bool:
        """
        Promote a sufficiently reliable observation into the
        creator's structured interests.
        """

        confidence = self._clamp_confidence(
            confidence
        )

        if confidence < minimum_confidence:
            return False

        if self.user_model is None:
            return False

        method = getattr(
            self.user_model,
            "add_interest",
            None,
        )

        if not callable(method):
            return False

        result = method(
            interest
        )

        if result:
            self._touch()

        return bool(result)

    def promote_preference(
        self,
        key: str,
        value: Any,
        *,
        confidence: float = 1.0,
        minimum_confidence: float = 0.7,
    ) -> bool:
        """
        Promote a reliable understanding into the creator's
        structured preferences.
        """

        confidence = self._clamp_confidence(
            confidence
        )

        if confidence < minimum_confidence:
            return False

        if self.user_model is None:
            return False

        method = getattr(
            self.user_model,
            "set_preference",
            None,
        )

        if not callable(method):
            return False

        method(
            key,
            value,
        )

        self._touch()

        return True

    # ============================================================
    # SEARCH
    # ============================================================

    def search(
        self,
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Search Mary's relationship understanding.

        This is intentionally simple for V2's foundation. A more
        sophisticated semantic/vector retrieval system can replace
        this later without changing the public interface.
        """

        if not query:
            return []

        query_terms = {
            term.lower()
            for term in str(query).split()
            if term.strip()
        }

        results = []

        for collection_name, collection in (
            ("observation", self.observations),
            ("inference", self.inferences),
            ("pattern", self.patterns),
        ):

            for item in collection:

                searchable = " ".join(
                    str(value)
                    for key, value in item.items()
                    if key not in {
                        "id",
                        "created_at",
                        "updated_at",
                    }
                ).lower()

                score = sum(
                    1
                    for term in query_terms
                    if term in searchable
                )

                if score <= 0:
                    continue

                results.append(
                    {
                        "type": collection_name,
                        "score": score,
                        "item": item,
                    }
                )

        results.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return results

    # ============================================================
    # SUMMARY
    # ============================================================

    def summary(self) -> Dict[str, Any]:
        """
        Return a compact summary of Mary's current understanding.
        """

        return {
            "observations": len(
                self.observations
            ),
            "inferences": len(
                self.inferences
            ),
            "patterns": len(
                self.patterns
            ),
            "high_confidence_inferences": len(
                self.get_inferences(
                    minimum_confidence=0.7
                )
            ),
            "updated_at": self.updated_at,
        }

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the understanding state.
        """

        return {
            "observations": list(
                self.observations
            ),
            "inferences": list(
                self.inferences
            ),
            "patterns": list(
                self.patterns
            ),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(
        cls,
        data: Optional[Dict[str, Any]],
        *,
        user_model=None,
        history=None,
    ) -> "RelationshipUnderstanding":
        """
        Restore relationship understanding from serialized data.
        """

        understanding = cls(
            user_model=user_model,
            history=history,
        )

        if not isinstance(
            data,
            dict,
        ):
            return understanding

        observations = data.get(
            "observations",
            [],
        )

        inferences = data.get(
            "inferences",
            [],
        )

        patterns = data.get(
            "patterns",
            [],
        )

        if isinstance(
            observations,
            list,
        ):
            understanding.observations = observations

        if isinstance(
            inferences,
            list,
        ):
            understanding.inferences = inferences

        if isinstance(
            patterns,
            list,
        ):
            understanding.patterns = patterns

        understanding.updated_at = data.get(
            "updated_at",
            understanding.updated_at,
        )

        return understanding

    # ============================================================
    # INTERNAL
    # ============================================================

    def _touch(self) -> None:
        """
        Update modification timestamp.
        """

        self.updated_at = datetime.now().isoformat()

    @staticmethod
    def _clamp_confidence(
        confidence: float,
    ) -> float:
        """
        Keep confidence between 0.0 and 1.0.
        """

        try:
            value = float(
                confidence
            )
        except (
            TypeError,
            ValueError,
        ):
            value = 0.5

        return max(
            0.0,
            min(
                1.0,
                value,
            ),
        )

    @staticmethod
    def _new_id(
        prefix: str,
    ) -> str:
        """
        Generate a unique understanding record ID.
        """

        return (
            f"{prefix}_"
            f"{uuid.uuid4().hex[:12]}"
        )