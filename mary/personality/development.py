"""
MaryV2 - Personality Development System

Manages controlled evolution of Mary's personality.

This system does NOT allow the LLM to directly rewrite Mary's
personality. Instead, personality changes are represented as
development proposals that can be evaluated, accepted, rejected,
or applied according to explicit rules.

Values are treated as relatively stable.
Preferences are more flexible.
Personality traits may evolve gradually through experience.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional


class PersonalityDevelopment:
    """
    Controlled personality-development system.

    Responsibilities:

        - track development history
        - create development proposals
        - evaluate proposals
        - apply approved changes
        - prevent excessively large personality changes
        - preserve values as a separate layer
        - expose development information to other systems

    The actual personality object is intentionally supplied from
    outside this class so the development system does not become
    tightly coupled to personality.py.
    """

    DEFAULT_MAX_CHANGE = 0.10
    DEFAULT_MIN_CONFIDENCE = 0.60

    def __init__(
        self,
        personality: Any = None,
        values: Any = None,
        preferences: Any = None,
        max_change: float = DEFAULT_MAX_CHANGE,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ):
        self.personality = personality
        self.values = values
        self.preferences = preferences

        self.max_change = self._clamp(
            max_change
        )

        self.min_confidence = self._clamp(
            min_confidence
        )

        self.history: List[
            Dict[str, Any]
        ] = []

        self.pending: List[
            Dict[str, Any]
        ] = []

    # ============================================================
    # PROPOSALS
    # ============================================================

    def propose_change(
        self,
        trait: str,
        change: float,
        reason: str,
        confidence: float = 0.5,
        source: str = "experience",
    ) -> Dict[str, Any]:
        """
        Create a personality-development proposal.

        The proposal is NOT applied immediately.
        """

        trait = self._normalize(
            trait
        )

        if not trait:
            raise ValueError(
                "Trait cannot be empty."
            )

        proposal = {
            "id": self._next_id(),
            "trait": trait,
            "requested_change": float(
                change
            ),
            "reason": str(
                reason
            ).strip(),
            "confidence": self._clamp(
                confidence
            ),
            "source": str(
                source
            ).strip() or "experience",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }

        self.pending.append(
            proposal
        )

        return deepcopy(
            proposal
        )

    # ============================================================
    # EVALUATION
    # ============================================================

    def evaluate(
        self,
        proposal: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate whether a development proposal should be allowed.

        Evaluation considers:

            - confidence
            - maximum change size
            - existing values
            - whether the trait exists
        """

        result = {
            "approved": False,
            "reason": "",
            "change": 0.0,
        }

        if not isinstance(
            proposal,
            dict,
        ):
            result["reason"] = (
                "Invalid development proposal."
            )
            return result

        trait = self._normalize(
            proposal.get(
                "trait",
                "",
            )
        )

        if not trait:
            result["reason"] = (
                "No personality trait specified."
            )
            return result

        confidence = self._clamp(
            proposal.get(
                "confidence",
                0.0,
            )
        )

        if confidence < self.min_confidence:
            result["reason"] = (
                "Confidence is below the development threshold."
            )
            return result

        try:
            requested_change = float(
                proposal.get(
                    "requested_change",
                    0.0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            result["reason"] = (
                "Invalid requested change."
            )
            return result

        if requested_change == 0:
            result["reason"] = (
                "Requested change is zero."
            )
            return result

        bounded_change = max(
            -self.max_change,
            min(
                self.max_change,
                requested_change,
            ),
        )

        if abs(requested_change) > self.max_change:
            result["reason"] = (
                "Change was reduced to the maximum allowed "
                "development step."
            )
        else:
            result["reason"] = (
                "Development proposal approved."
            )

        result["approved"] = True
        result["change"] = bounded_change

        return result

    # ============================================================
    # APPLY
    # ============================================================

    def apply(
        self,
        proposal: Dict[str, Any],
    ) -> bool:
        """
        Evaluate and apply a development proposal.

        Returns True when the change is applied.
        """

        evaluation = self.evaluate(
            proposal
        )

        if not evaluation["approved"]:
            return False

        trait = self._normalize(
            proposal.get(
                "trait",
                "",
            )
        )

        change = evaluation[
            "change"
        ]

        old_value = self._get_trait(
            trait
        )

        new_value = self._apply_trait_change(
            trait,
            change,
        )

        if new_value is None:
            return False

        record = {
            "id": proposal.get(
                "id",
                self._next_id(),
            ),
            "trait": trait,
            "change": change,
            "old_value": old_value,
            "new_value": new_value,
            "reason": proposal.get(
                "reason",
                "",
            ),
            "confidence": self._clamp(
                proposal.get(
                    "confidence",
                    0.0,
                )
            ),
            "source": proposal.get(
                "source",
                "experience",
            ),
            "status": "applied",
            "timestamp": datetime.now().isoformat(),
        }

        self.history.append(
            record
        )

        self._mark_pending(
            proposal.get(
                "id"
            ),
            "applied",
        )

        return True

    # ============================================================
    # REJECT
    # ============================================================

    def reject(
        self,
        proposal: Dict[str, Any],
        reason: str = "",
    ) -> bool:
        """
        Reject a development proposal.
        """

        if not isinstance(
            proposal,
            dict,
        ):
            return False

        proposal_id = proposal.get(
            "id"
        )

        self._mark_pending(
            proposal_id,
            "rejected",
        )

        self.history.append(
            {
                "id": proposal_id,
                "trait": proposal.get(
                    "trait",
                    "",
                ),
                "change": 0.0,
                "reason": reason
                or "Proposal rejected.",
                "confidence": self._clamp(
                    proposal.get(
                        "confidence",
                        0.0,
                    )
                ),
                "source": proposal.get(
                    "source",
                    "unknown",
                ),
                "status": "rejected",
                "timestamp": datetime.now().isoformat(),
            }
        )

        return True

    # ============================================================
    # PENDING
    # ============================================================

    def get_pending(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Return pending development proposals.
        """

        return [
            deepcopy(item)
            for item in self.pending
            if item.get(
                "status"
            ) == "pending"
        ]

    # ============================================================
    # HISTORY
    # ============================================================

    def get_history(
        self,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return personality-development history.
        """

        history = [
            deepcopy(item)
            for item in self.history
        ]

        if limit is not None:
            history = history[
                -max(0, int(limit)):
            ]

        return history

    # ============================================================
    # TRAIT ACCESS
    # ============================================================

    def _get_trait(
        self,
        trait: str,
    ) -> Optional[float]:
        """
        Read a personality trait.

        Supports personality implementations that expose either:

            get_trait(name)

        or:

            traits[name]
        """

        if self.personality is None:
            return None

        getter = getattr(
            self.personality,
            "get_trait",
            None,
        )

        if callable(getter):

            try:
                value = getter(
                    trait
                )

                return self._numeric_or_none(
                    value
                )

            except Exception:
                pass

        traits = getattr(
            self.personality,
            "traits",
            None,
        )

        if isinstance(
            traits,
            dict,
        ):
            return self._numeric_or_none(
                traits.get(
                    trait
                )
            )

        return None

    # ============================================================
    # TRAIT CHANGE
    # ============================================================

    def _apply_trait_change(
        self,
        trait: str,
        change: float,
    ) -> Optional[float]:
        """
        Apply a bounded change to a personality trait.

        Supports personality implementations exposing:

            adjust_trait(name, amount)

        or:

            traits[name]
        """

        if self.personality is None:
            return None

        adjuster = getattr(
            self.personality,
            "adjust_trait",
            None,
        )

        if callable(adjuster):

            try:
                result = adjuster(
                    trait,
                    change,
                )

                numeric = (
                    self._numeric_or_none(
                        result
                    )
                )

                if numeric is not None:
                    return self._clamp(
                        numeric
                    )

                current = self._get_trait(
                    trait
                )

                return current

            except Exception:
                pass

        traits = getattr(
            self.personality,
            "traits",
            None,
        )

        if not isinstance(
            traits,
            dict,
        ):
            return None

        current = self._numeric_or_none(
            traits.get(
                trait
            )
        )

        if current is None:
            current = 0.5

        new_value = self._clamp(
            current + change
        )

        traits[trait] = new_value

        return new_value

    # ============================================================
    # DEVELOPMENT FROM EXPERIENCE
    # ============================================================

    def learn_from_experience(
        self,
        trait: str,
        change: float,
        reason: str,
        confidence: float = 0.5,
        source: str = "experience",
        auto_apply: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a development proposal from an experience.

        By default this only creates the proposal.

        auto_apply=True may be used by higher-level systems when
        the experience has already passed their evaluation criteria.
        """

        proposal = self.propose_change(
            trait=trait,
            change=change,
            reason=reason,
            confidence=confidence,
            source=source,
        )

        if auto_apply:
            self.apply(
                proposal
            )

        return proposal

    # ============================================================
    # DEVELOPMENT SUMMARY
    # ============================================================

    def summary(self) -> Dict[str, Any]:
        """
        Return a compact development summary.
        """

        return {
            "pending": len(
                self.get_pending()
            ),
            "history": len(
                self.history
            ),
            "max_change": self.max_change,
            "min_confidence": self.min_confidence,
        }

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Serialize personality development state.
        """

        return {
            "max_change": self.max_change,
            "min_confidence": self.min_confidence,
            "pending": deepcopy(
                self.pending
            ),
            "history": deepcopy(
                self.history
            ),
        }

    def load(
        self,
        data: Dict[str, Any],
    ) -> None:
        """
        Load serialized development state.
        """

        if not isinstance(
            data,
            dict,
        ):
            return

        self.max_change = self._clamp(
            data.get(
                "max_change",
                self.DEFAULT_MAX_CHANGE,
            )
        )

        self.min_confidence = self._clamp(
            data.get(
                "min_confidence",
                self.DEFAULT_MIN_CONFIDENCE,
            )
        )

        pending = data.get(
            "pending",
            [],
        )

        history = data.get(
            "history",
            [],
        )

        self.pending = (
            deepcopy(pending)
            if isinstance(
                pending,
                list,
            )
            else []
        )

        self.history = (
            deepcopy(history)
            if isinstance(
                history,
                list,
            )
            else []
        )

    @classmethod
    def from_dict(
        cls,
        data: Optional[Dict[str, Any]],
        personality: Any = None,
        values: Any = None,
        preferences: Any = None,
    ) -> "PersonalityDevelopment":
        """
        Construct the development system from serialized data.
        """

        system = cls(
            personality=personality,
            values=values,
            preferences=preferences,
        )

        if isinstance(
            data,
            dict,
        ):
            system.load(
                data
            )

        return system

    # ============================================================
    # RESET
    # ============================================================

    def reset_history(
        self,
    ) -> None:
        """
        Clear development history and pending proposals.
        """

        self.pending = []
        self.history = []

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    def _mark_pending(
        self,
        proposal_id: Any,
        status: str,
    ) -> None:
        """
        Update the status of a pending proposal.
        """

        for proposal in self.pending:

            if proposal.get(
                "id"
            ) == proposal_id:

                proposal["status"] = status

                return

    def _next_id(
        self,
    ) -> str:
        """
        Generate the next development proposal ID.
        """

        highest = 0

        for item in (
            self.pending
            + self.history
        ):

            item_id = str(
                item.get(
                    "id",
                    "",
                )
            )

            if not item_id.startswith(
                "development_"
            ):
                continue

            try:
                number = int(
                    item_id.split(
                        "_"
                    )[-1]
                )

                highest = max(
                    highest,
                    number,
                )

            except (
                ValueError,
            ):
                continue

        return (
            f"development_{highest + 1}"
        )

    @staticmethod
    def _normalize(
        value: Any,
    ) -> str:
        """
        Normalize a string identifier.
        """

        return str(
            value
        ).strip().lower()

    @staticmethod
    def _numeric_or_none(
        value: Any,
    ) -> Optional[float]:
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
            return None

    @staticmethod
    def _clamp(
        value: Any,
    ) -> float:
        """
        Clamp a numeric value between 0.0 and 1.0.
        """

        try:
            value = float(
                value
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