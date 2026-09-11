from dataclasses import dataclass

from mary.continuity.memory_lab import MemoryEvaluationSuite


@dataclass(frozen=True)
class Hit:
    record_id: str


class FakeCanonicalRetriever:
    def __init__(self, ids):
        self.ids = list(ids)
        self.calls = []

    def search(self, query, *, limit, minimum_confidence, context):
        self.calls.append({
            "query": query,
            "limit": limit,
            "minimum_confidence": minimum_confidence,
            "context": dict(context),
        })
        return [Hit(value) for value in self.ids[:limit]]


def test_memory_lab_evaluates_injected_canonical_retriever_without_promotion():
    retriever = FakeCanonicalRetriever(["current-fact", "older-fact"])
    result = MemoryEvaluationSuite().evaluate_retrieval(
        retriever,
        query="what is current?",
        expected_record_ids=["current-fact"],
        forbidden_record_ids=["invented-fact"],
        limit=5,
        context={"performance_mode": "private"},
    )
    assert result["passed"] is True
    assert result["metrics"]["recall"] == 1.0
    assert result["memory_promotion_performed"] is False
    assert result["retrieval_authority"] == "derived_candidate_selection_only"
    assert retriever.calls[0]["context"]["performance_mode"] == "private"


def test_memory_lab_fails_when_forbidden_candidate_is_retrieved():
    retriever = FakeCanonicalRetriever(["wanted", "creator-private"])
    result = MemoryEvaluationSuite().evaluate_retrieval(
        retriever,
        query="public performer recall",
        expected_record_ids=["wanted"],
        forbidden_record_ids=["creator-private"],
        context={"performance_mode": "stream"},
    )
    assert result["passed"] is False
    assert result["forbidden_hits"] == ["creator-private"]


def test_memory_lab_requires_real_retrieval_contract():
    try:
        MemoryEvaluationSuite().evaluate_retrieval(
            object(), query="x", expected_record_ids=[]
        )
    except TypeError as exc:
        assert "search" in str(exc)
    else:
        raise AssertionError("invalid retriever was accepted")
