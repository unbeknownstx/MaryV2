"""
MaryV2 - Root Application

Mary is the root object of the system.

Mary owns the system's major components and lifecycle,
while specialized subsystems remain responsible for
their own domains.
"""

from .config import Config
from .identity import Identity
from .lifecycle import Lifecycle

from ..personality.personality import Personality
from ..personality.values import Values
from ..personality.character import Character

from ..relationship.user import UserModel
from ..learning.learner import Learner
from ..knowledge.manager import KnowledgeManager
from ..memory.manager import MemoryManager


class Mary:
    """
    Root application object for MaryV2.
    """

    def __init__(
        self,
        config: Config | None = None,
        identity: Identity | None = None,
    ) -> None:

        # ========================================================
        # CORE CONFIGURATION
        # ========================================================

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

        # ========================================================
        # PERSONALITY
        # ========================================================

        self.personality = Personality(
            name=self.identity.name
        )

        self.values = Values()

        self.character = Character()

        # ========================================================
        # RELATIONSHIP
        # ========================================================

        self.relationship = UserModel(
            creator_id=self.identity.creator
        )

        # ========================================================
        # LEARNING
        # ========================================================

        self.learning = Learner()

        # ========================================================
        # KNOWLEDGE
        # ========================================================

        self.knowledge = KnowledgeManager()

        # ========================================================
        # MEMORY
        # ========================================================

        self.memory = MemoryManager()

        # ========================================================
        # FUTURE SUBSYSTEMS
        # ========================================================

        # These will be attached as MaryV2 develops.
        #
        # self.cognition = ...
        # self.development = ...
        # self.agency = ...
        # self.tools = ...
        # self.llm = ...
        # self.perception = ...
        # self.autonomy = ...
        # self.expression = ...
        # self.voice = ...
        # self.avatar = ...

    # ============================================================
    # LIFECYCLE
    # ============================================================

    def initialize(self) -> None:
        """
        Initialize Mary's foundational environment.

        Later this will initialize individual subsystems
        through their own lifecycle interfaces.
        """

        self.lifecycle.initialize()

        self.config.ensure_directories()

        # Initialize memory and other subsystems that support it.
        self.memory.initialize()

        self.lifecycle.ready()

    def wake(self) -> None:
        """
        Wake Mary after initialization.
        """

        self.lifecycle.wake()

    def start(self) -> None:
        """
        Start Mary's active runtime.
        """

        if self.lifecycle.state.value == "created":
            self.initialize()

        if self.lifecycle.state.value == "ready":
            self.wake()

        self.lifecycle.start()

    def shutdown(self) -> None:
        """
        Shut Mary down cleanly.
        """

        self.lifecycle.shutdown()
        self.lifecycle.stop()

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> dict:
        """
        Return a snapshot of Mary's current system state.
        """

        return {
            "name": self.identity.name,
            "version": self.identity.version,
            "creator": self.identity.creator,
            "state": self.lifecycle.state.value,
            "running": self.lifecycle.is_running,
        }

    # ============================================================
    # REPRESENTATION
    # ============================================================

    def __repr__(self) -> str:
        return (
            f"<Mary "
            f"name={self.identity.name!r} "
            f"version={self.identity.version!r} "
            f"state={self.lifecycle.state.value!r}>"
        )