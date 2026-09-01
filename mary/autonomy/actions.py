"""
Mary - Autonomy Actions

Defines the actions that Mary's autonomy system can represent.

This module describes actions; it does not automatically execute them.

Important capability rule:

    An Action is only a description of something Mary may want to do.

    Creating an Action does NOT:
        - execute anything
        - access the internet
        - access the filesystem
        - invoke a tool
        - create a new capability
        - grant permission to a capability

Actual execution must be handled by an explicitly registered and
approved action handler elsewhere in the system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Mapping
from uuid import uuid4


# ================================================================
# ACTION TYPES
# ================================================================


class ActionType(str, Enum):
    """
    Broad category describing what an action represents.
    """

    INTERNAL = "internal"
    COMMUNICATION = "communication"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    OBSERVATION = "observation"
    TASK = "task"
    SYSTEM = "system"
    TOOL = "tool"


# ================================================================
# ACTION PRIORITY
# ================================================================


class ActionPriority(str, Enum):
    """
    Priority assigned to an autonomous action.
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ================================================================
# ACTION STATUS
# ================================================================


class ActionStatus(str, Enum):
    """
    Current state of an action.
    """

    CREATED = "created"
    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


# ================================================================
# ACTION SOURCE
# ================================================================


class ActionSource(str, Enum):
    """
    Where an autonomous action originated.
    """

    GOAL = "goal"
    INTENTION = "intention"
    TRIGGER = "trigger"
    SCHEDULE = "schedule"
    REFLECTION = "reflection"
    USER = "user"
    SYSTEM = "system"
    MANUAL = "manual"


# ================================================================
# ACTION PERMISSION
# ================================================================


class ActionPermission(str, Enum):
    """
    Permission state for an action.

    Permission is deliberately separate from action creation.

    Creating an action does not imply permission to execute it.
    """

    UNSPECIFIED = "unspecified"
    REQUIRED = "required"
    APPROVED = "approved"
    DENIED = "denied"


# ================================================================
# ACTION ERROR
# ================================================================


class ActionError(RuntimeError):
    """
    Base exception for action-related failures.
    """


class ActionValidationError(ActionError):
    """
    Raised when an action is invalid.
    """


class ActionPermissionError(ActionError):
    """
    Raised when execution is attempted without appropriate
    permission.
    """


# ================================================================
# ACTION RESULT
# ================================================================


