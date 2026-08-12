"""
MaryV2 - Root Application

Mary is the root object of the system.

Mary owns the major subsystems and their lifecycle, while each
specialized subsystem remains responsible for its own domain.

Character represents how Mary expresses herself.

Canon represents the fictional source material from which Mary's
character originated.

These systems are related, but they are intentionally distinct.
"""

from .config import Config
from .identity import Identity
from .lifecycle import Lifecycle

from ..personality.personality import Personality
from ..personality.character import Character
from ..personality.values import Values

from ..character.canon import Canon

from ..relationship.user import UserModel
from ..learning.learner import Learner
from ..knowledge.manager import KnowledgeManager
from ..memory.manager import MemoryManager


class Mary:
    """
    Root application object for MaryV2.

    Mary coordinates the major systems but does not replace
    their individual responsibilities.
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
        learning: Learner | None = None,
        knowledge: KnowledgeManager | None = None,
        memory: MemoryManager | None = None,
    ):
        # ============================================================
        # CORE
        # ============================================================

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

        # ============================================================
        # PERSONALITY
        # ============================================================

        self.personality = (
            personality
            if personality is not None
            else Personality(
                name=self.identity.name
            )
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
        # CANON
        # ============================================================

        self.canon = (
            canon
            if canon is not None
            else Canon(
                source="Unbe novel",
                character_name=self.identity.name,
                fictional_age=21,
            )
        )

        # ============================================================
        # RELATIONSHIP
        # ============================================================

        self.relationship = (
            relationship
            if relationship is not None
            else UserModel()
        )

        # ============================================================
        # LEARNING
        # ============================================================

        self.learning = (
            learning
            if learning is not None
            else Learner()
        )

        # ============================================================
        # KNOWLEDGE
        # ============================================================

        self.knowledge = (
            knowledge
            if knowledge is not None
            else KnowledgeManager()
        )

        # ============================================================
        # MEMORY
        # ============================================================

        self.memory = (
            memory
            if memory is not None
            else MemoryManager()
        )

    # ================================================================
    # LIFECYCLE
    # ================================================================

    def initialize(self):
        """
        Initialize Mary's foundational environment.

        Subsystems can later expose their own initialization
        interfaces and be initialized here.
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

    # ================================================================
    # SELF / CHARACTER
    # ================================================================

    def self_profile(self) -> dict:
        """
        Return a unified snapshot of Mary's current self-model.

        This combines identity, personality, character, values,
        canon, relationship, learning, knowledge, and memory
        without merging their meanings.
        """

        return {
            "identity": self.identity.to_dict(),

            "personality": self.personality.to_dict(),

            "character": self.character.to_dict(),

            "values": self.values.to_dict(),

            "canon": self.canon.to_dict(),

            "relationship": self.relationship.to_dict(),

            "learning": self.learning.summarize(),

            "knowledge": self.knowledge,

            "memory": self.memory,
        }

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

            "systems": {
                "personality": self.personality is not None,
                "character": self.character is not None,
                "values": self.values is not None,
                "canon": self.canon is not None,
                "relationship": self.relationship is not None,
                "learning": self.learning is not None,
                "knowledge": self.knowledge is not None,
                "memory": self.memory is not None,
            },
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