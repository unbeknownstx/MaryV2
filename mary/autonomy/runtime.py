"""
Mary - Autonomy Runtime

Coordinates Mary's autonomous decision cycle.

The autonomy runtime connects:

    actions
    triggers
    scheduler

It is responsible for evaluating autonomous conditions and producing
actions for the rest of Mary to handle.

It does NOT:

    - discover tools
    - access the internet
    - execute arbitrary external capabilities
    - create permissions
    - install capabilities
    - modify the filesystem
    - bypass explicit approval

An action produced by autonomy remains a description of intended work
until an explicitly approved execution system handles it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Mapping
from uuid import uuid4

from mary.runtime.turn_observability import record_turn_stage

from .actions import (
    Action,
    ActionPermission,
    ActionQueue,
    ActionResult,
    ActionStatus,
)

from .scheduler import (
    ScheduleEvent,
    Scheduler,
)

from .triggers import (
    TriggerContext,
    TriggerRegistry,
    TriggerResult,
)


# ================================================================
# RUNTIME STATUS
# ================================================================


class AutonomyRuntimeStatus(str, Enum):
    """
    Current state of the autonomy runtime.
    """

    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


# ================================================================
# RUNTIME ERRORS
# ================================================================


class AutonomyRuntimeError(RuntimeError):
    """
    Base autonomy runtime exception.
    """


class AutonomyRuntimeStateError(
    AutonomyRuntimeError
):
    """
    Raised when an operation is invalid for the current state.
    """


class AutonomyExecutionError(
    AutonomyRuntimeError
):
    """
    Raised when an approved action cannot be processed.
    """


# ================================================================
# RUNTIME RESULT
# ================================================================


@dataclass
class AutonomyCycleResult:
    """
    Result of one autonomy processing cycle.

    The result describes what autonomy discovered or produced.
    It does not imply that external actions were executed.
    """

    cycle_id: int

    timestamp: float

    evaluation_id: str = field(
        default_factory=lambda: f"evaluation_{uuid4().hex[:16]}"
    )

    cycle_reference_id: str = field(
        default_factory=lambda: f"autonomy_cycle_{uuid4().hex[:16]}"
    )

    trigger_results: tuple[
        TriggerResult,
        ...
    ] = ()

    schedule_events: tuple[
        ScheduleEvent,
        ...
    ] = ()

    actions_created: tuple[
        Action,
        ...
    ] = ()

    actions_ready: tuple[
        Action,
        ...
    ] = ()

    deduplicated_proposal_ids: tuple[str, ...] = ()

    errors: tuple[
        str,
        ...
    ] = ()

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Convert the cycle result into serializable data.
        """

        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "evaluation_id": self.evaluation_id,
            "cycle_reference_id": self.cycle_reference_id,
            "trigger_results": [
                result.to_dict()
                for result
                in self.trigger_results
            ],
            "schedule_events": [
                event.to_dict()
                for event
                in self.schedule_events
            ],
            "actions_created": [
                action.to_dict()
                for action
                in self.actions_created
            ],
            "actions_ready": [
                action.to_dict()
                for action
                in self.actions_ready
            ],
            "deduplicated_proposal_ids": list(
                self.deduplicated_proposal_ids
            ),
            "errors": list(
                self.errors
            ),
        }


# ================================================================
# RUNTIME SNAPSHOT
# ================================================================


@dataclass(frozen=True)
class AutonomyRuntimeSnapshot:
    """
    Read-only snapshot of autonomy runtime state.
    """

    status: AutonomyRuntimeStatus

    cycle_count: int

    action_count: int

    trigger_count: int

    schedule_count: int

    last_cycle_at: float | None

    last_error: str | None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "cycle_count": self.cycle_count,
            "action_count": self.action_count,
            "trigger_count": self.trigger_count,
            "schedule_count": self.schedule_count,
            "last_cycle_at": self.last_cycle_at,
            "last_error": self.last_error,
        }


# ================================================================
# AUTONOMY RUNTIME
# ================================================================


