"""
MaryV2 - Root Application

Mary is the root object of the system.

Mary owns the major subsystems and their lifecycle.
Specialized systems remain responsible for their own domains.

The SelfModel provides Mary with a unified understanding of
how her identity, personality, character, values, canon,
and relationships fit together.
"""

from .config import Config
from .identity import Identity
from .lifecycle import Lifecycle

from mary.personality.personality import Personality
from mary.personality.character import Character
from mary.personality.values import Values

from mary.character.canon import Canon

from mary.relationship.user import UserModel

from mary.learning.learner import Learner
from mary.knowledge.manager import KnowledgeManager
from mary.memory.manager import MemoryManager

from mary.self.self import SelfModel


class Mary:
    """
    Root application object for MaryV2.
    """

    def __init__(
        self,
        config: Config | None = None,
        identity: Identity | None = None,
        personality: Personality | None = None,
        character: Character | None = None,
        values: Values | None = None,
        canon: Canon | None = None,
        relationship: UserModel | None = None,
        self_model: SelfModel | None = None,
    ) -> None:

        # ============================================================
        # CONFIGURATION
        # ============================================================

        self.config = (
            config
            if config is not None
            else Config.from_environment()
        )

        # ============================================================
        # IDENTITY
        # ============================================================

        self.identity = (
            identity
            if identity is not None
            else Identity(
                name=self.config.application_name,
                version=self.config.version,
            )
        )

        # ============================================================
        # PERSONALITY
        # ============================================================

        self.personality = (
            personality
            if personality is not None
            else Personality()
        )

        # ============================================================
        # CHARACTER
        # ============================================================

        self.character = (
            character
            if character is not None
            else Character()
        )

        # ============================================================
        # VALUES
        # ============================================================

        self.values = (
            values
            if values is not None
            else Values()
        )

        # ============================================================
        # FICTIONAL CANON
        # ============================================================

        self.canon = (
            canon
            if canon is not None
            else Canon(
                source="Unbe novel",
                character_name="Mary",
                fictional_age=21,
            )
        )

        # ============================================================
        # CREATOR RELATIONSHIP
        # ============================================================

        self.relationship = (
            relationship
            if relationship is not None
            else UserModel()
        )

        # ============================================================
        # LEARNING
        # ============================================================

        self.learning = Learner()

        # ============================================================
        # KNOWLEDGE
        # ============================================================

        self.knowledge = KnowledgeManager()

        # ============================================================
        # MEMORY
        # ============================================================

        self.memory = MemoryManager()

        # ============================================================
        # SELF MODEL
        # ============================================================

        self.self_model = (
            self_model
            if self_model is not None
            else SelfModel()
        )

        self.self_model.attach(
            identity=self.identity,
            personality=self.personality,
            character=self.character,
            values=self.values,
            canon=self.canon,
            relationship=self.relationship,
        )

        # ============================================================
        # LIFECYCLE
        # ============================================================

        self.lifecycle = Lifecycle()

    # ================================================================
    # INITIALIZATION
    # ================================================================

    def initialize(self) -> None:
        """
        Initialize Mary's foundational environment.
        """

        self.lifecycle.initialize()

        self.config.ensure_directories()

        self.lifecycle.ready()

    # ================================================================
    # RUNTIME
    # ================================================================

    def wake(self) -> None:
        """Wake Mary after initialization."""

        self.lifecycle.wake()

    def start(self) -> None:
        """Start Mary's active runtime."""

        if self.lifecycle.state.value == "created":
            self.initialize()

        if self.lifecycle.state.value == "ready":
            self.wake()

        self.lifecycle.start()

    def shutdown(self) -> None:
        """Shut Mary down cleanly."""

        self.lifecycle.shutdown()
        self.lifecycle.stop()

    # ================================================================
    # SELF
    # ================================================================

    def self_profile(self) -> dict:
        """
        Return Mary's unified self-profile.
        """

        return self.self_model.to_dict()

    def describe_self(self) -> str:
        """
        Return a human-readable description of Mary's
        current self-understanding.
        """

        return self.self_model.describe()

    def canon_vs_self(self) -> dict:
        """
        Distinguish Mary's fictional canon from her
        current self-model.
        """

        return self.self_model.distinguish_canon_from_self()

    # ================================================================
    # STATUS
    # ================================================================

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

    # ================================================================
    # REPRESENTATION
    # ================================================================

    def __repr__(self) -> str:
        return (
            f"<Mary "
            f"name={self.identity.name!r} "
            f"version={self.identity.version!r} "
            f"state={self.lifecycle.state.value!r}>"
        )