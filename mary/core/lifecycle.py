"""
MaryV2 Lifecycle

Controls Mary's high-level runtime state.

Subsystems such as cognition, memory, autonomy, voice, and avatar should
eventually integrate with this lifecycle rather than independently deciding
whether Mary is running.
"""

from enum import Enum
from datetime import datetime


class LifecycleState(Enum):
    """Possible states of the Mary runtime."""

    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    AWAKE = "awake"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


class Lifecycle:
    """
    Manages Mary's lifecycle state and transitions.
    """

    def __init__(self):
        self.state = LifecycleState.CREATED
        self.started_at = None
        self.stopped_at = None

    def transition(self, state: LifecycleState):
        """Transition Mary into a new lifecycle state."""

        self.state = state

        if state in {
            LifecycleState.AWAKE,
            LifecycleState.RUNNING,
        } and self.started_at is None:
            self.started_at = datetime.now().isoformat()

        if state == LifecycleState.STOPPED:
            self.stopped_at = datetime.now().isoformat()

    def initialize(self):
        """Move Mary into the initialization phase."""

        self.transition(
            LifecycleState.INITIALIZING
        )

    def ready(self):
        """Mark Mary as initialized and ready."""

        self.transition(
            LifecycleState.READY
        )

    def wake(self):
        """Wake Mary."""

        if self.state != LifecycleState.READY:
            raise RuntimeError(
                "Mary must be ready before she can wake."
            )

        self.transition(
            LifecycleState.AWAKE
        )

    def start(self):
        """Start Mary's active runtime."""

        if self.state != LifecycleState.AWAKE:
            raise RuntimeError(
                "Mary must be awake before the runtime can start."
            )

        self.transition(
            LifecycleState.RUNNING
        )

    def shutdown(self):
        """Begin Mary's shutdown sequence."""

        if self.state == LifecycleState.STOPPED:
            return

        self.transition(
            LifecycleState.SHUTTING_DOWN
        )

    def stop(self):
        """Mark Mary as completely stopped."""

        self.transition(
            LifecycleState.STOPPED
        )

    @property
    def is_running(self) -> bool:
        """Whether Mary is actively running."""

        return self.state == LifecycleState.RUNNING

    @property
    def is_awake(self) -> bool:
        """Whether Mary is awake or actively running."""

        return self.state in {
            LifecycleState.AWAKE,
            LifecycleState.RUNNING,
        }