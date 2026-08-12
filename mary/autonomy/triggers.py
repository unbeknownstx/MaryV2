"""
Mary - Autonomy Triggers

Defines the conditions that can cause Mary's autonomy system to
consider creating or activating an action.

Triggers are passive definitions.

They do NOT:

    - execute actions
    - access the internet
    - access tools
    - modify the filesystem
    - create capabilities
    - bypass permissions
    - automatically approve actions

A trigger only answers:

    "Is this condition satisfied?"

The autonomy runtime is responsible for deciding what to do with
that information.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Callable, Mapping
from uuid import uuid4

from .actions import (
    Action,
    ActionPriority,
    ActionSource,
    ActionType,
    create_action,
)


# ================================================================
# TRIGGER TYPES
# ================================================================


class TriggerType(str, Enum):
    """
    Broad category of trigger.
    """

    EVENT = "event"
    CONDITION = "condition"
    SCHEDULE = "schedule"
    STATE = "state"
    GOAL = "goal"
    TIME = "time"
    USER = "user"
    INTERNAL = "internal"


# ================================================================
# TRIGGER STATUS
# ================================================================


class TriggerStatus(str, Enum):
    """
    Current state of a trigger.
    """

    ENABLED = "enabled"
    DISABLED = "disabled"
    FIRED = "fired"
    EXPIRED = "expired"


# ================================================================
# TRIGGER ERROR
# ================================================================


class TriggerError(RuntimeError):
    """
    Base trigger exception.
    """


class TriggerValidationError(TriggerError):
    """
    Raised when a trigger is invalid.
    """


# ================================================================
# TRIGGER CONTEXT
# ================================================================


@dataclass
class TriggerContext:
    """
    Information available while evaluating a trigger.

    This is deliberately generic so the trigger system does not
    need to know the internals of every Mary subsystem.
    """

    event: Any = None

    state: Any = None

    values: dict[str, Any] = field(
        default_factory=dict
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    timestamp: float = field(
        default_factory=time
    )

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Retrieve a context value.
        """

        return self.values.get(
            key,
            default,
        )

    def set(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        Store a context value.
        """

        self.values[key] = value


# ================================================================
# TRIGGER RESULT
# ================================================================


@dataclass
class TriggerResult:
    """
    Result of evaluating a trigger.
    """

    triggered: bool

    trigger_id: str

    timestamp: float = field(
        default_factory=time
    )

    action: Action | None = None

    reason: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "triggered": self.triggered,
            "trigger_id": self.trigger_id,
            "timestamp": self.timestamp,
            "action": (
                self.action.to_dict()
                if self.action is not None
                else None
            ),
            "reason": self.reason,
            "metadata": dict(
                self.metadata
            ),
        }


# ================================================================
# BASE TRIGGER
# ================================================================


class Trigger(ABC):
    """
    Base class for all autonomy triggers.
    """

    trigger_type: TriggerType = (
        TriggerType.INTERNAL
    )

    def __init__(
        self,
        name: str,
        *,
        description: str = "",
        enabled: bool = True,
        one_shot: bool = False,
        expires_at: float | None = None,
        metadata: Mapping[
            str,
            Any,
        ]
        | None = None,
        trigger_id: str | None = None,
    ) -> None:

        self.trigger_id = (
            trigger_id
            if trigger_id is not None
            else str(uuid4())
        )

        self.name = name

        self.description = (
            description
        )

        self.enabled = enabled

        self.one_shot = one_shot

        self.expires_at = expires_at

        self.metadata: dict[
            str,
            Any,
        ] = dict(
            metadata
            if metadata is not None
            else {}
        )

        self.status = (
            TriggerStatus.ENABLED
            if enabled
            else TriggerStatus.DISABLED
        )

        self.fire_count = 0

        self.created_at = time()

        self.last_fired_at: float | None = None

    # ------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------

    def validate(self) -> None:
        """
        Validate the trigger definition.
        """

        if not self.name.strip():
            raise TriggerValidationError(
                "Trigger name cannot be empty."
            )

        if (
            self.expires_at is not None
            and self.expires_at
            < self.created_at
        ):
            raise TriggerValidationError(
                "Trigger expiration cannot be before creation."
            )

    # ------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------

    @abstractmethod
    def evaluate(
        self,
        context: TriggerContext,
    ) -> bool:
        """
        Determine whether the trigger condition is satisfied.
        """

    # ------------------------------------------------------------
    # Action creation
    # ------------------------------------------------------------

    def build_action(
        self,
        context: TriggerContext,
    ) -> Action | None:
        """
        Optionally create an action after the trigger fires.

        The resulting action is NOT approved and NOT executed.
        """

        return None

    # ------------------------------------------------------------
    # Fire
    # ------------------------------------------------------------

    def check(
        self,
        context: TriggerContext | None = None,
    ) -> TriggerResult:
        """
        Evaluate the trigger and return a TriggerResult.
        """

        self.validate()

        if context is None:
            context = TriggerContext()

        now = context.timestamp

        if not self.enabled:
            return TriggerResult(
                triggered=False,
                trigger_id=self.trigger_id,
                timestamp=now,
                reason="Trigger is disabled.",
            )

        if self.status == TriggerStatus.EXPIRED:
            return TriggerResult(
                triggered=False,
                trigger_id=self.trigger_id,
                timestamp=now,
                reason="Trigger has expired.",
            )

        if (
            self.expires_at is not None
            and now > self.expires_at
        ):
            self.status = (
                TriggerStatus.EXPIRED
            )

            return TriggerResult(
                triggered=False,
                trigger_id=self.trigger_id,
                timestamp=now,
                reason="Trigger has expired.",
            )

        if (
            self.one_shot
            and self.fire_count > 0
        ):
            return TriggerResult(
                triggered=False,
                trigger_id=self.trigger_id,
                timestamp=now,
                reason="One-shot trigger has already fired.",
            )

        triggered = bool(
            self.evaluate(context)
        )

        if not triggered:
            return TriggerResult(
                triggered=False,
                trigger_id=self.trigger_id,
                timestamp=now,
                reason="Condition not satisfied.",
            )

        action = self.build_action(
            context
        )

        self.fire_count += 1

        self.last_fired_at = now

        if self.one_shot:
            self.status = (
                TriggerStatus.FIRED
            )

        return TriggerResult(
            triggered=True,
            trigger_id=self.trigger_id,
            timestamp=now,
            action=action,
            reason=(
                "Trigger condition satisfied."
            ),
            metadata=dict(
                self.metadata
            ),
        )

    # ------------------------------------------------------------
    # Enable / disable
    # ------------------------------------------------------------

    def enable(self) -> None:
        """
        Enable the trigger.
        """

        if self.status == TriggerStatus.EXPIRED:
            raise TriggerError(
                "An expired trigger cannot be enabled."
            )

        self.enabled = True

        self.status = (
            TriggerStatus.ENABLED
        )

    def disable(self) -> None:
        """
        Disable the trigger.
        """

        self.enabled = False

        self.status = (
            TriggerStatus.DISABLED
        )

    # ------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "trigger_id": self.trigger_id,
            "name": self.name,
            "trigger_type": self.trigger_type.value,
            "description": self.description,
            "enabled": self.enabled,
            "one_shot": self.one_shot,
            "expires_at": self.expires_at,
            "status": self.status.value,
            "fire_count": self.fire_count,
            "created_at": self.created_at,
            "last_fired_at": self.last_fired_at,
            "metadata": dict(
                self.metadata
            ),
        }


# ================================================================
# CONDITION TRIGGER
# ================================================================


class ConditionTrigger(Trigger):
    """
    Trigger based on a callable condition.

    The callable must only evaluate the supplied context.
    """

    trigger_type = (
        TriggerType.CONDITION
    )

    def __init__(
        self,
        name: str,
        condition: Callable[
            [TriggerContext],
            bool,
        ],
        *,
        description: str = "",
        enabled: bool = True,
        one_shot: bool = False,
        expires_at: float | None = None,
        metadata: Mapping[
            str,
            Any,
        ]
        | None = None,
    ) -> None:

        super().__init__(
            name,
            description=description,
            enabled=enabled,
            one_shot=one_shot,
            expires_at=expires_at,
            metadata=metadata,
        )

        self.condition = condition

    def evaluate(
        self,
        context: TriggerContext,
    ) -> bool:

        return bool(
            self.condition(context)
        )


# ================================================================
# EVENT TRIGGER
# ================================================================


class EventTrigger(Trigger):
    """
    Trigger when an event matches a specified event name.

    Event matching is local to the supplied TriggerContext.
    """

    trigger_type = (
        TriggerType.EVENT
    )

    def __init__(
        self,
        name: str,
        event_name: str,
        *,
        description: str = "",
        enabled: bool = True,
        one_shot: bool = False,
        expires_at: float | None = None,
        metadata: Mapping[
            str,
            Any,
        ]
        | None = None,
    ) -> None:

        super().__init__(
            name,
            description=description,
            enabled=enabled,
            one_shot=one_shot,
            expires_at=expires_at,
            metadata=metadata,
        )

        self.event_name = event_name

    def evaluate(
        self,
        context: TriggerContext,
    ) -> bool:

        event = context.event

        if event is None:
            return False

        if isinstance(
            event,
            str,
        ):
            return event == self.event_name

        if isinstance(
            event,
            Mapping,
        ):
            return (
                event.get("name")
                == self.event_name
            )

        event_name = getattr(
            event,
            "name",
            None,
        )

        return event_name == self.event_name

    def to_dict(
        self,
    ) -> dict[str, Any]:

        data = super().to_dict()

        data["event_name"] = (
            self.event_name
        )

        return data


# ================================================================
# STATE TRIGGER
# ================================================================


class StateTrigger(Trigger):
    """
    Trigger based on a value in TriggerContext.
    """

    trigger_type = (
        TriggerType.STATE
    )

    def __init__(
        self,
        name: str,
        key: str,
        expected: Any,
        *,
        description: str = "",
        enabled: bool = True,
        one_shot: bool = False,
        expires_at: float | None = None,
        metadata: Mapping[
            str,
            Any,
        ]
        | None = None,
    ) -> None:

        super().__init__(
            name,
            description=description,
            enabled=enabled,
            one_shot=one_shot,
            expires_at=expires_at,
            metadata=metadata,
        )

        self.key = key

        self.expected = expected

    def evaluate(
        self,
        context: TriggerContext,
    ) -> bool:

        return (
            context.get(
                self.key
            )
            == self.expected
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:

        data = super().to_dict()

        data["key"] = self.key

        data["expected"] = (
            self.expected
        )

        return data


# ================================================================
# VALUE TRIGGER
# ================================================================


class ValueTrigger(Trigger):
    """
    Trigger based on a numeric value crossing a threshold.
    """

    trigger_type = (
        TriggerType.CONDITION
    )

    def __init__(
        self,
        name: str,
        key: str,
        threshold: float,
        *,
        operator: str = ">=",
        description: str = "",
        enabled: bool = True,
        one_shot: bool = False,
        expires_at: float | None = None,
        metadata: Mapping[
            str,
            Any,
        ]
        | None = None,
    ) -> None:

        super().__init__(
            name,
            description=description,
            enabled=enabled,
            one_shot=one_shot,
            expires_at=expires_at,
            metadata=metadata,
        )

        self.key = key

        self.threshold = threshold

        self.operator = operator

        if operator not in {
            ">",
            ">=",
            "<",
            "<=",
            "==",
            "!=",
        }:
            raise TriggerValidationError(
                (
                    "Unsupported comparison operator: "
                    f"{operator}"
                )
            )

    def evaluate(
        self,
        context: TriggerContext,
    ) -> bool:

        value = context.get(
            self.key
        )

        if value is None:
            return False

        try:
            numeric_value = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return False

        if self.operator == ">":
            return numeric_value > self.threshold

        if self.operator == ">=":
            return numeric_value >= self.threshold

        if self.operator == "<":
            return numeric_value < self.threshold

        if self.operator == "<=":
            return numeric_value <= self.threshold

        if self.operator == "==":
            return numeric_value == self.threshold

        if self.operator == "!=":
            return numeric_value != self.threshold

        return False

    def to_dict(
        self,
    ) -> dict[str, Any]:

        data = super().to_dict()

        data["key"] = self.key

        data["threshold"] = (
            self.threshold
        )

        data["operator"] = (
            self.operator
        )

        return data


# ================================================================
# ACTION TRIGGER
# ================================================================


class ActionTrigger(Trigger):
    """
    Trigger that creates a predefined Action when its condition
    is satisfied.

    The resulting action is still unapproved.
    """

    trigger_type = (
        TriggerType.INTERNAL
    )

    def __init__(
        self,
        name: str,
        action_name: str,
        *,
        condition: Callable[
            [TriggerContext],
            bool,
        ]
        | None = None,
        action_type: ActionType = ActionType.INTERNAL,
        priority: ActionPriority = ActionPriority.NORMAL,
        description: str = "",
        action_description: str = "",
        parameters: Mapping[
            str,
            Any,
        ]
        | None = None,
        enabled: bool = True,
        one_shot: bool = False,
        expires_at: float | None = None,
        metadata: Mapping[
            str,
            Any,
        ]
        | None = None,
    ) -> None:

        super().__init__(
            name,
            description=description,
            enabled=enabled,
            one_shot=one_shot,
            expires_at=expires_at,
            metadata=metadata,
        )

        self.action_name = action_name

        self.condition = condition

        self.action_type = (
            action_type
        )

        self.priority = priority

        self.action_description = (
            action_description
        )

        self.parameters = dict(
            parameters
            if parameters is not None
            else {}
        )

    def evaluate(
        self,
        context: TriggerContext,
    ) -> bool:

        if self.condition is None:
            return True

        return bool(
            self.condition(context)
        )

    def build_action(
        self,
        context: TriggerContext,
    ) -> Action:

        return create_action(
            self.action_name,
            action_type=self.action_type,
            priority=self.priority,
            source=ActionSource.TRIGGER,
            description=self.action_description,
            parameters=self.parameters,
            metadata={
                "trigger_id": self.trigger_id,
                **self.metadata,
            },
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:

        data = super().to_dict()

        data["action_name"] = (
            self.action_name
        )

        data["action_type"] = (
            self.action_type.value
        )

        data["priority"] = (
            self.priority.value
        )

        data["action_description"] = (
            self.action_description
        )

        data["parameters"] = dict(
            self.parameters
        )

        return data


# ================================================================
# TRIGGER REGISTRY
# ================================================================


class TriggerRegistry:
    """
    Explicit registry of autonomy triggers.

    Triggers must be registered by the application.

    No automatic discovery occurs.
    """

    def __init__(self) -> None:

        self._triggers: dict[
            str,
            Trigger,
        ] = {}

    # ------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------

    def register(
        self,
        trigger: Trigger,
    ) -> None:
        """
        Register a trigger.
        """

        trigger.validate()

        if trigger.trigger_id in self._triggers:
            raise TriggerError(
                (
                    f"Trigger already registered: "
                    f"{trigger.trigger_id}"
                )
            )

        self._triggers[
            trigger.trigger_id
        ] = trigger

    def unregister(
        self,
        trigger_id: str,
    ) -> bool:
        """
        Remove a trigger.
        """

        if trigger_id not in self._triggers:
            return False

        del self._triggers[
            trigger_id
        ]

        return True

    # ------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------

    def get(
        self,
        trigger_id: str,
    ) -> Trigger | None:

        return self._triggers.get(
            trigger_id
        )

    def require(
        self,
        trigger_id: str,
    ) -> Trigger:

        trigger = self.get(
            trigger_id
        )

        if trigger is None:
            raise TriggerError(
                (
                    f"Unknown trigger: "
                    f"{trigger_id}"
                )
            )

        return trigger

    def all(
        self,
    ) -> tuple[Trigger, ...]:

        return tuple(
            self._triggers.values()
        )

    # ------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------

    def evaluate_all(
        self,
        context: TriggerContext,
    ) -> tuple[TriggerResult, ...]:
        """
        Evaluate every registered trigger.

        Evaluation only.

        No resulting action is automatically approved or executed.
        """

        results: list[
            TriggerResult
        ] = []

        for trigger in self._triggers.values():

            result = trigger.check(
                context
            )

            results.append(
                result
            )

        return tuple(
            results
        )

    def evaluate_trigger(
        self,
        trigger_id: str,
        context: TriggerContext,
    ) -> TriggerResult:

        trigger = self.require(
            trigger_id
        )

        return trigger.check(
            context
        )

    # ------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------

    def enabled(
        self,
    ) -> tuple[Trigger, ...]:

        return tuple(
            trigger
            for trigger
            in self._triggers.values()
            if trigger.enabled
        )

    def disabled(
        self,
    ) -> tuple[Trigger, ...]:

        return tuple(
            trigger
            for trigger
            in self._triggers.values()
            if not trigger.enabled
        )

    # ------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------

    def to_list(
        self,
    ) -> list[dict[str, Any]]:

        return [
            trigger.to_dict()
            for trigger
            in self._triggers.values()
        ]


# ================================================================
# FACTORIES
# ================================================================


def create_condition_trigger(
    name: str,
    condition: Callable[
        [TriggerContext],
        bool,
    ],
    *,
    description: str = "",
    one_shot: bool = False,
    expires_at: float | None = None,
) -> ConditionTrigger:
    """
    Create a condition trigger.
    """

    trigger = ConditionTrigger(
        name,
        condition,
        description=description,
        one_shot=one_shot,
        expires_at=expires_at,
    )

    trigger.validate()

    return trigger


def create_event_trigger(
    name: str,
    event_name: str,
    *,
    description: str = "",
    one_shot: bool = False,
    expires_at: float | None = None,
) -> EventTrigger:
    """
    Create an event trigger.
    """

    trigger = EventTrigger(
        name,
        event_name,
        description=description,
        one_shot=one_shot,
        expires_at=expires_at,
    )

    trigger.validate()

    return trigger


def create_state_trigger(
    name: str,
    key: str,
    expected: Any,
    *,
    description: str = "",
    one_shot: bool = False,
    expires_at: float | None = None,
) -> StateTrigger:
    """
    Create a state trigger.
    """

    trigger = StateTrigger(
        name,
        key,
        expected,
        description=description,
        one_shot=one_shot,
        expires_at=expires_at,
    )

    trigger.validate()

    return trigger


# ================================================================
# EXPORTS
# ================================================================


__all__ = [
    "ActionTrigger",
    "ConditionTrigger",
    "EventTrigger",
    "StateTrigger",
    "Trigger",
    "TriggerContext",
    "TriggerError",
    "TriggerRegistry",
    "TriggerResult",
    "TriggerStatus",
    "TriggerType",
    "TriggerValidationError",
    "ValueTrigger",
    "create_condition_trigger",
    "create_event_trigger",
    "create_state_trigger",
]