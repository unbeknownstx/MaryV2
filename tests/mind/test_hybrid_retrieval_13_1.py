from mary.mind.hybrid_retrieval import HybridReservoirRetriever
from mary.mind.reservoir import CognitiveReservoir, ReservoirRecord
from mary.mind.vector_index import SemanticVectorIndex


class FakeEmbeddings:
    model = "fake-embed"
    def __init__(self):
        self.calls = 0
    def model_available(self):
        return True
    def available(self):
        return True
    def embed(self, text):
        self.calls += 1
        text = text.lower()
        if "rain" in text or "storm" in text:
            return [1.0, 0.0, 0.0]
        if "pizza" in text:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]


def record(rid, content):
    return ReservoirRecord(
        record_id=rid, kind="memory", subject="creator", predicate="note",
        content=content, source="memory", authority="canonical_memory", confidence=0.95,
    )


def test_auto_mode_does_not_call_embeddings_before_index_exists(monkeypatch):
    monkeypatch.setenv("MARY_VECTOR_RETRIEVAL", "auto")
    reservoir = CognitiveReservoir.in_memory()
    reservoir.rebuild([record("one", "rainy creative nights")])
    fake = FakeEmbeddings()
    retriever = HybridReservoirRetriever(reservoir, vector_index=SemanticVectorIndex.in_memory(), embedding_client=fake)
    hits = retriever.search("rainy", limit=3)
    assert hits
    assert fake.calls == 0
    retriever.close(); reservoir.close()


def test_vector_rebuild_enables_semantic_candidate_recall(monkeypatch):
    monkeypatch.setenv("MARY_VECTOR_RETRIEVAL", "auto")
    records = [record("rain", "creative work during rainy nights"), record("pizza", "likes pizza")]
    reservoir = CognitiveReservoir.in_memory()
    reservoir.rebuild(records)
    fake = FakeEmbeddings()
    retriever = HybridReservoirRetriever(reservoir, vector_index=SemanticVectorIndex.in_memory(), embedding_client=fake)
    result = retriever.rebuild_vectors(records)
    assert result["ok"] and result["indexed"] == 2
    hits = retriever.search("stormy weather projects", limit=2)
    assert hits[0].record_id == "rain"
    assert hits[0].authority == "canonical_memory"
    assert hits[0].metadata["retrieval"]["vector_score"] > 0
    retriever.close(); reservoir.close()
