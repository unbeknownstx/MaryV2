from __future__ import annotations

from pathlib import Path

import pytest

from mary.distributed.qdrant_knowledge import (
    EmbeddingSpaceMismatch,
    QdrantKnowledgeBackend,
)
from mary.knowledge import KnowledgeFabric


class _Identity:
    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint


class _Embeddings:
    def __init__(self, fingerprint: str, vector: list[float]) -> None:
        self.fingerprint = fingerprint
        self.vector = vector

    def embedding_identity(self, *, refresh: bool = False):
        return _Identity(self.fingerprint)

    def embed(self, text: str):
        return list(self.vector)


def _pack(tmp_path: Path, *, identity: str = "a" * 64):
    fabric = KnowledgeFabric(tmp_path / "fabric.json")
    return fabric.register(
        pack_id="semantic",
        title="Semantic manuals",
        kind="qdrant",
        location="http://127.0.0.1:6333",
        query_mode="vector",
        collection="manuals",
        topics=("mary", "manual"),
        metadata={
            "qdrant_collection": "mary_manuals",
            "embedding_model": "nomic-embed-text",
            "embedding_space_identity": identity,
            "embedding_dimensions": 3,
        },
    )


def test_qdrant_query_requires_exact_embedding_space_and_returns_citations(
    tmp_path: Path,
) -> None:
    pack = _pack(tmp_path)
    calls = []

    def request(url, payload):
        calls.append((url, payload))
        return {
            "result": {
                "points": [{
                    "id": 7,
                    "score": 0.91,
                    "payload": {
                        "title": "Local Manual",
                        "text": "Mary retrieves this as evidence, never memory truth.",
                        "locator": "manual.md#chunk-2",
                        "content_hash": "f" * 64,
                        "source_date": "2026-09-18",
                    },
                }]
            }
        }

    backend = QdrantKnowledgeBackend(
        embedding_client_factory=lambda model: _Embeddings("a" * 64, [0.1, 0.2, 0.3]),
        request_json=request,
    )
    hits = backend.search(pack, "Mary evidence", limit=4)

    assert len(hits) == 1
    assert hits[0].citation_id == "knowledge:semantic:" + ("f" * 16)
    assert hits[0].collection == "manuals"
    assert calls[0][0].endswith("/collections/mary_manuals/points/query")
    assert calls[0][1]["query"] == [0.1, 0.2, 0.3]
    assert calls[0][1]["with_payload"] is True
    assert calls[0][1]["with_vector"] is False


def test_qdrant_query_fails_before_transport_on_embedding_identity_mismatch(
    tmp_path: Path,
) -> None:
    pack = _pack(tmp_path, identity="a" * 64)
    called = False

    def request(url, payload):
        nonlocal called
        called = True
        return {}

    backend = QdrantKnowledgeBackend(
        embedding_client_factory=lambda model: _Embeddings("b" * 64, [0.1, 0.2, 0.3]),
        request_json=request,
    )
    with pytest.raises(EmbeddingSpaceMismatch):
        backend.search(pack, "unsafe mismatch")
    assert called is False


def test_qdrant_pack_registration_is_local_private_and_metadata_strict(
    tmp_path: Path,
) -> None:
    fabric = KnowledgeFabric(tmp_path / "fabric.json")
    with pytest.raises(ValueError, match="local/private"):
        fabric.register(
            pack_id="remote",
            title="Remote vector DB",
            kind="qdrant",
            location="https://example.com",
            query_mode="vector",
            metadata={
                "qdrant_collection": "mary",
                "embedding_model": "nomic-embed-text",
                "embedding_space_identity": "a" * 64,
                "embedding_dimensions": 768,
            },
        )

    with pytest.raises(ValueError, match="embedding_space_identity"):
        fabric.register(
            pack_id="missing-identity",
            title="Broken local vector DB",
            kind="qdrant",
            location="http://127.0.0.1:6333",
            query_mode="vector",
            metadata={
                "qdrant_collection": "mary",
                "embedding_model": "nomic-embed-text",
                "embedding_dimensions": 768,
            },
        )
