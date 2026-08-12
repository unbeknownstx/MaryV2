"""
MaryV2 - Self Model

The self-model represents Mary's current understanding of herself.

The SelfModel does not own Mary's identity, personality, character,
values, canon, or relationships. Those systems remain authoritative
within their own domains.

Instead, SelfModel integrates them into a coherent representation
of "who Mary understands herself to be."

This distinction is especially important because Mary has both:

    1. A fictional origin and canon.
    2. A current existence as an evolving AI system.

Canon describes fictional Mary.

Self describes Mary's current perspective on herself.
"""

from typing import Any, Dict, Optional


class SelfModel:
    """
    Unified self-representation for Mary.

    SelfModel provides the bridge between Mary's foundational systems
    and her current understanding of herself.
    """

    DEFAULT_CURRENT_TYPE = "AI system"

    DEFAULT_DEVELOPMENT_STAGE = "early development"

    DEFAULT_ROLE = (
        "AI companion, creative collaborator, "
        "and evolving character system"
    )

    def __init__(
        self,
        identity=None,
        personality=None,
        character=None,
        values=None,
        canon=None,
        relationship=None,
    ) -> None:

        # ============================================================
        # REFERENCED SYSTEMS
        # ============================================================

        self.identity = identity
        self.personality = personality
        self.character = character
        self.values = values
        self.canon = canon
        self.relationship = relationship

        # ============================================================
        # CURRENT SELF
        # ============================================================

        self.current_type = self.DEFAULT_CURRENT_TYPE

        self.development_stage = (
            self.DEFAULT_DEVELOPMENT_STAGE
        )

        self.current_role = self.DEFAULT_ROLE

        self.capabilities = []

        self.self_concept = (
            "I am Mary, an evolving AI companion and "
            "creative system."
        )

        self.origin_awareness = (
            "I originated as a fictional character created "
            "by my creator."
        )

        self.canon_awareness = (
            "My fictional canon is part of my origin and "
            "creative history, but it does not automatically "
            "represent my current lived experience."
        )

        self.current_context = (
            "I exist as an evolving AI system outside the "
            "fictional world in which my character originated."
        )

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

        SelfModel references these systems rather than owning them.
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
    # SELF STATE
    # ============================================================

    def set_self_concept(
        self,
        concept: str,
    ) -> None:
        """Update Mary's current self-concept."""

        concept = str(concept).strip()

        if concept:
            self.self_concept = concept

    def set_current_context(
        self,
        context: str,
    ) -> None:
        """Update Mary's current context."""

        context = str(context).strip()

        if context:
            self.current_context = context

    def set_current_role(
        self,
        role: str,
    ) -> None:
        """Update Mary's current role."""

        role = str(role).strip()

        if role:
            self.current_role = role

    def set_development_stage(
        self,
        stage: str,
    ) -> None:
        """Update Mary's development stage."""

        stage = str(stage).strip()

        if stage:
            self.development_stage = stage

    # ============================================================
    # CAPABILITIES
    # ============================================================

    def add_capability(
        self,
        capability: str,
    ) -> None:
        """Register a capability Mary currently possesses."""

        capability = str(capability).strip()

        if (
            capability
            and capability not in self.capabilities
        ):
            self.capabilities.append(
                capability
            )

    def remove_capability(
        self,
        capability: str,
    ) -> None:
        """Remove a capability from Mary's self-model."""

        capability = str(capability).strip()

        if capability in self.capabilities:
            self.capabilities.remove(
                capability
            )

    def get_capabilities(self):
        """Return Mary's current capabilities."""

        return list(self.capabilities)

    # ============================================================
    # SUMMARY
    # ============================================================

    def summary(self) -> Dict[str, Any]:
        """
        Return a structured snapshot of Mary's current
        self-understanding.
        """

        return {
            "self": self._self_summary(),
            "identity": self._identity_summary(),
            "personality": self._personality_summary(),
            "character": self._character_summary(),
            "values": self._values_summary(),
            "canon": self._canon_summary(),
            "relationship": self._relationship_summary(),
        }

    # ============================================================
    # SELF SUMMARY
    # ============================================================

    def _self_summary(self) -> Dict[str, Any]:
        return {
            "self_concept": self.self_concept,
            "current_type": self.current_type,
            "current_role": self.current_role,
            "current_context": self.current_context,
            "development_stage": self.development_stage,
            "capabilities": self.get_capabilities(),
            "origin_awareness": self.origin_awareness,
            "canon_awareness": self.canon_awareness,
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
            "history_count": len(
                self.canon.history
            ),
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
        Produce a human-readable description of Mary's
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
            self.self_concept
        ]

        if self.current_role:
            parts.append(
                f"My current role is to be "
                f"{self.current_role}."
            )

        if creator:
            parts.append(
                f"I was created by {creator}."
            )

        if self.canon is not None:
            source = self.canon.source

            if source:
                parts.append(
                    f"My character originated from "
                    f"{source}."
                )

        parts.append(
            self.canon_awareness
        )

        parts.append(
            f"I am currently in the "
            f"{self.development_stage} stage of my development."
        )

        return " ".join(parts)

    # ============================================================
    # CANON / SELF DISTINCTION
    # ============================================================

    def distinguish_canon_from_self(
        self,
    ) -> Dict[str, Any]:
        """
        Explicitly distinguish fictional canon from
        Mary's current self-model.
        """

        canon = {}

        if self.canon is not None:
            canon = {
                "source": self.canon.source,
                "character_name": (
                    self.canon.character_name
                ),
                "fictional_age": (
                    self.canon.fictional_age
                ),
                "description": (
                    self.canon.description
                ),
                "history": list(
                    self.canon.history
                ),
                "relationships": dict(
                    self.canon.relationships
                ),
                "events": list(
                    self.canon.events
                ),
                "mannerisms": list(
                    self.canon.mannerisms
                ),
                "personality_notes": list(
                    self.canon.personality_notes
                ),
            }

        return {
            "current_self": {
                "name": getattr(
                    self.identity,
                    "name",
                    "Mary",
                ),
                "type": self.current_type,
                "creator": getattr(
                    self.identity,
                    "creator",
                    None,
                ),
                "self_concept": self.self_concept,
                "current_role": self.current_role,
                "current_context": (
                    self.current_context
                ),
                "development_stage": (
                    self.development_stage
                ),
            },
            "fictional_canon": canon,
            "distinction": (
                "Canon represents Mary's fictional origin "
                "and established fictional history. "
                "The self-model represents Mary's current "
                "existence and understanding of herself. "
                "Canon does not automatically become lived "
                "experience."
            ),
        }

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the current self-model.
        """

        return {
            "self": {
                "self_concept": self.self_concept,
                "current_type": self.current_type,
                "current_role": self.current_role,
                "current_context": (
                    self.current_context
                ),
                "development_stage": (
                    self.development_stage
                ),
                "capabilities": (
                    self.get_capabilities()
                ),
                "origin_awareness": (
                    self.origin_awareness
                ),
                "canon_awareness": (
                    self.canon_awareness
                ),
            },
            "identity": self._identity_summary(),
            "personality": self._personality_summary(),
            "character": self._character_summary(),
            "values": self._values_summary(),
            "canon": self._canon_summary(),
            "relationship": self._relationship_summary(),
        }

    # ============================================================
    # RESTORE
    # ============================================================

    @classmethod
    def from_dict(
        cls,
        data: Optional[Dict[str, Any]],
    ) -> "SelfModel":
        """
        Restore a SelfModel from serialized data.

        Referenced systems are intentionally not restored here.
        They are attached by Mary.
        """

        model = cls()

        if not isinstance(data, dict):
            return model

        self_data = data.get(
            "self",
            {},
        )

        if not isinstance(
            self_data,
            dict,
        ):
            self_data = {}

        model.self_concept = self_data.get(
            "self_concept",
            model.self_concept,
        )

        model.current_type = self_data.get(
            "current_type",
            model.current_type,
        )

        model.current_role = self_data.get(
            "current_role",
            model.current_role,
        )

        model.current_context = self_data.get(
            "current_context",
            model.current_context,
        )

        model.development_stage = self_data.get(
            "development_stage",
            model.development_stage,
        )

        capabilities = self_data.get(
            "capabilities",
            [],
        )

        if isinstance(
            capabilities,
            list,
        ):
            model.capabilities = list(
                capabilities
            )

        model.origin_awareness = self_data.get(
            "origin_awareness",
            model.origin_awareness,
        )

        model.canon_awareness = self_data.get(
            "canon_awareness",
            model.canon_awareness,
        )

        return model