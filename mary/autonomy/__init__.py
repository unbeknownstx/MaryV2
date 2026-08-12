"""
Mary - Autonomy Layer

Provides Mary's autonomous action, trigger, scheduling, and runtime
coordination systems.

This package does not automatically:

    - discover capabilities
    - access the internet
    - execute external tools
    - install anything
    - grant permissions

All external capability access must be explicitly registered and
approved by the surrounding system.
"""

from .actions import (
    Action,
    ActionError,
    ActionPermission,
    ActionPermissionError,
    ActionPriority,
    ActionQueue,
    ActionResult,
    ActionSource,
    ActionStatus,
    ActionType,
    ActionValidationError,
    create_action,
)

from .triggers import (
    ActionTrigger,
    ConditionTrigger,
    EventTrigger,
    StateTrigger,
    Trigger,
    TriggerContext,
    TriggerError,
    TriggerRegistry,
    TriggerResult,
    TriggerStatus,
    TriggerType,
    TriggerValidationError,
    ValueTrigger,
    create_condition_trigger,
    create_event_trigger,
    create_state_trigger,
)

from .scheduler import (
    ScheduleEntry,
    ScheduleError,
    ScheduleEvent,
    ScheduleStatus,
    ScheduleType,
    ScheduleValidationError,
    Scheduler,
    create_interval_schedule,
    create_one_time_schedule,
)

from .runtime import (
    AutonomyCycleResult,
    AutonomyExecutionError,
    AutonomyRuntime,
    AutonomyRuntimeError,
    AutonomyRuntimeSnapshot,
    AutonomyRuntimeStateError,
    AutonomyRuntimeStatus,
    create_autonomy_runtime,
)


__all__ = [
    # ============================================================
    # Actions
    # ============================================================

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

    # ============================================================
    # Triggers
    # ============================================================

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

    # ============================================================
    # Scheduler
    # ============================================================

    "ScheduleEntry",
    "ScheduleError",
    "ScheduleEvent",
    "ScheduleStatus",
    "ScheduleType",
    "ScheduleValidationError",
    "Scheduler",
    "create_interval_schedule",
    "create_one_time_schedule",

    # ============================================================
    # Runtime
    # ============================================================

    "AutonomyCycleResult",
    "AutonomyExecutionError",
    "AutonomyRuntime",
    "AutonomyRuntimeError",
    "AutonomyRuntimeSnapshot",
    "AutonomyRuntimeStateError",
    "AutonomyRuntimeStatus",
    "create_autonomy_runtime",
]