"""
MaryV2 Entity System

Entities represent identifiable things Mary encounters.

An entity can eventually be connected to memory, knowledge, relationships,
and reasoning without those systems needing to understand raw input formats.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class EntityType(str, Enum):
    """General categories of entities Mary can recognize."""

    PERSON = "person"
    PLACE = "place"
    OBJECT = "object"
    ORGANIZATION = "organization"
    CONCEPT = "concept"
    EVENT = "event"
    UNKNOWN = "unknown"


@dataclass
class Entity:
    """
    A normalized entity perceived by Mary.
    """

    name: str
    entity_type: EntityType = EntityType.UNKNOWN

    id: str = field(
        default_factory=lambda: str(uuid4())
    )

    description: str | None = None

    attributes: dict[str, Any] = field(
        default_factory=dict
    )

    confidence: float = 1.0

    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the entity into a serializable dictionary."""

        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type.value,
            "description": self.description,
            "attributes": self.attributes,
            "confidence": self.confidence,
            "source": self.source,
        }