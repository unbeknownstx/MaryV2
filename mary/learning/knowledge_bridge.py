"""Connect evaluated research into Mary's existing learning/knowledge systems."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class KnowledgeLearningOutcome:
    candidate_id: str
    recommendation: str
    candidate_status: str
    promoted: bool = False
    concept_id: str | None = None
    source_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class KnowledgeLearningBridge:
    """Coordinate evaluated information without becoming a knowledge authority.

    Ownership remains intentionally split:
    - Evaluator owns the evaluation.
    - LearningKnowledge owns candidate/review state.
    - KnowledgeManager owns accepted long-term concepts and provenance.
    - Learner records the learning event/history.
    """

    def __init__(
        self,
        *,
        candidates: Any,
        knowledge: Any,
        learner: Any,
        on_change: Callable[[], Any] | None = None,
    ) -> None:
        self.candidates = candidates
        self.knowledge = knowledge
        self.learner = learner
        self.on_change = on_change

    def ingest_evaluation(
        self,
        *,
        subject: str,
        statement: str,
        source: Any | None,
        evaluation: Any,
        category: str = "research",
    ) -> KnowledgeLearningOutcome:
        source_title = str(getattr(source, "title", "") or "").strip()
        source_url = str(getattr(source, "url", "") or "").strip()
        source_type = str(getattr(source, "source_type", "unknown") or "unknown").strip().lower()

        confidence = float(getattr(evaluation, "confidence", 0.5) or 0.5)
        usefulness = float(getattr(evaluation, "usefulness", 0.5) or 0.5)
        novelty = float(getattr(evaluation, "novelty", 0.5) or 0.5)
        reliability = float(getattr(evaluation, "reliability", 0.5) or 0.5)
        recommendation = str(getattr(evaluation, "recommendation", "review") or "review").strip().lower()
        evaluation_id = str(getattr(evaluation, "id", "") or "")

        event = self.learner.record(
            event_type="evaluated_research",
            subject=subject,
            content=statement,
            source=source_url or None,
            confidence=confidence,
            usefulness=usefulness,
            metadata={
                "recommendation": recommendation,
                "evaluation_id": evaluation_id,
                "source_title": source_title,
                "source_type": source_type,
            },
        )
        self.learner.mark_evaluated(
            event.id,
            confidence=confidence,
            usefulness=usefulness,
        )

        candidate = self.candidates.create(
            subject=subject,
            statement=statement,
            category=category,
            source=source_url or None,
            confidence=confidence,
            usefulness=usefulness,
            novelty=novelty,
            metadata={
                "evaluation_id": evaluation_id,
                "recommendation": recommendation,
                "source_title": source_title,
                "source_type": source_type,
            },
        )
        self.candidates.evaluate(
            candidate.id,
            confidence=confidence,
            usefulness=usefulness,
            novelty=novelty,
        )

        if recommendation == "reject":
            self.candidates.reject(candidate.id)
            self.learner.reject(event.id)
            self._changed()
            return KnowledgeLearningOutcome(
                candidate_id=candidate.id,
                recommendation="reject",
                candidate_status="rejected",
            )

        if recommendation != "accept":
            self._changed()
            return KnowledgeLearningOutcome(
                candidate_id=candidate.id,
                recommendation="review",
                candidate_status="evaluated",
            )

        self.candidates.accept(candidate.id)
        self.learner.accept(event.id)

        knowledge_source = self._knowledge_source(
            source=source,
            title=source_title,
            url=source_url,
            source_type=source_type,
            reliability=reliability,
            evaluation_id=evaluation_id,
        )

        concept_name = (
            str(subject or "").strip()
            or source_title
            or "researched knowledge"
        )

        aliases = []
        if source_title and source_title.casefold() != concept_name.casefold():
            aliases.append(source_title)

        concept = self.knowledge.learn(
            name=concept_name,
            statement=statement,
            source=knowledge_source,
            knowledge_type="observation",
            confidence=confidence,
            importance=usefulness,
            tags=["research", category],
            aliases=aliases,
            metadata={
                "evaluation_id": evaluation_id,
                "recommendation": recommendation,
                "candidate_id": candidate.id,
                "source_url": source_url,
            },
        )

        # Accepted evaluator output is the explicit gate that permits this
        # concept to enter the trusted knowledge set. The manager remains the
        # owner of the resulting concept and provenance.
        self.knowledge.add_evidence(
            concept.id,
            statement,
            supports=True,
            confidence=confidence,
            source=knowledge_source,
            metadata={
                "evaluation_id": evaluation_id,
                "candidate_id": candidate.id,
            },
        )
        self.knowledge.trust(
            concept.id,
            confidence=max(confidence, float(getattr(concept, "confidence", 0.0) or 0.0)),
        )
        self.candidates.mark_merged(candidate.id)

        self.learner.record(
            event_type="knowledge_promoted",
            subject=concept_name,
            content=statement,
            source=source_url or None,
            confidence=confidence,
            usefulness=usefulness,
            metadata={
                "concept_id": concept.id,
                "candidate_id": candidate.id,
                "source_id": getattr(knowledge_source, "id", None),
            },
        )

        self._changed()

        return KnowledgeLearningOutcome(
            candidate_id=candidate.id,
            recommendation="accept",
            candidate_status="merged",
            promoted=True,
            concept_id=concept.id,
            source_id=getattr(knowledge_source, "id", None),
        )

    def _knowledge_source(
        self,
        *,
        source: Any | None,
        title: str,
        url: str,
        source_type: str,
        reliability: float,
        evaluation_id: str,
    ) -> Any:
        # Reuse a previously registered exact location when possible.
        if url:
            for existing in self.knowledge.sources.get_all():
                if str(getattr(existing, "location", "") or "").strip() == url:
                    existing.set_reliability(
                        max(float(getattr(existing, "reliability", 0.0) or 0.0), reliability)
                    )
                    existing.verify(reliability=existing.reliability)
                    return existing

        metadata = dict(getattr(source, "metadata", {}) or {})
        metadata["evaluation_id"] = evaluation_id

        created = self.knowledge.create_source(
            title=title or url or "Research source",
            source_type=source_type,
            location=url,
            description=str(getattr(source, "content", "") or "")[:1000],
            reliability=reliability,
            status="active",
            metadata=metadata,
        )
        created.verify(reliability=reliability)
        return created

    def _changed(self) -> None:
        if self.on_change is None:
            return
        try:
            self.on_change()
        except Exception:
            # Persistence/reporting errors are exposed by the persistence
            # adapter status; they must not rewrite the evaluation decision.
            pass
