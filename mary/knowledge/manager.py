"""
MaryV2 - Knowledge Manager

Central coordinator for Mary's persistent knowledge.

Responsibilities:

    - create and manage concepts
    - register knowledge sources
    - connect concepts to sources
    - search concepts
    - track evidence
    - track relationships
    - update confidence
    - detect basic contradictions
    - serialize and restore knowledge

This module intentionally does NOT:

    - perform web searches
    - call an LLM
    - decide what Mary should believe
    - directly access databases
    - perform autonomous actions

Those responsibilities belong to other layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .concepts import (
    Concept,
    Evidence,
)
from .sources import (
    Source,
    SourceManager,
)


# ================================================================
# RESULT TYPES
# ================================================================


@dataclass
class KnowledgeSearchResult:
    """
    Result returned from a knowledge search.

    score:
        Basic lexical relevance score.

    concept:
        The matched knowledge concept.
    """

    concept: Concept

    score: float

    matched_terms: list[str] = field(
        default_factory=list
    )


@dataclass
class KnowledgeStats:
    """
    Summary statistics for Mary's knowledge base.
    """

    concepts: int = 0

    sources: int = 0

    trusted_concepts: int = 0

    uncertain_concepts: int = 0

    disputed_concepts: int = 0

    candidate_concepts: int = 0

    deprecated_concepts: int = 0

    average_confidence: float = 0.0

    trusted_sources: int = 0


# ================================================================
# KNOWLEDGE MANAGER
# ================================================================


class KnowledgeManager:
    """
    Central registry for Mary's long-term knowledge.

    The manager provides the stable interface that other Mary
    subsystems can use without needing to know how knowledge is
    internally represented.
    """

    def __init__(
        self,
        source_manager: SourceManager | None = None,
    ) -> None:
        self.concepts: dict[
            str,
            Concept,
        ] = {}

        self.sources = (
            source_manager
            if source_manager is not None
            else SourceManager()
        )

    # ============================================================
    # CONCEPT CREATION
    # ============================================================

    def create_concept(
        self,
        name: str,
        statement: str,
        *,
        concept_id: str | None = None,
        knowledge_type: str = "concept",
        status: str = "candidate",
        confidence: float = 0.5,
        importance: float = 0.5,
        source_ids: list[str] | None = None,
        tags: list[str] | None = None,
        aliases: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Concept:
        """
        Create and register a knowledge concept.
        """

        concept = Concept(
            id=(
                concept_id
                if concept_id
                else self._next_concept_id()
            ),
            name=str(
                name
            ).strip(),
            statement=str(
                statement
            ).strip(),
            knowledge_type=knowledge_type,
            status=status,
            confidence=confidence,
            importance=importance,
            source_ids=list(
                source_ids or []
            ),
            tags=[
                str(tag).strip().lower()
                for tag in (
                    tags or []
                )
                if str(tag).strip()
            ],
            aliases=[
                str(alias).strip()
                for alias in (
                    aliases or []
                )
                if str(alias).strip()
            ],
            metadata=metadata or {},
        )

        self.concepts[
            concept.id
        ] = concept

        return concept

    # ============================================================
    # CONCEPT ACCESS
    # ============================================================

    def get_concept(
        self,
        concept_id: str,
    ) -> Concept | None:
        """
        Retrieve a concept by ID.
        """

        return self.concepts.get(
            concept_id
        )

    def get_all_concepts(
        self,
    ) -> list[Concept]:
        """
        Return all concepts.
        """

        return list(
            self.concepts.values()
        )

    def remove_concept(
        self,
        concept_id: str,
    ) -> bool:
        """
        Remove a concept from the registry.
        """

        if concept_id not in self.concepts:
            return False

        del self.concepts[
            concept_id
        ]

        return True

    # ============================================================
    # SOURCES
    # ============================================================

    def create_source(
        self,
        title: str,
        *,
        source_type: str = "unknown",
        location: str = "",
        author: str = "",
        publisher: str = "",
        description: str = "",
        reliability: float | None = None,
        status: str = "unverified",
        published_at: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Source:
        """
        Create a source through the source manager.
        """

        return self.sources.create(
            title,
            source_type=source_type,
            location=location,
            author=author,
            publisher=publisher,
            description=description,
            reliability=reliability,
            status=status,
            published_at=published_at,
            tags=tags,
            metadata=metadata,
        )

    def get_source(
        self,
        source_id: str,
    ) -> Source | None:
        """
        Retrieve a source.
        """

        return self.sources.get(
            source_id
        )

    # ============================================================
    # KNOWLEDGE INGESTION
    # ============================================================

    def learn(
        self,
        name: str,
        statement: str,
        *,
        source: Source | str | None = None,
        knowledge_type: str = "concept",
        confidence: float = 0.5,
        importance: float = 0.5,
        tags: list[str] | None = None,
        aliases: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Concept:
        """
        Register a new piece of knowledge.

        If an existing concept has the same name and statement,
        the existing concept is updated instead of duplicated.
        """

        existing = self.find_exact(
            name=name,
            statement=statement,
        )

        if existing is not None:
            self._update_existing_knowledge(
                existing,
                source=source,
                confidence=confidence,
            )

            return existing

        source_id = (
            self._resolve_source_id(
                source
            )
        )

        concept = self.create_concept(
            name=name,
            statement=statement,
            knowledge_type=knowledge_type,
            confidence=confidence,
            importance=importance,
            source_ids=(
                [source_id]
                if source_id
                else []
            ),
            tags=tags,
            aliases=aliases,
            metadata=metadata,
        )

        return concept

    # ============================================================
    # FINDING KNOWLEDGE
    # ============================================================

    def find_exact(
        self,
        *,
        name: str,
        statement: str,
    ) -> Concept | None:
        """
        Find a concept with matching name and statement.
        """

        normalized_name = _normalize(
            name
        )

        normalized_statement = _normalize(
            statement
        )

        for concept in self.concepts.values():
            if (
                _normalize(
                    concept.name
                )
                == normalized_name
                and _normalize(
                    concept.statement
                )
                == normalized_statement
            ):
                return concept

        return None

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        include_deprecated: bool = False,
    ) -> list[KnowledgeSearchResult]:
        """
        Perform basic lexical knowledge retrieval.

        Semantic/vector retrieval can be added later without
        changing the public interface.
        """

        query_words = _words(
            query
        )

        if not query_words:
            return []

        results: list[
            KnowledgeSearchResult
        ] = []

        for concept in self.concepts.values():
            if (
                concept.status == "deprecated"
                and not include_deprecated
            ):
                continue

            searchable = _words(
                " ".join(
                    [
                        concept.name,
                        concept.statement,
                        *concept.aliases,
                        *concept.tags,
                    ]
                )
            )

            matched = (
                query_words
                & searchable
            )

            if not matched:
                continue

            score = self._calculate_score(
                concept,
                query_words,
                matched,
            )

            results.append(
                KnowledgeSearchResult(
                    concept=concept,
                    score=score,
                    matched_terms=sorted(
                        matched
                    ),
                )
            )

        results.sort(
            key=lambda result: result.score,
            reverse=True,
        )

        return results[
            :max(1, limit)
        ]

    # ============================================================
    # CONFIDENCE
    # ============================================================

    def update_confidence(
        self,
        concept_id: str,
        confidence: float,
    ) -> bool:
        """
        Update concept confidence.
        """

        concept = self.get_concept(
            concept_id
        )

        if concept is None:
            return False

        concept.update_confidence(
            confidence
        )

        return True

    def reinforce(
        self,
        concept_id: str,
        amount: float = 0.05,
    ) -> bool:
        """
        Increase confidence in a concept.
        """

        concept = self.get_concept(
            concept_id
        )

        if concept is None:
            return False

        concept.increase_confidence(
            amount
        )

        return True

    def weaken(
        self,
        concept_id: str,
        amount: float = 0.05,
    ) -> bool:
        """
        Decrease confidence in a concept.
        """

        concept = self.get_concept(
            concept_id
        )

        if concept is None:
            return False

        concept.decrease_confidence(
            amount
        )

        return True

    # ============================================================
    # TRUST
    # ============================================================

    def trust(
        self,
        concept_id: str,
        *,
        confidence: float | None = None,
    ) -> bool:
        """
        Mark a concept as trusted.
        """

        concept = self.get_concept(
            concept_id
        )

        if concept is None:
            return False

        concept.trust(
            confidence
        )

        return True

    def mark_uncertain(
        self,
        concept_id: str,
    ) -> bool:
        """
        Mark a concept as uncertain.
        """

        concept = self.get_concept(
            concept_id
        )

        if concept is None:
            return False

        concept.mark_uncertain()

        return True

    def dispute(
        self,
        concept_id: str,
    ) -> bool:
        """
        Mark a concept as disputed.
        """

        concept = self.get_concept(
            concept_id
        )

        if concept is None:
            return False

        concept.dispute()

        return True

    # ============================================================
    # EVIDENCE
    # ============================================================

    def add_evidence(
        self,
        concept_id: str,
        statement: str,
        *,
        supports: bool = True,
        confidence: float = 0.5,
        source: Source | str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Evidence | None:
        """
        Add evidence to an existing concept.
        """

        concept = self.get_concept(
            concept_id
        )

        if concept is None:
            return None

        source_id = (
            self._resolve_source_id(
                source
            )
        )

        evidence = concept.add_evidence(
            statement=statement,
            supports=supports,
            confidence=confidence,
            source_id=source_id,
            metadata=metadata,
        )

        if source_id:
            if supports:
                self.sources.verify(
                    source_id
                )
            else:
                self.sources.record_contradiction(
                    source_id
                )

        self._recalculate_concept_confidence(
            concept
        )

        return evidence

    # ============================================================
    # RELATIONSHIPS
    # ============================================================

    def relate(
        self,
        concept_id: str,
        relation: str,
        target_id: str,
        *,
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Create a relationship between two concepts.
        """

        concept = self.get_concept(
            concept_id
        )

        target = self.get_concept(
            target_id
        )

        if (
            concept is None
            or target is None
        ):
            return False

        concept.add_relation(
            relation=relation,
            target_id=target_id,
            confidence=confidence,
            metadata=metadata,
        )

        return True

    def related(
        self,
        concept_id: str,
        *,
        relation: str | None = None,
    ) -> list[Concept]:
        """
        Return concepts related to a given concept.
        """

        concept = self.get_concept(
            concept_id
        )

        if concept is None:
            return []

        results: list[
            Concept
        ] = []

        for item in concept.relations:
            if (
                relation is not None
                and item.relation
                != relation
            ):
                continue

            target = self.get_concept(
                item.target_id
            )

            if target is not None:
                results.append(
                    target
                )

        return results

    # ============================================================
    # SOURCE ASSOCIATION
    # ============================================================

    def attach_source(
        self,
        concept_id: str,
        source: Source | str,
    ) -> bool:
        """
        Attach a source to an existing concept.
        """

        concept = self.get_concept(
            concept_id
        )

        if concept is None:
            return False

        source_id = (
            self._resolve_source_id(
                source
            )
        )

        if source_id is None:
            return False

        concept.add_source(
            source_id
        )

        return True

    # ============================================================
    # SOURCE EVALUATION
    # ============================================================

    def evaluate_sources(
        self,
        concept_id: str,
    ) -> float:
        """
        Calculate a basic source-weighted confidence estimate.

        This does NOT replace learning/evaluator.py.

        It provides the knowledge layer with a simple provenance
        signal.
        """

        concept = self.get_concept(
            concept_id
        )

        if concept is None:
            return 0.0

        reliabilities: list[
            float
        ] = []

        for source_id in concept.source_ids:
            source = self.get_source(
                source_id
            )

            if source is None:
                continue

            if source.status == "invalid":
                continue

            reliabilities.append(
                source.reliability
            )

        if not reliabilities:
            return concept.confidence

        source_score = sum(
            reliabilities
        ) / len(
            reliabilities
        )

        return (
            concept.confidence
            * 0.5
            + source_score
            * 0.5
        )

    # ============================================================
    # CONTRADICTIONS
    # ============================================================

    def find_similar(
        self,
        concept: Concept,
        *,
        threshold: float = 0.25,
    ) -> list[Concept]:
        """
        Find concepts that share enough lexical information with
        the supplied concept.

        This is intentionally simple.

        A future semantic/vector retrieval system can replace or
        augment this mechanism.
        """

        query_words = _words(
            " ".join(
                [
                    concept.name,
                    concept.statement,
                ]
            )
        )

        if not query_words:
            return []

        results: list[
            tuple[
                float,
                Concept,
            ]
        ] = []

        for candidate in self.concepts.values():
            if candidate.id == concept.id:
                continue

            candidate_words = _words(
                " ".join(
                    [
                        candidate.name,
                        candidate.statement,
                    ]
                )
            )

            if not candidate_words:
                continue

            overlap = (
                len(
                    query_words
                    & candidate_words
                )
                / len(
                    query_words
                    | candidate_words
                )
            )

            if overlap >= threshold:
                results.append(
                    (
                        overlap,
                        candidate,
                    )
                )

        results.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            item[1]
            for item in results
        ]

    def detect_contradictions(
        self,
        concept: Concept,
    ) -> list[Concept]:
        """
        Find potentially contradictory concepts.

        This performs a conservative heuristic check.

        Actual semantic contradiction detection belongs in the
        evaluator/LLM layer.
        """

        candidates = self.find_similar(
            concept
        )

        contradictions: list[
            Concept
        ] = []

        negative_markers = {
            "not",
            "never",
            "false",
            "incorrect",
            "cannot",
            "can't",
            "no",
            "doesn't",
            "isn't",
            "wrong",
        }

        concept_words = _words(
            concept.statement
        )

        for candidate in candidates:
            candidate_words = _words(
                candidate.statement
            )

            if not (
                concept_words
                & candidate_words
            ):
                continue

            concept_negative = bool(
                concept_words
                & negative_markers
            )

            candidate_negative = bool(
                candidate_words
                & negative_markers
            )

            if (
                concept_negative
                != candidate_negative
            ):
                contradictions.append(
                    candidate
                )

        return contradictions

    # ============================================================
    # STATISTICS
    # ============================================================

    def statistics(
        self,
    ) -> KnowledgeStats:
        """
        Return knowledge-base statistics.
        """

        concepts = list(
            self.concepts.values()
        )

        stats = KnowledgeStats(
            concepts=len(
                concepts
            ),
            sources=len(
                self.sources.get_all()
            ),
            trusted_sources=len(
                self.sources.trusted()
            ),
        )

        if not concepts:
            return stats

        total_confidence = 0.0

        for concept in concepts:
            total_confidence += (
                concept.confidence
            )

            if concept.status == "trusted":
                stats.trusted_concepts += 1

            elif concept.status == "uncertain":
                stats.uncertain_concepts += 1

            elif concept.status == "disputed":
                stats.disputed_concepts += 1

            elif concept.status == "candidate":
                stats.candidate_concepts += 1

            elif concept.status == "deprecated":
                stats.deprecated_concepts += 1

        stats.average_confidence = (
            total_confidence
            / len(concepts)
        )

        return stats

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize the knowledge registry.
        """

        return {
            "concepts": [
                concept.to_dict()
                for concept
                in self.concepts.values()
            ],
            "sources": self.sources.to_dict(),
        }

    def from_dict(
        self,
        data: dict[str, Any],
    ) -> None:
        """
        Restore the knowledge registry.
        """

        self.concepts.clear()

        if not isinstance(
            data,
            dict,
        ):
            return

        source_data = data.get(
            "sources",
            [],
        )

        self.sources.from_dict(
            source_data
        )

        concept_data = data.get(
            "concepts",
            [],
        )

        if not isinstance(
            concept_data,
            list,
        ):
            return

        for entry in concept_data:
            if not isinstance(
                entry,
                dict,
            ):
                continue

            concept = Concept.from_dict(
                entry
            )

            if concept.id:
                self.concepts[
                    concept.id
                ] = concept

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    def _resolve_source_id(
        self,
        source: Source | str | None,
    ) -> str | None:
        """
        Resolve a Source object or source ID.
        """

        if source is None:
            return None

        if isinstance(
            source,
            Source,
        ):
            if source.id not in self.sources.sources:
                self.sources.sources[
                    source.id
                ] = source

            return source.id

        source_id = str(
            source
        ).strip()

        if (
            source_id
            and self.sources.get(
                source_id
            )
            is not None
        ):
            return source_id

        return None

    def _update_existing_knowledge(
        self,
        concept: Concept,
        *,
        source: Source | str | None,
        confidence: float,
    ) -> None:
        """
        Update an existing concept when the same knowledge is
        encountered again.
        """

        source_id = (
            self._resolve_source_id(
                source
            )
        )

        if source_id:
            concept.add_source(
                source_id
            )

        # Repeated independent observations should gradually
        # increase confidence rather than instantly maxing it out.
        delta = (
            confidence
            - concept.confidence
        ) * 0.25

        concept.update_confidence(
            concept.confidence
            + delta
        )

        if concept.confidence >= 0.75:
            concept.status = "trusted"

    def _calculate_score(
        self,
        concept: Concept,
        query_words: set[str],
        matched_words: set[str],
    ) -> float:
        """
        Calculate a basic retrieval score.
        """

        if not query_words:
            return 0.0

        lexical_score = (
            len(matched_words)
            / len(query_words)
        )

        confidence_bonus = (
            concept.confidence
            * 0.20
        )

        importance_bonus = (
            concept.importance
            * 0.10
        )

        status_bonus = (
            0.10
            if concept.status
            == "trusted"
            else 0.0
        )

        return (
            lexical_score
            + confidence_bonus
            + importance_bonus
            + status_bonus
        )

    def _recalculate_concept_confidence(
        self,
        concept: Concept,
    ) -> None:
        """
        Recalculate confidence using evidence.

        Supporting and contradictory evidence both contribute.
        """

        if not concept.evidence:
            return

        supporting = [
            item
            for item in concept.evidence
            if item.supports
        ]

        contradicting = [
            item
            for item in concept.evidence
            if not item.supports
        ]

        support_score = (
            sum(
                item.confidence
                for item in supporting
            )
            / len(supporting)
            if supporting
            else 0.0
        )

        contradiction_score = (
            sum(
                item.confidence
                for item in contradicting
            )
            / len(contradicting)
            if contradicting
            else 0.0
        )

        evidence_score = max(
            0.0,
            min(
                1.0,
                support_score
                - (
                    contradiction_score
                    * 0.5
                ),
            ),
        )

        # Blend existing confidence with evidence rather than
        # replacing it completely.
        concept.update_confidence(
            (
                concept.confidence
                * 0.5
            )
            + (
                evidence_score
                * 0.5
            )
        )

        if (
            concept.confidence
            >= 0.75
            and not contradicting
        ):
            concept.status = "trusted"

        elif (
            contradicting
            and concept.confidence
            < 0.50
        ):
            concept.status = "disputed"

    def _next_concept_id(
        self,
    ) -> str:
        """
        Generate the next concept ID.
        """

        highest = 0

        for concept_id in self.concepts:
            if not concept_id.startswith(
                "concept_"
            ):
                continue

            try:
                number = int(
                    concept_id.split(
                        "_"
                    )[-1]
                )
            except ValueError:
                continue

            highest = max(
                highest,
                number,
            )

        return (
            f"concept_{highest + 1}"
        )


# ================================================================
# HELPERS
# ================================================================


def _normalize(
    text: str,
) -> str:
    """
    Normalize text for exact comparisons.
    """

    return " ".join(
        str(
            text
        )
        .strip()
        .lower()
        .split()
    )


def _words(
    text: str,
) -> set[str]:
    """
    Convert text into normalized words.
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