"""
MaryV2 - Learning Evaluator

Responsible for evaluating information before it becomes trusted
knowledge.

The evaluator does not search the web and does not permanently
store knowledge.

Its job is to answer:

    How reliable does this information appear?
    How relevant is it?
    How useful is it?
    How novel is it?
    Should Mary accept, reject, or review it?

Architecture:

    Researcher
        ↓
    Sources
        ↓
    Evaluator
        ↓
    Evaluation
        ↓
    Learning Knowledge
        ↓
    Long-Term Knowledge
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


# ================================================================
# EVALUATION
# ================================================================


@dataclass
class Evaluation:
    """
    Evaluation of a piece of information.

    Scores are normalized between 0.0 and 1.0.
    """

    id: str

    subject: str

    statement: str

    reliability: float = 0.5

    relevance: float = 0.5

    usefulness: float = 0.5

    novelty: float = 0.5

    confidence: float = 0.5

    recommendation: str = "review"

    reasoning: str = ""

    created_at: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _timestamp()

        self.reliability = _clamp(
            self.reliability
        )

        self.relevance = _clamp(
            self.relevance
        )

        self.usefulness = _clamp(
            self.usefulness
        )

        self.novelty = _clamp(
            self.novelty
        )

        self.confidence = _clamp(
            self.confidence
        )


# ================================================================
# EVALUATOR
# ================================================================


class Evaluator:
    """
    Evaluates information before it enters Mary's trusted
    knowledge system.

    The evaluator supports both:

    1. Rule-based evaluation
    2. Future LLM-assisted evaluation

    The initial implementation remains deterministic so the system
    can operate without requiring another LLM call for every piece
    of information.
    """

    ACCEPT_THRESHOLD = 0.75
    REVIEW_THRESHOLD = 0.45

    def __init__(
        self,
        llm: Any | None = None,
    ) -> None:
        self.llm = llm

        self.evaluations: list[
            Evaluation
        ] = []

    # ============================================================
    # EVALUATE
    # ============================================================

    def evaluate(
        self,
        subject: str,
        statement: str,
        *,
        source: Any | None = None,
        context: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Evaluation:
        """
        Evaluate a statement.

        If an external source is supplied, source metadata is used
        to establish an initial reliability estimate.

        The LLM is optional and is reserved for more sophisticated
        evaluation later.
        """

        reliability = self._estimate_reliability(
            source
        )

        relevance = self._estimate_relevance(
            statement,
            context,
        )

        usefulness = self._estimate_usefulness(
            statement,
            context,
        )

        novelty = self._estimate_novelty(
            statement
        )

        confidence = self._calculate_confidence(
            reliability=reliability,
            relevance=relevance,
            usefulness=usefulness,
        )

        recommendation = (
            self._recommend(
                confidence
            )
        )

        reasoning = self._build_reasoning(
            reliability=reliability,
            relevance=relevance,
            usefulness=usefulness,
            novelty=novelty,
            confidence=confidence,
        )

        evaluation = Evaluation(
            id=self._next_id(),
            subject=str(
                subject
            ).strip(),
            statement=str(
                statement
            ).strip(),
            reliability=reliability,
            relevance=relevance,
            usefulness=usefulness,
            novelty=novelty,
            confidence=confidence,
            recommendation=recommendation,
            reasoning=reasoning,
            metadata=metadata or {},
        )

        self.evaluations.append(
            evaluation
        )

        return evaluation

    # ============================================================
    # SOURCE RELIABILITY
    # ============================================================

    def _estimate_reliability(
        self,
        source: Any | None,
    ) -> float:
        """
        Estimate source reliability.

        This is intentionally conservative.

        A source's existence does not automatically make it
        trustworthy.
        """

        if source is None:
            return 0.5

        confidence = getattr(
            source,
            "confidence",
            None,
        )

        if confidence is not None:
            return _clamp(
                confidence
            )

        metadata = getattr(
            source,
            "metadata",
            {},
        )

        if isinstance(
            metadata,
            dict,
        ):
            value = metadata.get(
                "reliability"
            )

            if value is not None:
                return _clamp(
                    value
                )

        source_type = str(
            getattr(
                source,
                "source_type",
                "unknown",
            )
        ).lower()

        trusted_types = {
            "official",
            "documentation",
            "academic",
            "research",
            "government",
        }

        if source_type in trusted_types:
            return 0.8

        if source_type == "web":
            return 0.5

        return 0.4

    # ============================================================
    # RELEVANCE
    # ============================================================

    def _estimate_relevance(
        self,
        statement: str,
        context: str,
    ) -> float:
        """
        Estimate how relevant information is to the current
        research context.
        """

        statement_words = _words(
            statement
        )

        context_words = _words(
            context
        )

        if not context_words:
            return 0.7

        if not statement_words:
            return 0.0

        overlap = (
            len(
                statement_words
                & context_words
            )
            / max(
                len(context_words),
                1,
            )
        )

        return _clamp(
            min(
                overlap * 2.0,
                1.0,
            )
        )

    # ============================================================
    # USEFULNESS
    # ============================================================

    def _estimate_usefulness(
        self,
        statement: str,
        context: str,
    ) -> float:
        """
        Estimate practical usefulness.

        This is intentionally heuristic in V2.

        A future evaluator can use an LLM to make a deeper
        judgment.
        """

        if not statement.strip():
            return 0.0

        length = len(
            statement.split()
        )

        score = 0.5

        if length >= 5:
            score += 0.1

        if length >= 15:
            score += 0.1

        if context.strip():
            score += 0.1

        useful_terms = {
            "how",
            "why",
            "method",
            "solution",
            "example",
            "evidence",
            "documentation",
            "research",
            "implementation",
            "explanation",
            "process",
        }

        statement_words = _words(
            statement
        )

        if statement_words & useful_terms:
            score += 0.1

        return _clamp(
            score
        )

    # ============================================================
    # NOVELTY
    # ============================================================

    def _estimate_novelty(
        self,
        statement: str,
    ) -> float:
        """
        Estimate novelty.

        True semantic novelty belongs in the knowledge/retrieval
        layer once embeddings or semantic search are available.

        For now this provides a neutral starting estimate.
        """

        if not statement.strip():
            return 0.0

        return 0.5

    # ============================================================
    # CONFIDENCE
    # ============================================================

    def _calculate_confidence(
        self,
        *,
        reliability: float,
        relevance: float,
        usefulness: float,
    ) -> float:
        """
        Calculate overall evaluation confidence.

        Reliability receives the largest weight because Mary should
        not trust information simply because it is interesting.
        """

        confidence = (
            reliability * 0.55
            + relevance * 0.25
            + usefulness * 0.20
        )

        return _clamp(
            confidence
        )

    # ============================================================
    # RECOMMENDATION
    # ============================================================

    def _recommend(
        self,
        confidence: float,
    ) -> str:
        """
        Convert confidence into a learning recommendation.
        """

        if confidence >= self.ACCEPT_THRESHOLD:
            return "accept"

        if confidence >= self.REVIEW_THRESHOLD:
            return "review"

        return "reject"

    # ============================================================
    # REASONING
    # ============================================================

    def _build_reasoning(
        self,
        *,
        reliability: float,
        relevance: float,
        usefulness: float,
        novelty: float,
        confidence: float,
    ) -> str:
        """
        Produce a human-readable explanation of the evaluation.
        """

        return (
            "Reliability="
            f"{reliability:.2f}, "
            "relevance="
            f"{relevance:.2f}, "
            "usefulness="
            f"{usefulness:.2f}, "
            "novelty="
            f"{novelty:.2f}, "
            "overall confidence="
            f"{confidence:.2f}."
        )

    # ============================================================
    # ACCESS
    # ============================================================

    def get(
        self,
        evaluation_id: str,
    ) -> Evaluation | None:
        """
        Retrieve an evaluation by ID.
        """

        for evaluation in self.evaluations:
            if evaluation.id == evaluation_id:
                return evaluation

        return None

    def get_all(
        self,
    ) -> list[Evaluation]:
        """
        Return all evaluations.
        """

        return list(
            self.evaluations
        )

    def get_accepted(
        self,
    ) -> list[Evaluation]:
        """
        Return evaluations recommended for acceptance.
        """

        return [
            evaluation
            for evaluation in self.evaluations
            if evaluation.recommendation
            == "accept"
        ]

    def get_for_review(
        self,
    ) -> list[Evaluation]:
        """
        Return evaluations that require additional review.
        """

        return [
            evaluation
            for evaluation in self.evaluations
            if evaluation.recommendation
            == "review"
        ]

    def get_rejected(
        self,
    ) -> list[Evaluation]:
        """
        Return evaluations recommended for rejection.
        """

        return [
            evaluation
            for evaluation in self.evaluations
            if evaluation.recommendation
            == "reject"
        ]

    # ============================================================
    # MANUAL OVERRIDE
    # ============================================================

    def override(
        self,
        evaluation_id: str,
        recommendation: str,
        *,
        reason: str = "",
    ) -> bool:
        """
        Manually override an evaluation recommendation.

        This is useful during development and testing.
        """

        evaluation = self.get(
            evaluation_id
        )

        if evaluation is None:
            return False

        recommendation = str(
            recommendation
        ).strip().lower()

        if recommendation not in {
            "accept",
            "review",
            "reject",
        }:
            return False

        evaluation.recommendation = (
            recommendation
        )

        if reason:
            evaluation.reasoning = (
                f"{evaluation.reasoning} "
                f"Manual override: {reason}"
            ).strip()

        return True

    # ============================================================
    # BATCH EVALUATION
    # ============================================================

    def evaluate_many(
        self,
        items: list[dict[str, Any]],
    ) -> list[Evaluation]:
        """
        Evaluate multiple information items.
        """

        results: list[
            Evaluation
        ] = []

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                continue

            evaluation = self.evaluate(
                subject=str(
                    item.get(
                        "subject",
                        "",
                    )
                ),
                statement=str(
                    item.get(
                        "statement",
                        "",
                    )
                ),
                source=item.get(
                    "source"
                ),
                context=str(
                    item.get(
                        "context",
                        "",
                    )
                ),
                metadata=item.get(
                    "metadata",
                    {},
                ),
            )

            results.append(
                evaluation
            )

        return results

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> list[dict[str, Any]]:
        """
        Serialize evaluator state.
        """

        return [
            asdict(evaluation)
            for evaluation in self.evaluations
        ]

    def from_dict(
        self,
        data: list[dict[str, Any]],
    ) -> None:
        """
        Restore evaluator state.
        """

        self.evaluations.clear()

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

            evaluation = Evaluation(
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
                reliability=_clamp(
                    entry.get(
                        "reliability",
                        0.5,
                    )
                ),
                relevance=_clamp(
                    entry.get(
                        "relevance",
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
                confidence=_clamp(
                    entry.get(
                        "confidence",
                        0.5,
                    )
                ),
                recommendation=str(
                    entry.get(
                        "recommendation",
                        "review",
                    )
                ),
                reasoning=str(
                    entry.get(
                        "reasoning",
                        "",
                    )
                ),
                created_at=str(
                    entry.get(
                        "created_at",
                        _timestamp(),
                    )
                ),
                metadata=entry.get(
                    "metadata",
                    {},
                ),
            )

            self.evaluations.append(
                evaluation
            )

    # ============================================================
    # ID GENERATION
    # ============================================================

    def _next_id(
        self,
    ) -> str:
        """
        Generate the next evaluation ID.
        """

        highest = 0

        for evaluation in self.evaluations:
            evaluation_id = str(
                evaluation.id
            )

            if not evaluation_id.startswith(
                "evaluation_"
            ):
                continue

            try:
                number = int(
                    evaluation_id.split(
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
            f"evaluation_{highest + 1}"
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


def _words(
    text: str,
) -> set[str]:
    """
    Convert text into a basic set of normalized words.
    """

    return {
        word.strip(
            ".,!?;:\"'()[]{}"
        ).lower()
        for word in str(
            text
        ).split()
        if word.strip(
            ".,!?;:\"'()[]{}"
        )
    }


def _timestamp() -> str:
    """
    Return a timezone-aware UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()