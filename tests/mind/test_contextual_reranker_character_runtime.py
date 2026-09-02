from datetime import datetime, timezone

from mary.mind.contextual_reranker import ContextualReservoirReranker
from mary.mind.reservoir import ReservoirHit


def _hit(record_id, content, score, *, importance=0.0):
    return ReservoirHit(
        record_id=record_id,
        kind="episodic_memory",
        subject="shared_history",
        predicate="creative",
        content=content,
        source="episodic",
        authority="episodic_history",
        confidence=0.8,
        score=score,
        metadata={
            "importance": importance,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def test_contextual_reranker_favors_current_scene_without_replacing_base_retrieval():
    reranker = ContextualReservoirReranker()
    generic = _hit("generic", "We discussed a grocery list.", 0.72)
    project = _hit("project", "We revised the Unbeknownst Union Station scene.", 0.68, importance=0.8)
    ranked = reranker.rerank(
        [generic, project],
        context={
            "workspace": {
                "live_scene": {
                    "project": "Unbeknownst",
                    "activity": "Union Station storyboard",
                }
            }
        },
    )
    assert ranked[0].record_id == "project"
    # Reranking must not mutate authority-bearing selector metadata.
    assert "retrieval" not in ranked[0].metadata
    assert reranker.last_diagnostics["project"]["scene_relevance"] > 0
