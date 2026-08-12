"""
MaryV2 - Knowledge Concepts

Defines the core data structures used by Mary's long-term
knowledge system.

A Concept represents a piece of knowledge that Mary can:

    - remember
    - retrieve
    - update
    - relate to other concepts
    - evaluate
    - track by confidence
    - trace back to its source

This module intentionally contains no:

    - file I/O
    - database code
    - web requests
    - LLM calls

Those responsibilities belong to other layers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


# ================================================================
# KNOWLEDGE TYPES
# ================================================================


KNOWLEDGE_TYPES = {
    "fact",
    "concept",
    "rule",
    "procedure",
    "definition",
    "observation",
    "hypothesis",
    "preference",
    "relationship",
    "lesson",
}


KNOWLEDGE_STATUSES = {
    "candidate",
    "trusted",
    "uncertain",
    "disputed",
    "deprecated",
}


# ================================================================
# SOURCE REFERENCE
# ================================================================


@dataclass
class SourceReference:
    """
    Identifies where a piece of knowledge came from.

    The complete source model will live in sources.py.

    This lightweight reference allows concepts to remain
    independent from the source implementation.
    """

    source_id: str

    source_type: str = "unknown"

    title: str = ""

    location: str = ""

    accessed_at: str = ""

    reliability: float = 0.5

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.reliability = _clamp(
            self.reliability
        )

        if not self.accessed_at:
            self.accessed_at = _timestamp()


# ================================================================
# RELATIONSHIP
# ================================================================


@dataclass
class ConceptRelation:
    """
    Represents a relationship between two concepts.

    Examples:

        Mary -> knows -> Python
        Python -> used_for -> programming
        creator -> built -> Mary

    Relations are intentionally generic so the knowledge graph
    can grow without requiring a fixed ontology.
    """

    relation: str

    target_id: str

    confidence: float = 0.5

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    created_at: str = ""

    def __post_init__(self) -> None:
        self.confidence = _clamp(
            self.confidence
        )

        if not self.created_at:
            self.created_at = _timestamp()


# ================================================================
# EVIDENCE
# ================================================================


@dataclass
class Evidence:
    """
    Evidence supporting or contradicting a concept.

    Evidence allows Mary to distinguish between:

        "I know this."

    and:

        "I believe this because these sources support it."
    """

    statement: str

    supports: bool = True

    confidence: float = 0.5

    source_id: str | None = None

    created_at: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.confidence = _clamp(
            self.confidence
        )

        if not self.created_at:
            self.created_at = _timestamp()


# ================================================================
# CONCEPT
# ================================================================


@dataclass
class Concept:
    """
    A persistent unit of knowledge.

    A Concept can represent a fact, idea, procedure, definition,
    observation, hypothesis, relationship, or lesson.
    """

    id: str

    name: str

    statement: str

    knowledge_type: str = "concept"

    status: str = "candidate"

    confidence: float = 0.5

    importance: float = 0.5

    first_learned: str = ""

    last_updated: str = ""

    last_confirmed: str | None = None

    source_ids: list[str] = field(
        default_factory=list
    )

    evidence: list[Evidence] = field(
        default_factory=list
    )

    relations: list[ConceptRelation] = field(
        default_factory=list
    )

    tags: list[str] = field(
        default_factory=list
    )

    aliases: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.confidence = _clamp(
            self.confidence
        )

        self.importance = _clamp(
            self.importance
        )

        if self.knowledge_type not in KNOWLEDGE_TYPES:
            self.knowledge_type = "concept"

        if self.status not in KNOWLEDGE_STATUSES:
            self.status = "candidate"

        now = _timestamp()

        if not self.first_learned:
            self.first_learned = now

        if not self.last_updated:
            self.last_updated = now

    # ============================================================
    # CONFIDENCE
    # ============================================================

    def update_confidence(
        self,
        confidence: float,
    ) -> None:
        """
        Update the concept's confidence.
        """

        self.confidence = _clamp(
            confidence
        )

        self.last_updated = _timestamp()

    def increase_confidence(
        self,
        amount: float = 0.05,
    ) -> None:
        """
        Increase confidence while keeping it bounded.
        """

        self.update_confidence(
            self.confidence + amount
        )

    def decrease_confidence(
        self,
        amount: float = 0.05,
    ) -> None:
        """
        Decrease confidence while keeping it bounded.
        """

        self.update_confidence(
            self.confidence - amount
        )

    # ============================================================
    # STATUS
    # ============================================================

    def trust(
        self,
        confidence: float | None = None,
    ) -> None:
        """
        Mark the concept as trusted.
        """

        if confidence is not None:
            self.confidence = _clamp(
                confidence
            )

        self.status = "trusted"

        self.last_confirmed = _timestamp()

        self.last_updated = _timestamp()

    def mark_uncertain(
        self,
    ) -> None:
        """
        Mark the concept as uncertain.
        """

        self.status = "uncertain"

        self.last_updated = _timestamp()

    def dispute(
        self,
    ) -> None:
        """
        Mark the concept as disputed.
        """

        self.status = "disputed"

        self.last_updated = _timestamp()

    def deprecate(
        self,
    ) -> None:
        """
        Mark the concept as no longer trusted or current.
        """

        self.status = "deprecated"

        self.last_updated = _timestamp()

    # ============================================================
    # SOURCES
    # ============================================================

    def add_source(
        self,
        source_id: str,
    ) -> None:
        """
        Associate a source with this concept.
        """

        source_id = str(
            source_id
        ).strip()

        if not source_id:
            return

        if source_id not in self.source_ids:
            self.source_ids.append(
                source_id
            )

        self.last_updated = _timestamp()

    def remove_source(
        self,
        source_id: str,
    ) -> None:
        """
        Remove a source association.
        """

        if source_id in self.source_ids:
            self.source_ids.remove(
                source_id
            )

            self.last_updated = _timestamp()

    # ============================================================
    # EVIDENCE
    # ============================================================

    def add_evidence(
        self,
        statement: str,
        *,
        supports: bool = True,
        confidence: float = 0.5,
        source_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Evidence:
        """
        Add supporting or contradictory evidence.
        """

        evidence = Evidence(
            statement=str(
                statement
            ).strip(),
            supports=supports,
            confidence=confidence,
            source_id=source_id,
            metadata=metadata or {},
        )

        self.evidence.append(
            evidence
        )

        if source_id:
            self.add_source(
                source_id
            )

        self.last_updated = _timestamp()

        return evidence

    def supporting_evidence(
        self,
    ) -> list[Evidence]:
        """
        Return evidence supporting the concept.
        """

        return [
            item
            for item in self.evidence
            if item.supports
        ]

    def contradicting_evidence(
        self,
    ) -> list[Evidence]:
        """
        Return evidence contradicting the concept.
        """

        return [
            item
            for item in self.evidence
            if not item.supports
        ]

    # ============================================================
    # RELATIONS
    # ============================================================

    def add_relation(
        self,
        relation: str,
        target_id: str,
        *,
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> ConceptRelation:
        """
        Add a relationship to another concept.
        """

        concept_relation = ConceptRelation(
            relation=str(
                relation
            ).strip(),
            target_id=str(
                target_id
            ).strip(),
            confidence=confidence,
            metadata=metadata or {},
        )

        self.relations.append(
            concept_relation
        )

        self.last_updated = _timestamp()

        return concept_relation

    def remove_relation(
        self,
        target_id: str,
        relation: str | None = None,
    ) -> int:
        """
        Remove matching relations.

        Returns the number of removed relations.
        """

        original_count = len(
            self.relations
        )

        self.relations = [
            item
            for item in self.relations
            if not (
                item.target_id == target_id
                and (
                    relation is None
                    or item.relation == relation
                )
            )
        ]

        removed = (
            original_count
            - len(self.relations)
        )

        if removed:
            self.last_updated = _timestamp()

        return removed

    # ============================================================
    # TAGS
    # ============================================================

    def add_tag(
        self,
        tag: str,
    ) -> None:
        """
        Add a normalized tag.
        """

        tag = str(
            tag
        ).strip().lower()

        if not tag:
            return

        if tag not in self.tags:
            self.tags.append(
                tag
            )

        self.last_updated = _timestamp()

    def remove_tag(
        self,
        tag: str,
    ) -> None:
        """
        Remove a tag.
        """

        tag = str(
            tag
        ).strip().lower()

        if tag in self.tags:
            self.tags.remove(
                tag
            )

            self.last_updated = _timestamp()

    # ============================================================
    # ALIASES
    # ============================================================

    def add_alias(
        self,
        alias: str,
    ) -> None:
        """
        Add an alternate name for the concept.
        """

        alias = str(
            alias
        ).strip()

        if not alias:
            return

        if alias.lower() == self.name.lower():
            return

        if alias not in self.aliases:
            self.aliases.append(
                alias
            )

        self.last_updated = _timestamp()

    # ============================================================
    # MATCHING
    # ============================================================

    def matches(
        self,
        query: str,
    ) -> bool:
        """
        Perform a basic lexical match.

        Semantic retrieval belongs to retrieval.py / manager.py.
        """

        query_words = _words(
            query
        )

        if not query_words:
            return False

        searchable = _words(
            " ".join(
                [
                    self.name,
                    self.statement,
                    *self.aliases,
                    *self.tags,
                ]
            )
        )

        return bool(
            query_words
            & searchable
        )

    # ============================================================
    # SUMMARY
    # ============================================================

    def summary(
        self,
    ) -> dict[str, Any]:
        """
        Return a compact representation suitable for retrieval or
        prompting.
        """

        return {
            "id": self.id,
            "name": self.name,
            "statement": self.statement,
            "type": self.knowledge_type,
            "status": self.status,
            "confidence": self.confidence,
            "importance": self.importance,
            "tags": list(self.tags),
            "aliases": list(self.aliases),
            "sources": list(self.source_ids),
        }

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize the concept into a dictionary.
        """

        return asdict(
            self
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "Concept":
        """
        Construct a Concept from serialized data.
        """

        evidence_data = data.get(
            "evidence",
            [],
        )

        relation_data = data.get(
            "relations",
            [],
        )

        evidence = [
            Evidence(
                statement=str(
                    item.get(
                        "statement",
                        "",
                    )
                ),
                supports=bool(
                    item.get(
                        "supports",
                        True,
                    )
                ),
                confidence=_clamp(
                    item.get(
                        "confidence",
                        0.5,
                    )
                ),
                source_id=item.get(
                    "source_id"
                ),
                created_at=str(
                    item.get(
                        "created_at",
                        _timestamp(),
                    )
                ),
                metadata=dict(
                    item.get(
                        "metadata",
                        {},
                    )
                ),
            )
            for item in evidence_data
            if isinstance(
                item,
                dict,
            )
        ]

        relations = [
            ConceptRelation(
                relation=str(
                    item.get(
                        "relation",
                        "",
                    )
                ),
                target_id=str(
                    item.get(
                        "target_id",
                        "",
                    )
                ),
                confidence=_clamp(
                    item.get(
                        "confidence",
                        0.5,
                    )
                ),
                metadata=dict(
                    item.get(
                        "metadata",
                        {},
                    )
                ),
                created_at=str(
                    item.get(
                        "created_at",
                        _timestamp(),
                    )
                ),
            )
            for item in relation_data
            if isinstance(
                item,
                dict,
            )
        ]

        return cls(
            id=str(
                data.get(
                    "id",
                    "",
                )
            ),
            name=str(
                data.get(
                    "name",
                    "",
                )
            ),
            statement=str(
                data.get(
                    "statement",
                    "",
                )
            ),
            knowledge_type=str(
                data.get(
                    "knowledge_type",
                    "concept",
                )
            ),
            status=str(
                data.get(
                    "status",
                    "candidate",
                )
            ),
            confidence=_clamp(
                data.get(
                    "confidence",
                    0.5,
                )
            ),
            importance=_clamp(
                data.get(
                    "importance",
                    0.5,
                )
            ),
            first_learned=str(
                data.get(
                    "first_learned",
                    _timestamp(),
                )
            ),
            last_updated=str(
                data.get(
                    "last_updated",
                    _timestamp(),
                )
            ),
            last_confirmed=data.get(
                "last_confirmed"
            ),
            source_ids=list(
                data.get(
                    "source_ids",
                    [],
                )
            ),
            evidence=evidence,
            relations=relations,
            tags=list(
                data.get(
                    "tags",
                    [],
                )
            ),
            aliases=list(
                data.get(
                    "aliases",
                    [],
                )
            ),
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )


# ================================================================
# HELPERS
# ================================================================


def _clamp(
    value: float,
) -> float:
    """
    Keep a value between 0.0 and 1.0.
    """

    try:
        value = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.5

    return max(
        0.0,
        min(
            1.0,
            value,
        ),
    )


def _words(
    text: str,
) -> set[str]:
    """
    Normalize text into a set of words.
    """

    punctuation = (
        ".,!?;:\"'()[]{}"
    )

    return {
        word.strip(
            punctuation
        ).lower()
        for word in str(
            text
        ).split()
        if word.strip(
            punctuation
        )
    }


def _timestamp() -> str:
    """
    Return a timezone-aware UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()