class AutonomyRuntime:
    """
    Coordinates the autonomy subsystem.

    The runtime performs three primary operations:

        1. Evaluate registered triggers.
        2. Process due schedules.
        3. Collect resulting actions.

    It intentionally separates discovering an intended action from
    actually executing that action.
    """

    def __init__(
        self,
        *,
        action_queue: ActionQueue | None = None,
        trigger_registry: TriggerRegistry | None = None,
        scheduler: Scheduler | None = None,
    ) -> None:

        self.actions = (
            action_queue
            if action_queue is not None
            else ActionQueue()
        )

        self.triggers = (
            trigger_registry
            if trigger_registry is not None
            else TriggerRegistry()
        )

        self.scheduler = (
            scheduler
            if scheduler is not None
            else Scheduler()
        )

        self.status = (
            AutonomyRuntimeStatus.STOPPED
        )

        self.cycle_count = 0

        self.last_cycle_at: float | None = None

        self.last_error: str | None = None

    # ============================================================
    # LIFECYCLE
    # ============================================================

    def start(self) -> None:
        """
        Start the autonomy runtime.
        """

        if self.status == (
            AutonomyRuntimeStatus.RUNNING
        ):
            return

        if self.status == (
            AutonomyRuntimeStatus.ERROR
        ):
            raise AutonomyRuntimeStateError(
                (
                    "Cannot start autonomy runtime "
                    "while it is in an error state."
                )
            )

        self.status = (
            AutonomyRuntimeStatus.RUNNING
        )

        self.last_error = None

    def stop(self) -> None:
        """
        Stop the autonomy runtime.

        Stopping autonomy does not delete queued actions,
        triggers, or schedules.
        """

        self.status = (
            AutonomyRuntimeStatus.STOPPED
        )

    def pause(self) -> None:
        """
        Pause autonomous processing.
        """

        if self.status != (
            AutonomyRuntimeStatus.RUNNING
        ):
            raise AutonomyRuntimeStateError(
                (
                    "Autonomy runtime must be running "
                    "before it can be paused."
                )
            )

        self.status = (
            AutonomyRuntimeStatus.PAUSED
        )

    def resume(self) -> None:
        """
        Resume autonomous processing.
        """

        if self.status != (
            AutonomyRuntimeStatus.PAUSED
        ):
            raise AutonomyRuntimeStateError(
                (
                    "Autonomy runtime is not paused."
                )
            )

        self.status = (
            AutonomyRuntimeStatus.RUNNING
        )

    def reset_error(self) -> None:
        """
        Clear an error state and return the runtime to stopped state.
        """

        if self.status != (
            AutonomyRuntimeStatus.ERROR
        ):
            return

        self.status = (
            AutonomyRuntimeStatus.STOPPED
        )

        self.last_error = None

    # ============================================================
    # CYCLE
    # ============================================================

    def cycle(
        self,
        context: TriggerContext | None = None,
        *,
        now: float | None = None,
    ) -> AutonomyCycleResult:
        """
        Process one autonomy cycle.

        A cycle:

            - evaluates triggers
            - processes schedules
            - stores newly generated actions
            - identifies approved actions that are ready

        It does NOT execute external actions.
        """

        if self.status != (
            AutonomyRuntimeStatus.RUNNING
        ):
            raise AutonomyRuntimeStateError(
                (
                    "Autonomy runtime must be running "
                    "before processing a cycle."
                )
            )

        timestamp = (
            time()
            if now is None
            else now
        )

        if context is None:
            context = TriggerContext(
                timestamp=timestamp
            )
        else:
            context.timestamp = timestamp

        evaluation_id = f"evaluation_{uuid4().hex[:16]}"
        cycle_reference_id = f"autonomy_cycle_{uuid4().hex[:16]}"
        attention_id = self._opaque_context_id(context, "attention_id")

        self.cycle_count += 1

        cycle_errors: list[
            str
        ] = []

        trigger_results: list[
            TriggerResult
        ] = []

        schedule_events: list[
            ScheduleEvent
        ] = []

        actions_created: list[
            Action
        ] = []
        deduplicated_proposal_ids: list[str] = []

        try:
            # ----------------------------------------------------
            # Trigger evaluation
            # ----------------------------------------------------

            trigger_results.extend(
                self.triggers.evaluate_all(
                    context
                )
            )

            # ----------------------------------------------------
            # Store actions produced by triggers
            # ----------------------------------------------------

            for result in trigger_results:

                if not result.triggered:
                    continue

                if result.action is None:
                    continue

                try:
                    self._prepare_proposal(
                        result.action,
                        evaluation_id=evaluation_id,
                        attention_id=attention_id,
                    )
                    if self.actions.add(result.action):
                        actions_created.append(result.action)
                    else:
                        existing = self.actions.active_by_dedupe_key(
                            str(result.action.metadata.get("dedupe_key") or "")
                        )
                        proposal_id = str(
                            getattr(existing, "metadata", {}).get("proposal_id")
                            or ""
                        )
                        if proposal_id:
                            deduplicated_proposal_ids.append(proposal_id)

                except Exception as exc:
                    cycle_errors.append(
                        (
                            "Failed to register "
                            f"trigger action: {exc}"
                        )
                    )

            # ----------------------------------------------------
            # Scheduled events
            # ----------------------------------------------------

            schedule_events.extend(
                self.scheduler.due(
                    timestamp
                )
            )

            # ----------------------------------------------------
            # Convert schedule events into passive actions
            # ----------------------------------------------------

            for event in schedule_events:

                if not event.callback_key:
                    continue

                try:
                    action = self._action_from_schedule(
                        event
                    )
                    self._prepare_proposal(
                        action,
                        evaluation_id=evaluation_id,
                        attention_id=attention_id,
                    )
                    if self.actions.add(action):
                        actions_created.append(action)
                    else:
                        existing = self.actions.active_by_dedupe_key(
                            str(action.metadata.get("dedupe_key") or "")
                        )
                        proposal_id = str(
                            getattr(existing, "metadata", {}).get("proposal_id")
                            or ""
                        )
                        if proposal_id:
                            deduplicated_proposal_ids.append(proposal_id)

                except Exception as exc:
                    cycle_errors.append(
                        (
                            "Failed to create scheduled "
                            f"action: {exc}"
                        )
                    )

            # ----------------------------------------------------
            # Approved actions ready for execution
            # ----------------------------------------------------

            actions_ready = tuple(
                action
                for action
                in self.actions.due(
                    timestamp
                )
                if action.permission
                == ActionPermission.APPROVED
                and action.can_attempt
            )

            self.last_cycle_at = timestamp

            if cycle_errors:
                self.last_error = (
                    "; ".join(
                        cycle_errors
                    )
                )
            else:
                self.last_error = None

            cycle_result = AutonomyCycleResult(
                cycle_id=self.cycle_count,
                timestamp=timestamp,
                evaluation_id=evaluation_id,
                cycle_reference_id=cycle_reference_id,
                trigger_results=tuple(
                    trigger_results
                ),
                schedule_events=tuple(
                    schedule_events
                ),
                actions_created=tuple(
                    actions_created
                ),
                actions_ready=actions_ready,
                deduplicated_proposal_ids=tuple(
                    dict.fromkeys(deduplicated_proposal_ids)
                ),
                errors=tuple(
                    cycle_errors
                ),
            )
            record_turn_stage(
                "autonomy_processing",
                status="success",
                elapsed_ms=0.0,
                outcome="proposals_recorded_not_executed",
            )
            return cycle_result

        except Exception as exc:

            self.last_error = str(
                exc
            )

            self.status = (
                AutonomyRuntimeStatus.ERROR
            )

            raise AutonomyRuntimeError(
                (
                    "Autonomy cycle failed: "
                    f"{exc}"
                )
            ) from exc

    @staticmethod
    def _opaque_context_id(
        context: TriggerContext | None,
        key: str,
    ) -> str | None:
        """Accept only an opaque attention correlation identifier."""
        if context is None:
            return None
        value = context.metadata.get(key) or context.values.get(key)
        text = str(value or "").strip()
        if key == "attention_id" and text.startswith("attention_"):
            return text[:80]
        return None

    @staticmethod
    def _prepare_proposal(
        action: Action,
        *,
        evaluation_id: str,
        attention_id: str | None,
    ) -> None:
        action.mark_as_proposal(
            evaluation_id=evaluation_id,
            attention_id=attention_id,
            dedupe_key=(
                str(action.metadata.get("dedupe_key") or "").strip()
                or None
            ),
        )

    # ============================================================
    # SCHEDULE ACTION CREATION
    # ============================================================

    @staticmethod
    def _action_from_schedule(
        event: ScheduleEvent,
    ) -> Action:
        """
        Convert a schedule event into a passive Action.

        The resulting action is NOT approved.
        """

        from .actions import (
            ActionSource,
            ActionType,
            create_action,
        )

        return create_action(
            event.callback_key,
            action_type=ActionType.TASK,
            source=ActionSource.SCHEDULE,
            description=(
                f"Scheduled autonomy task: "
                f"{event.name}"
            ),
            metadata={
                "schedule_id": event.schedule_id,
                "schedule_run": event.run_count,
                **dict(
                    event.metadata
                ),
            },
        )

    # ============================================================
    # ACTION APPROVAL
    # ============================================================

    def approve_action(
        self,
        action_id: str,
    ) -> Action:
        """
        Explicitly approve a queued action.

        Approval changes the action state only.

        It does NOT execute the action.
        """

        action = self.actions.require(
            action_id
        )

        action.approve()

        return action

    def reject_action(
        self,
        action_id: str,
    ) -> Action:
        """
        Reject a queued action.
        """

        action = self.actions.require(
            action_id
        )

        action.deny()

        return action

    def cancel_action(
        self,
        action_id: str,
    ) -> Action:
        """
        Cancel a queued action.
        """

        action = self.actions.require(
            action_id
        )

        action.cancel()

        return action

    # ============================================================
    # ACTION PROCESSING
    # ============================================================

    def begin_action(
        self,
        action_id: str,
    ) -> Action:
        """
        Mark an approved action as ready for an external executor.

        This method does NOT execute the action.

        The returned Action is handed to whatever explicitly
        approved execution layer is responsible for it.
        """

        action = self.actions.require(
            action_id
        )

        action.begin_attempt()

        return action

    def complete_action(
        self,
        action_id: str,
    ) -> Action:
        """
        Mark an action as completed.

        The actual work must have been performed by an external,
        explicitly approved execution layer before this method is
        called.
        """

        action = self.actions.require(
            action_id
        )

        action.complete()

        return action

    def fail_action(
        self,
        action_id: str,
    ) -> Action:
        """
        Mark an action as failed.
        """

        action = self.actions.require(
            action_id
        )

        action.fail()

        return action

    # ============================================================
    # SNAPSHOT
    # ============================================================

    def snapshot(
        self,
    ) -> AutonomyRuntimeSnapshot:
        """
        Return a read-only snapshot of runtime state.
        """

        return AutonomyRuntimeSnapshot(
            status=self.status,
            cycle_count=self.cycle_count,
            action_count=len(
                self.actions
            ),
            trigger_count=len(
                self.triggers.all()
            ),
            schedule_count=len(
                self.scheduler.all()
            ),
            last_cycle_at=self.last_cycle_at,
            last_error=self.last_error,
        )

    # ============================================================
    # STATE
    # ============================================================

    @property
    def running(
        self,
    ) -> bool:
        """
        Whether autonomy is actively processing.
        """

        return (
            self.status
            == AutonomyRuntimeStatus.RUNNING
        )

    @property
    def paused(
        self,
    ) -> bool:
        """
        Whether autonomy is paused.
        """

        return (
            self.status
            == AutonomyRuntimeStatus.PAUSED
        )

    @property
    def stopped(
        self,
    ) -> bool:
        """
        Whether autonomy is stopped.
        """

        return (
            self.status
            == AutonomyRuntimeStatus.STOPPED
        )

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize runtime state.
        """

        snapshot = self.snapshot()

        return {
            "runtime": snapshot.to_dict(),
            "actions": self.actions.to_list(),
            "triggers": self.triggers.to_list(),
            "schedules": self.scheduler.to_list(),
        }


# ================================================================
# FACTORY
# ================================================================


def create_autonomy_runtime(
    *,
    action_queue: ActionQueue | None = None,
    trigger_registry: TriggerRegistry | None = None,
    scheduler: Scheduler | None = None,
) -> AutonomyRuntime:
    """
    Create a configured autonomy runtime.

    No external capabilities are automatically registered.
    """

    return AutonomyRuntime(
        action_queue=action_queue,
        trigger_registry=trigger_registry,
        scheduler=scheduler,
    )


# ================================================================
# EXPORTS
# ================================================================


__all__ = [
    "AutonomyCycleResult",
    "AutonomyExecutionError",
    "AutonomyRuntime",
    "AutonomyRuntimeError",
    "AutonomyRuntimeSnapshot",
    "AutonomyRuntimeStateError",
    "AutonomyRuntimeStatus",
    "create_autonomy_runtime",
]