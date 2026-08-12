"""
MaryV2 - Mary Core

Central coordinator for Mary's foundational systems.

Mary owns and coordinates the major subsystems.

The individual systems remain responsible for their own data:

    Identity
    Personality
    Character
    Values
    Preferences
    Canon
    Relationship/User Model
    SelfModel
    PersonalityDevelopment
"""

from typing import Any, Dict


# ============================================================
# CORE
# ============================================================

from mary.core.identity import Identity


# ============================================================
# CHARACTER / CANON
# ============================================================

from mary.character.canon import Canon


# ============================================================
# PERSONALITY
# ============================================================

from mary.personality.personality import Personality
from mary.personality.character import Character
from mary.personality.values import Values
from mary.personality.preferences import Preferences
from mary.personality.development import PersonalityDevelopment


# ============================================================
# RELATIONSHIP
# ============================================================

from mary.relationship.user import UserModel


# ============================================================
# SELF
# ============================================================

from mary.self.self import SelfModel


class Mary:
    """
    Central representation of Mary.

    Mary coordinates the systems that make up her
    current identity and developing self-model.
    """

    VERSION = "2.0.0"

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(self) -> None:

        # ----------------------------------------------------
        # Identity
        # ----------------------------------------------------

        self.identity = Identity()

        # ----------------------------------------------------
        # Personality
        # ----------------------------------------------------

        self.personality = Personality()

        # ----------------------------------------------------
        # Character
        # ----------------------------------------------------

        self.character = Character()

        # ----------------------------------------------------
        # Values
        # ----------------------------------------------------

        self.values = Values()

        # ----------------------------------------------------
        # Preferences
        # ----------------------------------------------------

        self.preferences = Preferences()

        # ----------------------------------------------------
        # Fictional Canon
        # ----------------------------------------------------

        self.canon = Canon()

        # ----------------------------------------------------
        # Creator / Relationship Model
        # ----------------------------------------------------

        self.relationship = UserModel()

        # ----------------------------------------------------
        # Unified Self Model
        # ----------------------------------------------------

        self.self_model = SelfModel(
            identity=self.identity,
            personality=self.personality,
            character=self.character,
            values=self.values,
            canon=self.canon,
            relationship=self.relationship,
        )

        # ----------------------------------------------------
        # Personality Development
        # ----------------------------------------------------

        self.personality_development = (
            PersonalityDevelopment(
                personality=self.personality,
                values=self.values,
                preferences=self.preferences,
            )
        )

        # ----------------------------------------------------
        # Runtime State
        # ----------------------------------------------------

        self.state = "created"
        self.running = False

    # ========================================================
    # SELF
    # ========================================================

    def self_profile(self) -> Dict[str, Any]:
        """
        Return Mary's unified self-profile.
        """

        profile = self.self_model.to_dict()

        profile["development"] = (
            self.personality_development.summary()
        )

        return profile

    def describe_self(self) -> str:
        """
        Return a human-readable description of Mary.
        """

        return self.self_model.describe()

    def canon_vs_self(self) -> Dict[str, Any]:
        """
        Distinguish Mary's current self from her fictional
        canonical origin.
        """

        return self.self_model.distinguish_canon_from_self()

    # ========================================================
    # PERSONALITY DEVELOPMENT
    # ========================================================

    def personality_development_summary(
        self,
    ) -> Dict[str, Any]:
        """
        Return the current personality-development summary.
        """

        return self.personality_development.summary()

    def propose_personality_change(
        self,
        trait: str,
        change: float,
        reason: str,
        confidence: float = 0.5,
        source: str = "experience",
    ) -> Dict[str, Any]:
        """
        Create a personality-development proposal.

        Creating a proposal does not immediately change
        Mary's personality.
        """

        return self.personality_development.propose_change(
            trait=trait,
            change=change,
            reason=reason,
            confidence=confidence,
            source=source,
        )

    def apply_personality_change(
        self,
        proposal: Dict[str, Any],
    ) -> bool:
        """
        Apply a personality-development proposal.
        """

        return self.personality_development.apply(
            proposal
        )

    def reject_personality_change(
        self,
        proposal: Dict[str, Any],
        reason: str = "",
    ) -> bool:
        """
        Reject a personality-development proposal.
        """

        return self.personality_development.reject(
            proposal,
            reason=reason,
        )

    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> Dict[str, Any]:
        """
        Return Mary's current runtime status.
        """

        return {
            "name": getattr(
                self.identity,
                "name",
                "Mary",
            ),
            "version": self.VERSION,
            "creator": getattr(
                self.identity,
                "creator",
                None,
            ),
            "state": self.state,
            "running": self.running,
        }

    # ========================================================
    # LIFECYCLE
    # ========================================================

    def start(self) -> None:
        """
        Start Mary.
        """

        self.running = True
        self.state = "running"

    def stop(self) -> None:
        """
        Stop Mary.
        """

        self.running = False
        self.state = "stopped"

    # ========================================================
    # SERIALIZATION
    # ========================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize Mary's current foundational state.
        """

        return {
            "status": self.status(),
            "self": self.self_profile(),
            "personality_development": (
                self.personality_development.to_dict()
            ),
        }