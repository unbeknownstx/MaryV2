"""
MaryV2 - Runtime State

Defines the shared state model used by Mary's runtime layer.

RuntimeState represents the overall runtime.
SubsystemState represents the state of an individual subsystem.

This module contains state only. It does not start, stop, or
control subsystems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any


# ================================================================
# RUNTIME STATUS
# ================================================================


class RuntimeStatus(str, Enum):
    """
    Overall runtime state.
    """

    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


# ================================================================
# SUBSYSTEM STATUS
# ================================================================


class SubsystemStatus(str, Enum):
    """
    State of an individual runtime subsystem.
    """

    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


# ================================================================
# SUBSYSTEM STATE
# ================================================================


@dataclass
class SubsystemState:
    """
    Runtime state for one subsystem.
    """

    name: str

    status: SubsystemStatus = (
        SubsystemStatus.CREATED
    )

    initialized: bool = False

    running: bool = False

    paused: bool = False

    last_error: str | None = None

    started_at: float | None = None

    stopped_at: float | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize subsystem state.
        """

        return {
            "name": self.name,
            "status": self.status.value,
            "initialized": self.initialized,
            "running": self.running,
            "paused": self.paused,
            "last_error": self.last_error,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "metadata": dict(self.metadata),
        }


# ================================================================
# RUNTIME STATE
# ================================================================


@dataclass
class RuntimeState:
    """
    Shared state for Mary's runtime.

    RuntimeState is deliberately passive.

    It stores state but does not perform lifecycle operations.
    """

    status: RuntimeStatus = (
        RuntimeStatus.CREATED
    )

    initialized: bool = False

    running: bool = False

    paused: bool = False

    turn_count: int = 0

    started_at: float | None = None

    stopped_at: float | None = None

    last_error: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    subsystems: dict[
        str,
        SubsystemState,
    ] = field(
        default_factory=dict
    )

    created_at: float = field(
        default_factory=time
    )

    def register_subsystem(
        self,
        name: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> SubsystemState:
        """
        Register a subsystem in runtime state.
        """

        if not name or not str(name).strip():
            raise ValueError(
                "Subsystem name cannot be empty."
            )

        name = str(name).strip()

        if name in self.subsystems:
            return self.subsystems[name]

        subsystem = SubsystemState(
            name=name,
            metadata=dict(
                metadata
                if metadata is not None
                else {}
            ),
        )

        self.subsystems[name] = subsystem

        return subsystem

    def get_subsystem(
        self,
        name: str,
    ) -> SubsystemState | None:
        """
        Return a registered subsystem state.
        """

        return self.subsystems.get(name)

    def remove_subsystem(
        self,
        name: str,
    ) -> bool:
        """
        Remove a subsystem from runtime state.
        """

        if name not in self.subsystems:
            return False

        del self.subsystems[name]

        return True

    def increment_turn(
        self,
    ) -> int:
        """
        Increment and return the runtime turn count.
        """

        self.turn_count += 1

        return self.turn_count

    def set_error(
        self,
        error: str | Exception,
    ) -> None:
        """
        Record a runtime error.
        """

        self.last_error = str(error)

        self.status = RuntimeStatus.ERROR

    def clear_error(
        self,
    ) -> None:
        """
        Clear the current runtime error.
        """

        self.last_error = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize the complete runtime state.
        """

        return {
            "status": self.status.value,
            "initialized": self.initialized,
            "running": self.running,
            "paused": self.paused,
            "turn_count": self.turn_count,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
            "subsystems": {
                name: subsystem.to_dict()
                for name, subsystem
                in self.subsystems.items()
            },
        }

    def subsystem_names(
        self,
    ) -> tuple[str, ...]:
        """
        Return registered subsystem names.
        """

        return tuple(
            self.subsystems.keys()
        )


__all__ = [
    "RuntimeStatus",
    "SubsystemStatus",
    "SubsystemState",
    "RuntimeState",
]
