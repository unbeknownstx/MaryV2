"""
MaryV2 - Decision System

Responsible for turning prioritized agency items into structured
decisions.

This module does NOT execute actions.

Architecture:

    Goals / Intentions / Curiosities
                ↓
            Priorities
                ↓
            Decisions
                ↓
        Autonomy / Actions

The decision system evaluates what Mary should do next and records
the reasoning behind that decision.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from mary.agency.priorities import PriorityItem, PrioritySystem


# ================================================================
# DECISION DATA
# ================================================================


@dataclass
class Decision:
    """
    A structured representation of a decision made by Mary.
    """

    id: str

    decision_type: str

    description: str

    status: str = "proposed"

    priority_score: float = 0.0

    confidence: float = 0.5

    reason: str = ""

    source_item_id: str | None = None

    source_item_type: str | None = None

    action: str | None = None

    created_at: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _timestamp()

        self.priority_score = _clamp(
            self.priority_score
        )

        self.confidence = _clamp(
            self.confidence
        )


# ================================================================
# DECISION SYSTEM
# ================================================================


class DecisionSystem:
    """
    Mary's decision-making layer.

    The system evaluates prioritized agency items and produces
    structured decisions.

    It does not directly perform external actions.
    """

    VALID_STATUSES = {
        "proposed",
        "accepted",
        "rejected",
        "executed",
        "cancelled",
    }

    def __init__(
        self,
        priority_system: PrioritySystem | None = None,
    ) -> None:
        self.priority_system = (
            priority_system
            or PrioritySystem()
        )

        self.decisions: list[Decision] = []

    # ============================================================
    # EVALUATION
    # ============================================================

    def evaluate(
        self,
        priorities: Iterable[PriorityItem] | None = None,
        *,
        context: dict[str, Any] | None = None,
    ) -> Decision | None:
        """
        Evaluate the highest-priority item and create a decision.

        The decision is returned as a proposal. Nothing is executed.
        """

        if priorities is None:
            priorities = self.priority_system.rank()

        priorities = list(priorities)

        if not priorities:
            return None

        item = priorities[0]

        context = context or {}

        confidence = self._calculate_confidence(
            item,
            context,
        )

        reason = self._build_reason(
            item,
            context,
        )

        action = self._suggest_action(
            item
        )

        decision = self.create_decision(
            decision_type=self._decision_type(
                item
            ),
            description=item.description,
            priority_score=item.score,
            confidence=confidence,
            reason=reason,
            source_item_id=item.item_id,
            source_item_type=item.item_type,
            action=action,
            metadata={
                "priority_item": item.metadata,
                "context": context,
            },
        )

        return decision

    # ============================================================
    # CREATE
    # ============================================================

    def create_decision(
        self,
        *,
        decision_type: str,
        description: str,
        priority_score: float = 0.0,
        confidence: float = 0.5,
        reason: str = "",
        source_item_id: str | None = None,
        source_item_type: str | None = None,
        action: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Decision:
        """
        Create and store a decision.
        """

        decision = Decision(
            id=self._next_id(),
            decision_type=str(
                decision_type
            ),
            description=str(
                description
            ).strip(),
            priority_score=priority_score,
            confidence=confidence,
            reason=str(reason),
            source_item_id=source_item_id,
            source_item_type=source_item_type,
            action=action,
            metadata=metadata or {},
        )

        self.decisions.append(
            decision
        )

        return decision

    # ============================================================
    # READ
    # ============================================================

    def get(
        self,
        decision_id: str,
    ) -> Decision | None:
        """
        Retrieve a decision by ID.
        """

        for decision in self.decisions:
            if decision.id == decision_id:
                return decision

        return None

    def get_all(self) -> list[Decision]:
        """
        Return all decisions.
        """

        return list(
            self.decisions
        )

    def get_pending(self) -> list[Decision]:
        """
        Return decisions that have not been finalized.
        """

        return [
            decision
            for decision in self.decisions
            if decision.status == "proposed"
        ]

    def get_recent(
        self,
        count: int = 10,
    ) -> list[Decision]:
        """
        Return the most recent decisions.
        """

        if count <= 0:
            return []

        return self.decisions[-count:]

    # ============================================================
    # STATUS
    # ============================================================

    def accept(
        self,
        decision_id: str,
    ) -> bool:
        """
        Accept a proposed decision.
        """

        return self._set_status(
            decision_id,
            "accepted",
        )

    def reject(
        self,
        decision_id: str,
    ) -> bool:
        """
        Reject a proposed decision.
        """

        return self._set_status(
            decision_id,
            "rejected",
        )

    def mark_executed(
        self,
        decision_id: str,
    ) -> bool:
        """
        Mark an accepted decision as executed.

        Actual execution is performed elsewhere.
        """

        decision = self.get(
            decision_id
        )

        if decision is None:
            return False

        if decision.status not in {
            "accepted",
            "proposed",
        }:
            return False

        decision.status = "executed"

        return True

    def cancel(
        self,
        decision_id: str,
    ) -> bool:
        """
        Cancel a decision.
        """

        return self._set_status(
            decision_id,
            "cancelled",
        )

    def _set_status(
        self,
        decision_id: str,
        status: str,
    ) -> bool:
        if status not in self.VALID_STATUSES:
            return False

        decision = self.get(
            decision_id
        )

        if decision is None:
            return False

        decision.status = status

        return True

    # ============================================================
    # DECISION LOGIC
    # ============================================================

    def _calculate_confidence(
        self,
        item: PriorityItem,
        context: dict[str, Any],
    ) -> float:
        """
        Estimate confidence in a proposed decision.

        This is deliberately simple for V2's initial agency layer.

        Later this can incorporate:

            - historical success
            - learned preferences
            - uncertainty
            - relationship context
            - memory retrieval
            - reflection
            - tool results
            - LLM reasoning
        """

        confidence = 0.45

        confidence += (
            item.importance * 0.15
        )

        confidence += (
            item.relevance * 0.20
        )

        confidence += (
            item.urgency * 0.05
        )

        if context:
            confidence += 0.10

        return _clamp(
            confidence
        )

    def _build_reason(
        self,
        item: PriorityItem,
        context: dict[str, Any],
    ) -> str:
        """
        Build a human-readable explanation for the decision.
        """

        reason = (
            f"'{item.description}' was selected because "
            f"it has a priority score of "
            f"{item.score:.2f}."
        )

        if item.item_type:
            reason += (
                f" It originated from the "
                f"{item.item_type} system."
            )

        if context:
            reason += (
                " Current context was also considered."
            )

        return reason

    def _suggest_action(
        self,
        item: PriorityItem,
    ) -> str:
        """
        Suggest a generic action category.

        This is intentionally not an executable action.
        """

        if item.item_type == "goal":
            return "pursue_goal"

        if item.item_type == "intention":
            return "consider_intention"

        if item.item_type == "curiosity":
            return "investigate_curiosity"

        return "consider_item"

    def _decision_type(
        self,
        item: PriorityItem,
    ) -> str:
        """
        Convert the agency item type into a decision type.
        """

        mapping = {
            "goal": "GOAL_PURSUIT",
            "intention": "INTENTION_EVALUATION",
            "curiosity": "CURIOSITY_EXPLORATION",
        }

        return mapping.get(
            item.item_type,
            "GENERAL",
        )

    # ============================================================
    # DECISION SELECTION
    # ============================================================

    def choose(
        self,
        decisions: Iterable[Decision] | None = None,
    ) -> Decision | None:
        """
        Choose the strongest proposed decision.

        This does not execute it.
        """

        if decisions is None:
            decisions = self.get_pending()

        decisions = list(
            decisions
        )

        if not decisions:
            return None

        return max(
            decisions,
            key=lambda decision: (
                decision.priority_score
                * decision.confidence
            ),
        )

    # ============================================================
    # HISTORY / LEARNING SUPPORT
    # ============================================================

    def successful_decisions(
        self,
    ) -> list[Decision]:
        """
        Return decisions marked as executed.

        Later the learning system can use this history to learn
        which kinds of decisions tend to work well.
        """

        return [
            decision
            for decision in self.decisions
            if decision.status == "executed"
        ]

    def failed_or_rejected_decisions(
        self,
    ) -> list[Decision]:
        """
        Return decisions that were rejected or cancelled.
        """

        return [
            decision
            for decision in self.decisions
            if decision.status in {
                "rejected",
                "cancelled",
            }
        ]

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> list[dict[str, Any]]:
        """
        Convert the decision history to dictionaries.
        """

        return [
            asdict(decision)
            for decision in self.decisions
        ]

    def from_dict(
        self,
        data: list[dict[str, Any]],
    ) -> None:
        """
        Restore decision history from dictionaries.
        """

        self.decisions.clear()

        if not isinstance(
            data,
            list,
        ):
            return

        for entry in data:
            if not isinstance(
                entry,
                dict,
            ):
                continue

            decision = Decision(
                id=str(
                    entry.get(
                        "id",
                        "",
                    )
                ),
                decision_type=str(
                    entry.get(
                        "decision_type",
                        "GENERAL",
                    )
                ),
                description=str(
                    entry.get(
                        "description",
                        "",
                    )
                ),
                status=str(
                    entry.get(
                        "status",
                        "proposed",
                    )
                ),
                priority_score=_clamp(
                    entry.get(
                        "priority_score",
                        0.0,
                    )
                ),
                confidence=_clamp(
                    entry.get(
                        "confidence",
                        0.5,
                    )
                ),
                reason=str(
                    entry.get(
                        "reason",
                        "",
                    )
                ),
                source_item_id=entry.get(
                    "source_item_id"
                ),
                source_item_type=entry.get(
                    "source_item_type"
                ),
                action=entry.get(
                    "action"
                ),
                created_at=str(
                    entry.get(
                        "created_at",
                        _timestamp(),
                    )
                ),
                metadata=entry.get(
                    "metadata",
                    {},
                ),
            )

            self.decisions.append(
                decision
            )

    # ============================================================
    # UTILITIES
    # ============================================================

    def _next_id(self) -> str:
        """
        Generate the next persistent decision ID.
        """

        highest = 0

        for decision in self.decisions:
            decision_id = str(
                decision.id
            )

            if not decision_id.startswith(
                "decision_"
            ):
                continue

            try:
                number = int(
                    decision_id.split(
                        "_"
                    )[-1]
                )
            except ValueError:
                continue

            highest = max(
                highest,
                number,
            )

        return (
            f"decision_{highest + 1}"
        )


# ================================================================
# HELPERS
# ================================================================


def _clamp(
    value: float,
) -> float:
    """
    Keep a numeric value between 0.0 and 1.0.
    """

    try:
        value = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return 0.5

    return max(
        0.0,
        min(
            1.0,
            value,
        ),
    )


def _timestamp() -> str:
    """
    Return a timezone-aware UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()