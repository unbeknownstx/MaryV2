"""
MaryV2 - Agency Coordinator

Public coordinator for Mary's agency architecture.

The Agency coordinator connects:
- goals
- intentions
- curiosities
- priorities
- decisions

Individual agency systems remain responsible for their own
storage and behavior.

Agency determines and organizes what Mary may want to pursue,
consider, or investigate. It does not execute external actions.
Execution belongs to the autonomy/action systems.
"""

from __future__ import annotations

from mary.governance.limits import RuntimeLimits

from pathlib import Path
from typing import Any

from mary.agency.curiosity import CuriositySystem
from mary.agency.decisions import Decision, DecisionSystem
from mary.agency.goals import GoalSystem
from mary.agency.intentions import IntentionSystem
from mary.agency.priorities import PriorityItem, PrioritySystem


class Agency:
    """
    Unified public coordinator for Mary's agency architecture.
    """

    def __init__(
        self,
        goal_system: GoalSystem | None = None,
        intention_system: IntentionSystem | None = None,
        curiosity_system: CuriositySystem | None = None,
        priority_system: PrioritySystem | None = None,
        decision_system: DecisionSystem | None = None,
        limits: RuntimeLimits | None = None,
        storage_root: str | Path | None = None,
    ) -> None:

        self.limits = limits or RuntimeLimits()
        self.storage_root = Path(storage_root) if storage_root is not None else None
        self.goals = (
            goal_system
            if goal_system is not None
            else GoalSystem(
                path=(self.storage_root / "goals.json") if self.storage_root is not None else "data/goals/goals.json",
                capacity=self.limits.goal_capacity,
                content_limit=self.limits.agency_text_characters,
                backup_generations=self.limits.backup_generations,
            )
        )

        self.intentions = (
            intention_system
            if intention_system is not None
            else IntentionSystem(
                path=(self.storage_root / "intentions.json") if self.storage_root is not None else "data/goals/intentions.json",
                capacity=self.limits.intention_capacity,
                content_limit=self.limits.agency_text_characters,
                backup_generations=self.limits.backup_generations,
            )
        )

        self.curiosities = (
            curiosity_system
            if curiosity_system is not None
            else CuriositySystem(
                path=(self.storage_root / "curiosities.json") if self.storage_root is not None else "data/goals/curiosities.json",
                capacity=self.limits.curiosity_capacity,
                content_limit=self.limits.agency_text_characters,
                backup_generations=self.limits.backup_generations,
            )
        )

        self.priorities = (
            priority_system
            if priority_system is not None
            else PrioritySystem()
        )

        self.decisions = (
            decision_system
            if decision_system is not None
            else DecisionSystem(
                priority_system=self.priorities,
            )
        )

    # ================================================================
    # LIFECYCLE
    # ================================================================

    def load(self) -> None:
        """
        Load persistent agency state and rebuild derived priorities.
        """

        self.goals.load()
        self.intentions.load()
        self.curiosities.load()

        self.rebuild_priorities()

    # ================================================================
    # PRIORITIES
    # ================================================================

    def rebuild_priorities(
        self,
    ) -> list[PriorityItem]:
        """
        Rebuild priority state from Mary's current agency data.
        """

        return self.priorities.rebuild(
            goals=self.goals.get_goals(),
            intentions=self.intentions.get_intentions(),
            curiosities=self.curiosities.get_curiosities(),
        )

    # ================================================================
    # DECISIONS
    # ================================================================

    def evaluate(
        self,
        *,
        context: dict[str, Any] | None = None,
        rebuild: bool = True,
    ) -> Decision | None:
        """
        Evaluate current agency state and produce a proposed decision.

        Nothing is executed by this method.
        """

        if rebuild:
            self.rebuild_priorities()

        return self.decisions.evaluate(
            context=context,
        )

    def choose(
        self,
    ) -> Decision | None:
        """
        Choose the strongest proposed decision without executing it.
        """

        return self.decisions.choose()

    # ================================================================
    # STATUS
    # ================================================================

    def status(
        self,
    ) -> dict[str, Any]:
        """
        Return a high-level summary of Mary's agency state.
        """

        return {
            "goals": {
                "total": len(
                    self.goals.get_goals()
                ),
                "active": self.goals.count_active(),
            },
            "intentions": {
                "total": len(
                    self.intentions.get_intentions()
                ),
                "pending": self.intentions.count_pending(),
                "active": self.intentions.count_active(),
            },
            "curiosities": {
                "total": len(
                    self.curiosities.get_curiosities()
                ),
                "open": self.curiosities.count_open(),
                "exploring": self.curiosities.count_exploring(),
            },
            "priorities": len(
                self.priorities.get_all()
            ),
            "decisions": len(
                self.decisions.get_all()
            ),
        }
