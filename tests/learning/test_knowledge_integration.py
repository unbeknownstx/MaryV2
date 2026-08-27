"""Integration tests for Mary's evaluated-learning -> long-term knowledge path."""

from mary.core.mary import Mary
from mary.learning.evaluator import Evaluation
from mary.learning.researcher import ResearchSource
from mary.mind.sources import authoritative_records
from mary.runtime.application import create_application


def _accepted_evaluation(subject: str, statement: str) -> Evaluation:
    return Evaluation(
        id="evaluation_1",
        subject=subject,
        statement=statement,
        reliability=0.95,
        relevance=0.95,
        usefulness=0.9,
        novelty=0.7,
        confidence=0.93,
        recommendation="accept",
        reasoning="strong source and relevant evidence",
    )


def test_accepted_evaluation_flows_through_candidate_into_trusted_knowledge(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    source = ResearchSource(
        id="source_1",
        title="Python Documentation",
        url="https://docs.python.org/example",
        content="Python context managers implement a protocol for setup and cleanup.",
        source_type="documentation",
        relevance=0.95,
        confidence=0.95,
    )
    evaluation = _accepted_evaluation(
        "Python context managers",
        source.content,
    )

    outcome = mary.knowledge_learning.ingest_evaluation(
        subject=evaluation.subject,
        statement=evaluation.statement,
        source=source,
        evaluation=evaluation,
        category="research",
    )

    assert outcome.promoted is True
    assert outcome.candidate_status == "merged"
    assert outcome.concept_id

    candidate = mary.learning_knowledge.get(outcome.candidate_id)
    assert candidate is not None
    assert candidate.status == "merged"

    concept = mary.knowledge.get_concept(outcome.concept_id)
    assert concept is not None
    assert concept.status == "trusted"
    assert concept.statement == evaluation.statement
    assert concept.source_ids

    event_types = [event.event_type for event in mary.learner.get_all()]
    assert "evaluated_research" in event_types
    assert "knowledge_promoted" in event_types


def test_review_evaluation_stays_candidate_and_does_not_become_long_term_knowledge(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    evaluation = Evaluation(
        id="evaluation_review",
        subject="uncertain subject",
        statement="This requires more evidence before Mary should trust it.",
        reliability=0.55,
        relevance=0.7,
        usefulness=0.6,
        novelty=0.5,
        confidence=0.6,
        recommendation="review",
    )

    outcome = mary.knowledge_learning.ingest_evaluation(
        subject=evaluation.subject,
        statement=evaluation.statement,
        source=None,
        evaluation=evaluation,
    )

    assert outcome.promoted is False
    assert outcome.candidate_status == "evaluated"
    assert mary.learning_knowledge.get(outcome.candidate_id).status == "evaluated"
    assert mary.knowledge.get_all_concepts() == []


def test_trusted_knowledge_projects_into_rebuildable_reservoir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    concept = mary.knowledge.learn(
        name="Context manager",
        statement="A context manager coordinates setup and cleanup around a block.",
        confidence=0.9,
        importance=0.8,
    )
    mary.knowledge.trust(concept.id, confidence=0.9)

    records = list(authoritative_records(mary))
    matches = [
        record
        for record in records
        if record.kind == "knowledge_concept"
        and "Context manager" in record.content
    ]

    assert len(matches) == 1
    assert matches[0].authority == "knowledge_verified"
    assert "setup and cleanup" in matches[0].content


def test_application_persists_candidates_and_long_term_knowledge(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    memory_path = tmp_path / "memory" / "memory.json"
    knowledge_path = tmp_path / "knowledge" / "knowledge.json"

    first = create_application(
        memory_path=memory_path,
        knowledge_path=knowledge_path,
    )

    source = ResearchSource(
        id="source_persist",
        title="Official Guide",
        url="https://example.test/guide",
        content="A durable knowledge integration should preserve provenance across restart.",
        source_type="official",
        relevance=0.95,
        confidence=0.95,
    )
    evaluation = _accepted_evaluation(
        "Durable knowledge integration",
        source.content,
    )

    outcome = first.mary.knowledge_learning.ingest_evaluation(
        subject=evaluation.subject,
        statement=evaluation.statement,
        source=source,
        evaluation=evaluation,
    )

    assert outcome.promoted is True
    assert knowledge_path.exists()
    assert first.close() is True

    second = create_application(
        memory_path=memory_path,
        knowledge_path=knowledge_path,
    )

    restored = second.mary.knowledge.get_concept(outcome.concept_id)
    restored_candidate = second.mary.learning_knowledge.get(outcome.candidate_id)

    assert restored is not None
    assert restored.status == "trusted"
    assert restored_candidate is not None
    assert restored_candidate.status == "merged"
