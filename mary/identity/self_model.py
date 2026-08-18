"""
MaryV2 Self Model

The Self Model is the central representation of Mary's persistent identity.

It does not generate responses.

It provides a structured description of who Mary is so that
other systems can reason about and communicate with a consistent
representation of her identity.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from mary.personality.personality import Personality
from mary.personality.character import Character
from mary.personality.values import Values
from mary.personality.preferences import Preferences


class SelfModel:
    """
    Mary's persistent self representation.

    Combines:
        - core identity
        - personality
        - character
        - values
        - preferences
        - current self-description

    Memory is intentionally not owned here.
    Memory systems remain independent and can provide relevant
    experiences when the cognitive system requests them.
    """

    def __init__(
        self,
        name: str = "Mary",
        personality: Optional[Personality] = None,
        character: Optional[Character] = None,
        values: Optional[Values] = None,
        preferences: Optional[Preferences] = None,
    ) -> None:

        self.name = (
            str(name).strip()
            or "Mary"
        )

        self.personality = (
            personality
            if personality is not None
            else Personality(
                name=self.name
            )
        )

        self.character = (
            character
            if character is not None
            else Character()
        )

        self.values = (
            values
            if values is not None
            else Values()
        )

        self.preferences = (
            preferences
            if preferences is not None
            else Preferences()
        )

    # ============================================================
    # IDENTITY
    # ============================================================

    def identity(self) -> Dict[str, Any]:
        """
        Return Mary's core identity.
        """

        return {
            "name": self.name,
            "entity_type": "AI character",
        }

    # ============================================================
    # PROFILE
    # ============================================================

    def profile(self) -> Dict[str, Any]:
        """
        Return Mary's complete self profile.
        """

        return {
            "identity": self.identity(),
            "personality": self.personality.behavioral_profile(),
            "values": self.values.get_values(),
            "preferences": self.preferences.to_dict(),
            "character": self.character.profile(),
        }

    # ============================================================
    # DESCRIPTION
    # ============================================================

    def describe(self) -> str:
        """
        Produce a compact description of Mary's current self.
        """

        return (
            f"{self.name} is an AI character with a "
            f"{self.personality.get_style('tone', 'warm')} "
            f"communication style. "
            f"{self.character.describe()}"
        )

    # ============================================================
    # RESET
    # ============================================================

    def reset(self) -> None:
        """
        Reset mutable personality and character state.
        """

        self.personality = Personality(
            name=self.name
        )

        self.character = Character()
        self.values = Values()
        self.preferences = Preferences()
