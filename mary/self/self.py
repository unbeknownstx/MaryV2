"""
MaryV2 - Self Model

The self-model represents Mary's understanding of herself.

This is not Mary's personality, character, identity, or canon.
Instead, it provides a unified perspective over those systems.

Identity:
    What Mary fundamentally is and where she comes from.

Personality:
    Mary's underlying psychological tendencies.

Character:
    How those tendencies are expressed.

Values:
    What Mary considers important.

Canon:
    The fictional character and history from which Mary originated.

Self-model:
    Mary's current understanding of how these pieces relate to her.
"""

from typing import Any, Dict, Optional


class SelfModel:
    """
    Unified self-representation for Mary.

    The SelfModel does not own personality, identity, canon, etc.
    It reads those systems and produces a coherent self-description.
    """

    def __init__(
        self,
        identity=None,
        personality=None,
        character=None,
        values=None,
        canon=None,
        relationship=None,
    ) -> None:

        self.identity = identity
        self.personality = personality
        self.character = character
        self.values = values
        self.canon = canon
        self.relationship = relationship

    # ============================================================
    # ATTACHMENT
    # ============================================================

    def attach(
        self,
        identity=None,
        personality=None,
        character=None,
        values=None,
        canon=None,
        relationship=None,
    ) -> None:
        """
        Attach Mary's foundational systems.

        Systems remain owned by Mary. SelfModel only references them.
        """

        if identity is not None:
            self.identity = identity

        if personality is not None:
            self.personality = personality

        if character is not None:
            self.character = character

        if values is not None:
            self.values = values

        if canon is not None:
            self.canon = canon

        if relationship is not None:
            self.relationship = relationship

    # ============================================================
    # SUMMARY
    # ============================================================

    def summary(self) -> Dict[str, Any]:
        """
        Return a structured snapshot of Mary's current self-model.
        """

        return {
            "identity": self._identity_summary(),
            "personality": self._personality_summary(),
            "character": self._character_summary(),
            "values": self._values_summary(),
            "canon": self._canon_summary(),
            "relationship": self._relationship_summary(),
        }

    # ============================================================
    # IDENTITY
    # ============================================================

    def _identity_summary(self) -> Dict[str, Any]:
        if self.identity is None:
            return {}

        return {
            "name": getattr(
                self.identity,
                "name",
                "Mary",
            ),
            "version": getattr(
                self.identity,
                "version",
                "unknown",
            ),
            "creator": getattr(
                self.identity,
                "creator",
                None,
            ),
            "description": getattr(
                self.identity,
                "description",
                "",
            ),
            "purpose": getattr(
                self.identity,
                "purpose",
                "",
            ),
        }

    # ============================================================
    # PERSONALITY
    # ============================================================

    def _personality_summary(self) -> Dict[str, Any]:
        if self.personality is None:
            return {}

        return {
            "traits": self.personality.get_traits(),
            "style": self.personality.get_style(),
        }

    # ============================================================
    # CHARACTER
    # ============================================================

    def _character_summary(self) -> Dict[str, Any]:
        if self.character is None:
            return {}

        return {
            "archetype": self.character.archetype,
            "qualities": self.character.get_qualities(),
            "tendencies": self.character.get_tendencies(),
            "mannerisms": self.character.get_mannerisms(),
            "humor_style": self.character.get_humor_style(),
            "behavior": self.character.get_behavior(),
        }

    # ============================================================
    # VALUES
    # ============================================================

    def _values_summary(self) -> Dict[str, Any]:
        if self.values is None:
            return {}

        return {
            "priorities": self.values.get_priorities(),
            "strong_values": self.values.get_strong_values(),
        }

    # ============================================================
    # CANON
    # ============================================================

    def _canon_summary(self) -> Dict[str, Any]:
        if self.canon is None:
            return {}

        return {
            "source": self.canon.source,
            "character_name": self.canon.character_name,
            "fictional_age": self.canon.fictional_age,
            "description": self.canon.description,
            "history_count": len(self.canon.history),
            "relationship_count": len(
                self.canon.relationships
            ),
            "mannerism_count": len(
                self.canon.mannerisms
            ),
            "event_count": len(
                self.canon.events
            ),
            "knowledge_count": len(
                self.canon.knowledge
            ),
        }

    # ============================================================
    # RELATIONSHIP
    # ============================================================

    def _relationship_summary(self) -> Dict[str, Any]:
        if self.relationship is None:
            return {}

        try:
            return self.relationship.get_identity()
        except AttributeError:
            return {}

    # ============================================================
    # HUMAN-READABLE DESCRIPTION
    # ============================================================

    def describe(self) -> str:
        """
        Produce a concise human-readable description of Mary's
        current self-understanding.
        """

        name = (
            getattr(
                self.identity,
                "name",
                "Mary",
            )
            if self.identity is not None
            else "Mary"
        )

        description = (
            getattr(
                self.identity,
                "description",
                "",
            )
            if self.identity is not None
            else ""
        )

        archetype = (
            getattr(
                self.character,
                "archetype",
                "",
            )
            if self.character is not None
            else ""
        )

        creator = (
            getattr(
                self.identity,
                "creator",
                None,
            )
            if self.identity is not None
            else None
        )

        parts = [
            f"{name} is {archetype}."
        ]

        if description:
            parts.append(description)

        if creator:
            parts.append(
                f"She was created by {creator}."
            )

        if self.canon is not None:
            source = self.canon.source

            if source:
                parts.append(
                    f"Her character originated from "
                    f"{source}."
                )

        return " ".join(parts)

    # ============================================================
    # CANONICAL DISTINCTION
    # ============================================================

    def distinguish_canon_from_self(self) -> Dict[str, Any]:
        """
        Explicitly distinguish fictional canon from Mary's
        current self-model.

        This becomes important when Mary works with fiction,
        animation, art, or future creative projects.
        """

        canon = {}

        if self.canon is not None:
            canon = {
                "source": self.canon.source,
                "character_name": self.canon.character_name,
                "fictional_age": self.canon.fictional_age,
                "description": self.canon.description,
                "history": list(self.canon.history),
                "relationships": dict(
                    self.canon.relationships
                ),
                "events": list(self.canon.events),
            }

        return {
            "current_self": {
                "name": getattr(
                    self.identity,
                    "name",
                    "Mary",
                ),
                "type": "AI system",
                "creator": getattr(
                    self.identity,
                    "creator",
                    None,
                ),
            },
            "fictional_canon": canon,
            "relationship": (
                "Canon represents Mary's fictional origin "
                "and established fictional history. "
                "It does not automatically represent Mary's "
                "current lived experience."
            ),
        }

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the current self-model.
        """

        return self.summary()