@dataclass
class ActionResult:
    """
    Result produced after an action has been processed.

    This is a data object only. It does not execute anything.
    """

    success: bool

    action_id: str

    status: ActionStatus

    output: Any = None

    error: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    started_at: float | None = None

    completed_at: float | None = None

    @property
    def elapsed(self) -> float | None:
        """
        Return execution duration when timestamps are available.
        """

        if (
            self.started_at is None
            or self.completed_at is None
        ):
            return None

        return max(
            0.0,
            self.completed_at - self.started_at,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Convert the result to a serializable dictionary.
        """

        return {
            "success": self.success,
            "action_id": self.action_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "metadata": dict(self.metadata),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed": self.elapsed,
        }


# ================================================================
# ACTION
# ================================================================


@dataclass
class Action:
    """
    Represents something Mary may choose to do.

    An Action is intentionally passive.

    It describes an intended operation without executing it.
    """

    name: str

    action_type: ActionType = ActionType.INTERNAL

    priority: ActionPriority = ActionPriority.NORMAL

    source: ActionSource = ActionSource.SYSTEM

    description: str = ""

    parameters: dict[str, Any] = field(
        default_factory=dict
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    permission: ActionPermission = (
        ActionPermission.UNSPECIFIED
    )

    action_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    status: ActionStatus = ActionStatus.CREATED

    created_at: float = field(
        default_factory=time
    )

    scheduled_for: float | None = None

    expires_at: float | None = None

    attempts: int = 0

    max_attempts: int = 1

    parent_action_id: str | None = None

    # ------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------

    def validate(self) -> None:
        """
        Validate the action definition.

        This performs no external operation.
        """

        if not self.name.strip():
            raise ActionValidationError(
                "Action name cannot be empty."
            )

        if self.max_attempts < 1:
            raise ActionValidationError(
                "max_attempts must be at least 1."
            )

        if self.attempts < 0:
            raise ActionValidationError(
                "attempts cannot be negative."
            )

        if (
            self.expires_at is not None
            and self.scheduled_for is not None
            and self.expires_at < self.scheduled_for
        ):
            raise ActionValidationError(
                "expires_at cannot occur before scheduled_for."
            )

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------

    def mark_pending(self) -> None:
        """
        Mark the action as pending.
        """

        self.validate()

        if self.status in {
            ActionStatus.COMPLETED,
            ActionStatus.CANCELLED,
            ActionStatus.REJECTED,
        }:
            raise ActionError(
                (
                    f"Cannot mark action '{self.action_id}' "
                    f"as pending from status '{self.status.value}'."
                )
            )

        self.status = ActionStatus.PENDING

    def approve(self) -> None:
        """
        Explicitly approve an action for execution.

        Approval here records permission; it does not execute the
        action.
        """

        self.permission = (
            ActionPermission.APPROVED
        )

        self.status = ActionStatus.APPROVED

    def deny(self) -> None:
        """
        Explicitly deny an action.
        """

        self.permission = (
            ActionPermission.DENIED
        )

        self.status = ActionStatus.REJECTED

    def cancel(self) -> None:
        """
        Cancel the action.
        """

        if self.status in {
            ActionStatus.COMPLETED,
            ActionStatus.FAILED,
            ActionStatus.REJECTED,
        }:
            return

        self.status = ActionStatus.CANCELLED

    def expire(self) -> None:
        """
        Mark the action as expired.
        """

        if self.status in {
            ActionStatus.COMPLETED,
            ActionStatus.FAILED,
            ActionStatus.CANCELLED,
            ActionStatus.REJECTED,
        }:
            return

        self.status = ActionStatus.EXPIRED

    # ------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------

    def schedule(
        self,
        when: float,
    ) -> None:
        """
        Assign a scheduled execution timestamp.

        Scheduling does not execute the action.
        """

        if when < 0:
            raise ActionValidationError(
                "Scheduled timestamp cannot be negative."
            )

        self.scheduled_for = when

        if self.status == ActionStatus.CREATED:
            self.status = ActionStatus.PENDING

    def is_due(
        self,
        now: float | None = None,
    ) -> bool:
        """
        Return whether the action is currently due.
        """

        current_time = (
            time()
            if now is None
            else now
        )

        if self.status not in {
            ActionStatus.PENDING,
            ActionStatus.APPROVED,
        }:
            return False

        if (
            self.scheduled_for is not None
            and current_time < self.scheduled_for
        ):
            return False

        if (
            self.expires_at is not None
            and current_time > self.expires_at
        ):
            return False

        return True

    def is_expired(
        self,
        now: float | None = None,
    ) -> bool:
        """
        Return whether the action has passed its expiration time.
        """

        if self.expires_at is None:
            return False

        current_time = (
            time()
            if now is None
            else now
        )

        return current_time > self.expires_at

    # ------------------------------------------------------------
    # Attempts
    # ------------------------------------------------------------

    @property
    def can_attempt(
        self,
    ) -> bool:
        """
        Return whether another execution attempt is allowed.
        """

        return (
            self.attempts
            < self.max_attempts
        )

    def begin_attempt(self) -> None:
        """
        Record that an execution attempt has begun.

        This does not execute the action.
        """

        if not self.can_attempt:
            raise ActionError(
                (
                    f"Action '{self.action_id}' "
                    "has reached its maximum attempts."
                )
            )

        if self.permission != (
            ActionPermission.APPROVED
        ):
            raise ActionPermissionError(
                (
                    f"Action '{self.action_id}' "
                    "has not been approved."
                )
            )

        if self.status in {
            ActionStatus.CANCELLED,
            ActionStatus.REJECTED,
            ActionStatus.EXPIRED,
            ActionStatus.COMPLETED,
        }:
            raise ActionError(
                (
                    f"Action '{self.action_id}' "
                    f"cannot run from status "
                    f"'{self.status.value}'."
                )
            )

        self.attempts += 1

        self.status = ActionStatus.RUNNING

    # ------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------

    def complete(self) -> None:
        """
        Mark the action as completed.
        """

        self.status = ActionStatus.COMPLETED

    def fail(self) -> None:
        """
        Mark the action as failed.
        """

        self.status = ActionStatus.FAILED

    # ------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Convert the action to a serializable dictionary.
        """

        return {
            "action_id": self.action_id,
            "name": self.name,
            "action_type": self.action_type.value,
            "priority": self.priority.value,
            "source": self.source.value,
            "description": self.description,
            "parameters": dict(self.parameters),
            "metadata": dict(self.metadata),
            "permission": self.permission.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "scheduled_for": self.scheduled_for,
            "expires_at": self.expires_at,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "parent_action_id": self.parent_action_id,
        }

    # ------------------------------------------------------------
    # Copy
    # ------------------------------------------------------------

    def clone(
        self,
        *,
        name: str | None = None,
        parameters: Mapping[
            str,
            Any,
        ]
        | None = None,
    ) -> "Action":
        """
        Create a new independent action based on this action.

        The new action receives a new ID and starts unapproved.
        """

        new_parameters = dict(
            self.parameters
        )

        if parameters is not None:
            new_parameters.update(
                parameters
            )

        return Action(
            name=(
                self.name
                if name is None
                else name
            ),
            action_type=self.action_type,
            priority=self.priority,
            source=self.source,
            description=self.description,
            parameters=new_parameters,
            metadata=dict(
                self.metadata
            ),
            permission=(
                ActionPermission.UNSPECIFIED
            ),
            max_attempts=self.max_attempts,
            parent_action_id=self.action_id,
        )


# ================================================================
# ACTION FACTORY
# ================================================================


def create_action(
    name: str,
    *,
    action_type: ActionType = ActionType.INTERNAL,
    priority: ActionPriority = ActionPriority.NORMAL,
    source: ActionSource = ActionSource.SYSTEM,
    description: str = "",
    parameters: Mapping[
        str,
        Any,
    ]
    | None = None,
    metadata: Mapping[
        str,
        Any,
    ]
    | None = None,
    permission: ActionPermission = (
        ActionPermission.UNSPECIFIED
    ),
    scheduled_for: float | None = None,
    expires_at: float | None = None,
    max_attempts: int = 1,
) -> Action:
    """
    Create and validate an Action.

    Creation never executes the resulting action.
    """

    action = Action(
        name=name,
        action_type=action_type,
        priority=priority,
        source=source,
        description=description,
        parameters=dict(
            parameters
            if parameters is not None
            else {}
        ),
        metadata=dict(
            metadata
            if metadata is not None
            else {}
        ),
        permission=permission,
        scheduled_for=scheduled_for,
        expires_at=expires_at,
        max_attempts=max_attempts,
    )

    action.validate()

    if scheduled_for is not None:
        action.status = (
            ActionStatus.PENDING
        )

    return action


# ================================================================
# ACTION COLLECTION
# ================================================================


class ActionQueue:
    """
    In-memory collection of autonomous actions.

    This class only stores and retrieves action definitions.

    It does not execute actions.
    """

    def __init__(self) -> None:

        self._actions: dict[
            str,
            Action,
        ] = {}

    # ------------------------------------------------------------
    # Add
    # ------------------------------------------------------------

    def add(
        self,
        action: Action,
    ) -> None:
        """
        Add an action to the queue.
        """

        action.validate()

        if action.action_id in self._actions:
            raise ActionError(
                (
                    f"Action already exists: "
                    f"{action.action_id}"
                )
            )

        self._actions[
            action.action_id
        ] = action

    # ------------------------------------------------------------
    # Get
    # ------------------------------------------------------------

    def get(
        self,
        action_id: str,
    ) -> Action | None:
        """
        Retrieve an action by ID.
        """

        return self._actions.get(
            action_id
        )

    def require(
        self,
        action_id: str,
    ) -> Action:
        """
        Retrieve an action or raise an error.
        """

        action = self.get(
            action_id
        )

        if action is None:
            raise ActionError(
                (
                    f"Unknown action: "
                    f"{action_id}"
                )
            )

        return action

    # ------------------------------------------------------------
    # Remove
    # ------------------------------------------------------------

    def remove(
        self,
        action_id: str,
    ) -> bool:
        """
        Remove an action from the queue.
        """

        if action_id not in self._actions:
            return False

        del self._actions[
            action_id
        ]

        return True

    # ------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------

    def all(
        self,
    ) -> tuple[Action, ...]:
        """
        Return all stored actions.
        """

        return tuple(
            self._actions.values()
        )

    def pending(
        self,
    ) -> tuple[Action, ...]:
        """
        Return pending actions.
        """

        return tuple(
            action
            for action
            in self._actions.values()
            if action.status
            == ActionStatus.PENDING
        )

    def approved(
        self,
    ) -> tuple[Action, ...]:
        """
        Return approved actions.
        """

        return tuple(
            action
            for action
            in self._actions.values()
            if action.status
            == ActionStatus.APPROVED
        )

    def due(
        self,
        now: float | None = None,
    ) -> tuple[Action, ...]:
        """
        Return actions currently due for consideration.
        """

        current_time = (
            time()
            if now is None
            else now
        )

        due_actions = [
            action
            for action
            in self._actions.values()
            if action.is_due(
                current_time
            )
        ]

        due_actions.sort(
            key=lambda action: (
                -self._priority_value(
                    action.priority
                ),
                (
                    action.scheduled_for
                    if action.scheduled_for
                    is not None
                    else 0
                ),
                action.created_at,
            )
        )

        return tuple(
            due_actions
        )

    # ------------------------------------------------------------
    # Size
    # ------------------------------------------------------------

    def __len__(
        self,
    ) -> int:
        return len(
            self._actions
        )

    # ------------------------------------------------------------
    # Priority helper
    # ------------------------------------------------------------

    @staticmethod
    def _priority_value(
        priority: ActionPriority,
    ) -> int:

        values = {
            ActionPriority.LOW: 1,
            ActionPriority.NORMAL: 2,
            ActionPriority.HIGH: 3,
            ActionPriority.CRITICAL: 4,
        }

        return values[
            priority
        ]

    # ------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------

    def to_list(
        self,
    ) -> list[dict[str, Any]]:
        """
        Serialize all actions.
        """

        return [
            action.to_dict()
            for action
            in self._actions.values()
        ]


# ================================================================
# EXPORTS
# ================================================================


__all__ = [
    "Action",
    "ActionError",
    "ActionPermission",
    "ActionPermissionError",
    "ActionPriority",
    "ActionQueue",
    "ActionResult",
    "ActionSource",
    "ActionStatus",
    "ActionType",
    "ActionValidationError",
    "create_action",
]