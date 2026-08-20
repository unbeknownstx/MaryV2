"""
MaryV2 - Learning Knowledge

Responsible for turning evaluated learning material into structured
knowledge candidates.

This module does not blindly trust information.

Architecture:

    Research
       ↓
    Evaluation
       ↓
    Learning Knowledge
       ↓
    Knowledge Manager
       ↓
    Long-Term Knowledge

Knowledge created here should be considered candidate knowledge
until it has passed the appropriate evaluation and validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from mary.governance.bounds import bounded_payload, clip_text


# ================================================================
# KNOWLEDGE CANDIDATE
# ================================================================


@dataclass
class KnowledgeCandidate:
    """
    A piece of information that Mary may eventually incorporate
    into her long-term knowledge system.
    """

    id: str

    subject: str

    statement: str

    category: str = "general"

    source: str | None = None

    confidence: float = 0.5

    usefulness: float = 0.5

    novelty: float = 0.5

    status: str = "candidate"

    created_at: str = ""

    evaluated_at: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _timestamp()

        self.confidence = _clamp(
            self.confidence
        )

        self.usefulness = _clamp(
            self.usefulness
        )

        self.novelty = _clamp(
            self.novelty
        )


# ================================================================
# KNOWLEDGE SYSTEM
# ================================================================


class LearningKnowledge:
    """
    Manages candidate knowledge produced by the learning pipeline.

    This system intentionally does not own Mary's permanent
    knowledge base.

    The long-term knowledge layer lives under:

        mary/knowledge/
    """

    VALID_STATUSES = {
        "candidate",
        "evaluated",
        "accepted",
        "rejected",
        "merged",
    }

    def __init__(self, *, capacity: int = 512, text_limit: int = 4000) -> None:
        self.candidates: list[KnowledgeCandidate] = []
        self.capacity = max(1, int(capacity))
        self.text_limit = max(256, int(text_limit))

    def _trim(self) -> None:
        del self.candidates[:-self.capacity]

    # ============================================================
    # CREATE
    # ============================================================

    def create(
        self,
        subject: str,
        statement: str,
        *,
        category: str = "general",
        source: str | None = None,
        confidence: float = 0.5,
        usefulness: float = 0.5,
        novelty: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeCandidate:
        """
        Create a new candidate knowledge item.
        """

        candidate = KnowledgeCandidate(
            id=self._next_id(),
            subject=clip_text(subject, self.text_limit),
            statement=clip_text(statement, self.text_limit),
            category=clip_text(category, 160),
            source=source,
            confidence=confidence,
            usefulness=usefulness,
            novelty=novelty,
            metadata=bounded_payload(metadata or {}, text_limit=self.text_limit),
        )

        self.candidates.append(candidate)
        self._trim()

        return candidate

    # ============================================================
    # CREATE FROM RESEARCH
    # ============================================================

    def from_research_source(
        self,
        source: Any,
        *,
        subject: str = "",
        statement: str | None = None,
        category: str = "general",
    ) -> KnowledgeCandidate:
        """
        Convert a research source into a knowledge candidate.

        The source is not automatically considered trustworthy.
        Its existing confidence and relevance are carried into the
        candidate as initial values.
        """

        source_title = getattr(
            source,
            "title",
            "",
        )

        source_url = getattr(
            source,
            "url",
            None,
        )

        source_content = getattr(
            source,
            "content",
            "",
        )

        source_confidence = getattr(
            source,
            "confidence",
            0.5,
        )

        source_relevance = getattr(
            source,
            "relevance",
            0.5,
        )

        if not subject:
            subject = source_title

        if statement is None:
            statement = source_content

        return self.create(
            subject=subject,
            statement=statement,
            category=category,
            source=source_url,
            confidence=source_confidence,
            usefulness=source_relevance,
            novelty=0.5,
            metadata={
                "source_title": source_title,
                "source_url": source_url,
            },
        )

    # ============================================================
    # GET
    # ============================================================

    def get(
        self,
        candidate_id: str,
    ) -> KnowledgeCandidate | None:
        """
        Retrieve a candidate by ID.
        """

        for candidate in self.candidates:
            if candidate.id == candidate_id:
                return candidate

        return None

    def get_all(
        self,
    ) -> list[KnowledgeCandidate]:
        """
        Return all candidates.
        """

        return list(
            self.candidates
        )

    def get_candidates(
        self,
    ) -> list[KnowledgeCandidate]:
        """
        Return items still awaiting a final decision.
        """

        return [
            candidate
            for candidate in self.candidates
            if candidate.status == "candidate"
        ]

    # ============================================================
    # FILTERING
    # ============================================================

    def get_by_subject(
        self,
        subject: str,
    ) -> list[KnowledgeCandidate]:
        """
        Find knowledge related to a subject.
        """

        normalized = str(
            subject
        ).strip().lower()

        return [
            candidate
            for candidate in self.candidates
            if normalized
            in candidate.subject.lower()
        ]

    def get_by_category(
        self,
        category: str,
    ) -> list[KnowledgeCandidate]:
        """
        Return candidates belonging to a category.
        """

        normalized = str(
            category
        ).strip().lower()

        return [
            candidate
            for candidate in self.candidates
            if candidate.category.lower()
            == normalized
        ]

    def get_high_confidence(
        self,
        minimum: float = 0.7,
    ) -> list[KnowledgeCandidate]:
        """
        Return high-confidence knowledge candidates.
        """

        minimum = _clamp(
            minimum
        )

        return [
            candidate
            for candidate in self.candidates
            if candidate.confidence
            >= minimum
        ]

    def get_high_value(
        self,
        minimum_confidence: float = 0.7,
        minimum_usefulness: float = 0.7,
    ) -> list[KnowledgeCandidate]:
        """
        Return candidates that are both reliable and useful.
        """

        minimum_confidence = _clamp(
            minimum_confidence
        )

        minimum_usefulness = _clamp(
            minimum_usefulness
        )

        return [
            candidate
            for candidate in self.candidates
            if (
                candidate.confidence
                >= minimum_confidence
                and candidate.usefulness
                >= minimum_usefulness
            )
        ]

    # ============================================================
    # EVALUATION
    # ============================================================

    def evaluate(
        self,
        candidate_id: str,
        *,
        confidence: float | None = None,
        usefulness: float | None = None,
        novelty: float | None = None,
    ) -> KnowledgeCandidate | None:
        """
        Update the evaluation values for a candidate.
        """

        candidate = self.get(
            candidate_id
        )

        if candidate is None:
            return None

        if confidence is not None:
            candidate.confidence = _clamp(
                confidence
            )

        if usefulness is not None:
            candidate.usefulness = _clamp(
                usefulness
            )

        if novelty is not None:
            candidate.novelty = _clamp(
                novelty
            )

        candidate.status = "evaluated"

        candidate.evaluated_at = (
            _timestamp()
        )

        return candidate

    # ============================================================
    # ACCEPT / REJECT
    # ============================================================

    def accept(
        self,
        candidate_id: str,
    ) -> bool:
        """
        Accept a candidate for transfer into long-term knowledge.
        """

        candidate = self.get(
            candidate_id
        )

        if candidate is None:
            return False

        candidate.status = "accepted"

        return True

    def reject(
        self,
        candidate_id: str,
    ) -> bool:
        """
        Reject a candidate.

        Rejected information remains in the learning record so Mary
        can later understand that she encountered and rejected it.
        """

        candidate = self.get(
            candidate_id
        )

        if candidate is None:
            return False

        candidate.status = "rejected"

        return True

    def mark_merged(
        self,
        candidate_id: str,
    ) -> bool:
        """
        Mark a candidate as merged into existing knowledge.
        """

        candidate = self.get(
            candidate_id
        )

        if candidate is None:
            return False

        candidate.status = "merged"

        return True

    # ============================================================
    # KNOWLEDGE TRANSFER
    # ============================================================

    def get_ready_for_storage(
        self,
    ) -> list[KnowledgeCandidate]:
        """
        Return accepted candidates ready for the long-term
        knowledge manager.
        """

        return [
            candidate
            for candidate in self.candidates
            if candidate.status == "accepted"
        ]

    # ============================================================
    # DUPLICATE DETECTION
    # ============================================================

    def find_similar(
        self,
        statement: str,
    ) -> list[KnowledgeCandidate]:
        """
        Perform a simple text-level similarity check.

        This is intentionally lightweight.

        Semantic/vector similarity belongs in the retrieval and
        knowledge infrastructure later.
        """

        normalized = _normalize_text(
            statement
        )

        if not normalized:
            return []

        words = set(
            normalized.split()
        )

        matches: list[
            KnowledgeCandidate
        ] = []

        for candidate in self.candidates:
            candidate_words = set(
                _normalize_text(
                    candidate.statement
                ).split()
            )

            if not candidate_words:
                continue

            overlap = (
                len(
                    words
                    & candidate_words
                )
                / max(
                    len(words),
                    1,
                )
            )

            if overlap >= 0.5:
                matches.append(
                    candidate
                )

        return matches

    # ============================================================
    # VALUE SCORE
    # ============================================================

    def value_score(
        self,
        candidate: KnowledgeCandidate,
    ) -> float:
        """
        Calculate the overall value of a candidate.

        Confidence is weighted most heavily because useful but
        unreliable information should not automatically become
        knowledge.
        """

        return (
            candidate.confidence * 0.50
            + candidate.usefulness * 0.30
            + candidate.novelty * 0.20
        )

    def rank(
        self,
    ) -> list[KnowledgeCandidate]:
        """
        Rank candidates by overall learning value.
        """

        return sorted(
            self.candidates,
            key=self.value_score,
            reverse=True,
        )

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> list[dict[str, Any]]:
        """
        Serialize knowledge candidates.
        """

        return [
            asdict(candidate)
            for candidate in self.candidates
        ]

    def from_dict(
        self,
        data: list[dict[str, Any]],
    ) -> None:
        """
        Restore knowledge candidates.
        """

        self.candidates.clear()

        if not isinstance(
            data,
            list,
        ):
            return

        for entry in data:
            if not isinstance(
                entry,
                dict,
            ):
                continue

            candidate = KnowledgeCandidate(
                id=str(
                    entry.get(
                        "id",
                        "",
                    )
                ),
                subject=str(
                    entry.get(
                        "subject",
                        "",
                    )
                ),
                statement=str(
                    entry.get(
                        "statement",
                        "",
                    )
                ),
                category=str(
                    entry.get(
                        "category",
                        "general",
                    )
                ),
                source=entry.get(
                    "source"
                ),
                confidence=_clamp(
                    entry.get(
                        "confidence",
                        0.5,
                    )
                ),
                usefulness=_clamp(
                    entry.get(
                        "usefulness",
                        0.5,
                    )
                ),
                novelty=_clamp(
                    entry.get(
                        "novelty",
                        0.5,
                    )
                ),
                status=str(
                    entry.get(
                        "status",
                        "candidate",
                    )
                ),
                created_at=str(
                    entry.get(
                        "created_at",
                        _timestamp(),
                    )
                ),
                evaluated_at=entry.get(
                    "evaluated_at"
                ),
                metadata=entry.get(
                    "metadata",
                    {},
                ),
            )

            self.candidates.append(candidate)

        self._trim()

    # ============================================================
    # ID GENERATION
    # ============================================================

    def _next_id(
        self,
    ) -> str:
        """
        Generate the next candidate ID.
        """

        highest = 0

        for candidate in self.candidates:
            candidate_id = str(
                candidate.id
            )

            if not candidate_id.startswith(
                "knowledge_"
            ):
                continue

            try:
                number = int(
                    candidate_id.split(
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
            f"knowledge_{highest + 1}"
        )


# ================================================================
# HELPERS
# ================================================================


def _clamp(
    value: float,
) -> float:
    """
    Keep a numeric value between 0.0 and 1.0.
    """

    try:
        value = float(value)
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


def _normalize_text(
    text: str,
) -> str:
    """
    Normalize text for basic duplicate detection.
    """

    return " ".join(
        str(text)
        .lower()
        .strip()
        .split()
    )


def _timestamp() -> str:
    """
    Return a timezone-aware UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()