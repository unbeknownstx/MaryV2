"""
MaryV2 Root Application

Mary is the root object of the system.

This class intentionally does NOT contain the responsibilities of the old
MaryV1 Brain. Mary owns the system's major components and lifecycle, while
specialized subsystems remain responsible for their own domains.
"""

from .config import Config
from .identity import Identity
from .lifecycle import Lifecycle


class Mary:
    """
    Root application object for MaryV2.
    """

    def __init__(
        self,
        config: Config | None = None,
        identity: Identity | None = None,
    ):
        self.config = (
            config
            if config is not None
            else Config.from_environment()
        )

        self.identity = (
            identity
            if identity is not None
            else Identity(
                name=self.config.application_name,
                version=self.config.version,
            )
        )

        self.lifecycle = Lifecycle()

        # Subsystems will be attached here as V2 develops.
        #
        # They are intentionally not constructed yet.
        #
        # self.cognition = ...
        # self.memory = ...
        # self.relationship = ...
        # self.personality = ...
        # self.agency = ...
        # self.learning = ...
        # self.knowledge = ...
        # self.tools = ...
        # self.llm = ...
        # self.perception = ...
        # self.autonomy = ...
        # self.expression = ...
        # self.voice = ...
        # self.avatar = ...

    def initialize(self):
        """
        Initialize Mary's foundational environment.

        Later this method will initialize the individual subsystems through
        their own lifecycle interfaces.
        """

        self.lifecycle.initialize()

        self.config.ensure_directories()

        self.lifecycle.ready()

    def wake(self):
        """Wake Mary after initialization."""

        self.lifecycle.wake()

    def start(self):
        """Start Mary's active runtime."""

        if self.lifecycle.state.value == "created":
            self.initialize()

        if self.lifecycle.state.value == "ready":
            self.wake()

        self.lifecycle.start()

    def shutdown(self):
        """Shut Mary down cleanly."""

        self.lifecycle.shutdown()
        self.lifecycle.stop()

    def status(self) -> dict:
        """Return a snapshot of Mary's current system state."""

        return {
            "name": self.identity.name,
            "version": self.identity.version,
            "creator": self.identity.creator,
            "state": self.lifecycle.state.value,
            "running": self.lifecycle.is_running,
        }

    def __repr__(self) -> str:
        return (
            f"<Mary "
            f"name={self.identity.name!r} "
            f"version={self.identity.version!r} "
            f"state={self.lifecycle.state.value!r}>"
        )