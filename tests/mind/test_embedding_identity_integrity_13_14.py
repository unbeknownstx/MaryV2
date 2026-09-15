from __future__ import annotations

import sqlite3

from mary.mind.embeddings import EmbeddingIdentity
from mary.mind.hybrid_retrieval import HybridReservoirRetriever
from mary.mind.reservoir import CognitiveReservoir, ReservoirRecord
from mary.mind.vector_index import SemanticVectorIndex


def record(rid: str, content: str) -> ReservoirRecord:
    return ReservoirRecord(
        record_id=rid,
        kind="memory",
        subject="creator",
        predicate="note",
        content=content,
        source="memory",
        authority="canonical_memory",
        confidence=0.95,
    )


def test_embedding_identity_fingerprint_changes_with_digest_or_runtime() -> None:
    a = EmbeddingIdentity(
        provider="ollama",
        model="nomic-embed-text",
        model_digest="abc",
        backend_version="1.0",
    )
    b = EmbeddingIdentity(
        provider="ollama",
        model="nomic-embed-text",
        model_digest="def",
        backend_version="1.0",
    )
    c = EmbeddingIdentity(
        provider="ollama",
        model="nomic-embed-text",
        model_digest="abc",
        backend_version="1.1",
    )

    assert a.fingerprint != b.fingerprint
    assert a.fingerprint != c.fingerprint
    assert a.fingerprint == EmbeddingIdentity(
        provider="ollama",
        model="nomic-embed-text",
        model_digest="abc",
        backend_version="1.0",
    ).fingerprint


def test_vector_search_never_crosses_embedding_identity() -> None:
    index = SemanticVectorIndex.in_memory()
    index.upsert(
        record_id="r1",
        model="m",
        embedding_identity="space-a",
        vector=[1.0, 0.0],
        content="alpha",
    )

    assert index.search([1.0, 0.0], model="m", embedding_identity="space-a")
    assert index.search([1.0, 0.0], model="m", embedding_identity="space-b") == []


def test_register_identity_invalidates_only_incompatible_derived_rows() -> None:
    index = SemanticVectorIndex.in_memory()
    index.upsert(
        record_id="r1",
        model="m",
        embedding_identity="old-space",
        vector=[1.0, 0.0],
        content="alpha",
    )

    change = index.register_identity(model="m", embedding_identity="new-space")

    assert change["changed"] is True
    assert change["invalidated"] == 1
    assert index.count(model="m") == 0
    assert index.registered_identity("m") == "new-space"


class FakeEmbeddings:
    model = "fake-embed"

    def __init__(self, identity: str = "space-a") -> None:
        self.identity = identity

    def model_available(self) -> bool:
        return True

    def embedding_identity(self, refresh: bool = False):
        del refresh
        return {
            "fingerprint": self.identity,
            "provider": "fake",
            "model": self.model,
        }

    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0] if "alpha" in str(text).casefold() else [0.0, 1.0]


def test_retriever_fails_closed_after_identity_change_then_rebuilds(monkeypatch) -> None:
    monkeypatch.setenv("MARY_VECTOR_RETRIEVAL", "on")
    reservoir = CognitiveReservoir.in_memory()
    source_record = record("r1", "alpha fact")
    reservoir.rebuild([source_record])
    index = SemanticVectorIndex.in_memory()
    embeddings = FakeEmbeddings("space-a")
    retriever = HybridReservoirRetriever(
        reservoir,
        vector_index=index,
        embedding_client=embeddings,
    )

    first = retriever.rebuild_vectors([source_record])
    assert first["ok"] is True
    assert first["vectors"] == 1
    assert index.registered_identity("fake-embed") == "space-a"

    embeddings.identity = "space-b"
    retriever.search("alpha", limit=5)
    status = retriever.status()
    assert status["embedding_identity_mismatch"] is True
    assert status["last_query_used_vectors"] is False

    rebuilt = retriever.rebuild_vectors([source_record])
    assert rebuilt["ok"] is True
    assert rebuilt["invalidated_incompatible"] == 1
    assert rebuilt["vectors"] == 1
    assert index.registered_identity("fake-embed") == "space-b"

    retriever.search("alpha", limit=5)
    assert retriever.status()["last_query_used_vectors"] is True

    retriever.close()
    reservoir.close()


def test_schema_v1_database_migrates_and_legacy_rows_are_invalidated(tmp_path) -> None:
    db = tmp_path / "vectors.sqlite3"
    connection = sqlite3.connect(db)
    connection.executescript(
        """
        CREATE TABLE vector_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE reservoir_vectors (
            record_id TEXT NOT NULL,
            model TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            vector_json TEXT NOT NULL,
            vector_norm REAL NOT NULL,
            content_hash TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY(record_id, model)
        );
        INSERT INTO reservoir_vectors(
            record_id,model,dimensions,vector_json,vector_norm,content_hash,updated_at
        ) VALUES('r1','m',2,'[1.0,0.0]',1.0,'x',1.0);
        """
    )
    connection.commit()
    connection.close()

    index = SemanticVectorIndex(db)
    assert index.count(model="m") == 1

    result = index.register_identity(model="m", embedding_identity="space-new")

    assert result["invalidated"] == 1
    assert index.count(model="m") == 0
    assert index.status(model="m")["schema_version"] == 2
