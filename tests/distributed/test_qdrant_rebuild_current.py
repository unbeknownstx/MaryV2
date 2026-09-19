from __future__ import annotations

from pathlib import Path

from mary.distributed.qdrant_knowledge import QdrantKnowledgeIndexer
from mary.knowledge import KnowledgeFabric


class _Identity:
    fingerprint = "a" * 64


class _EmbeddingClient:
    def embedding_identity(self, *, refresh=False):
        return _Identity()

    def embed(self, text):
        length = float(len(str(text)) % 17) / 17.0
        return [length, 0.25, 0.75]


def _fabric(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "alpha.md").write_text(
        "Alpha semantic source for Mary.",
        encoding="utf-8",
    )
    (docs / "beta.md").write_text(
        "Beta semantic source for Mary.",
        encoding="utf-8",
    )
    fabric = KnowledgeFabric(
        tmp_path / "fabric.json",
        index_path=tmp_path / "fabric.sqlite3",
    )
    source = fabric.register(
        pack_id="source",
        title="Source documents",
        kind="local_files",
        location=str(docs),
        query_mode="fts",
        collection="manuals",
    )
    fabric.index_local_pack(source.id)
    # KnowledgePack values are immutable registry snapshots. Refresh after
    # indexing so downstream vector-build assertions compare against the
    # durable source fingerprint that was actually written.
    source = fabric.get(source.id)
    assert source.content_fingerprint
    vector = fabric.register(
        pack_id="vector",
        title="Semantic index",
        kind="qdrant",
        location="http://127.0.0.1:6333",
        query_mode="vector",
        collection="manuals",
        metadata={
            "qdrant_collection": "mary_manuals",
            "embedding_model": "nomic-embed-text",
            "embedding_space_identity": "a" * 64,
            "embedding_dimensions": 3,
            "source_pack_id": "source",
        },
    )
    return fabric, source, vector


def test_qdrant_rebuild_upserts_before_stale_delete_and_records_build(
    tmp_path: Path,
) -> None:
    fabric, source, vector = _fabric(tmp_path)
    calls = []

    def write(method, url, payload):
        calls.append((method, url, payload))
        return {"status": "ok", "result": {"status": "completed"}}

    indexer = QdrantKnowledgeIndexer(
        embedding_client_factory=lambda model: _EmbeddingClient(),
        write_json=write,
    )
    result = indexer.rebuild(vector, fabric, batch_size=1)

    assert result["ok"] is True
    assert result["vectors_indexed"] == 2
    assert result["stale_generation_deleted"] is True
    methods = [item[0] for item in calls]
    assert methods == ["PUT", "PUT", "POST"]
    assert all("/points?wait=true" in calls[i][1] for i in (0, 1))
    assert "/points/delete?wait=true" in calls[-1][1]
    first_point = calls[0][2]["points"][0]
    assert first_point["payload"]["mary_vector_pack_id"] == "vector"
    assert first_point["payload"]["mary_source_pack_id"] == "source"
    assert first_point["payload"]["embedding_space_identity"] == "a" * 64

    updated = fabric.get("vector")
    build = updated.metadata["vector_build"]
    assert build["source_pack_id"] == "source"
    assert build["source_fingerprint"] == fabric.derivative_source_fingerprint(
        source.id
    )
    assert build["source_fingerprint"] != source.content_fingerprint
    assert build["vectors"] == 2


def test_qdrant_create_collection_uses_configured_dimensions(tmp_path: Path) -> None:
    fabric, _source, vector = _fabric(tmp_path)
    calls = []

    def write(method, url, payload):
        calls.append((method, url, payload))
        return {"status": "ok", "result": True}

    result = QdrantKnowledgeIndexer(
        embedding_client_factory=lambda model: _EmbeddingClient(),
        write_json=write,
    ).create_collection(vector)

    assert result["ok"] is True
    assert calls == [(
        "PUT",
        "http://127.0.0.1:6333/collections/mary_manuals",
        {
            "vectors": {"size": 3, "distance": "Cosine"},
            "on_disk_payload": True,
        },
    )]


def test_qdrant_reconciliation_detects_stale_or_mismatched_vector_accounting(tmp_path: Path):
    fabric, source_pack, vector_pack = _fabric(tmp_path)
    embed = _EmbeddingClient()

    indexer = QdrantKnowledgeIndexer(
        embedding_client_factory=lambda _model: embed,
        write_json=lambda _method, _url, _payload: {"status": "ok"},
        request_json=lambda _url, _payload: {"result": {"count": 0}},
    )
    built = indexer.rebuild(
        vector_pack,
        fabric,
        source_pack_id=source_pack.id,
        batch_size=8,
    )
    assert built["ok"] is True

    refreshed_pack = fabric.get(vector_pack.id)
    expected = len(fabric.indexed_chunks(source_pack.id))
    responses = iter([
        {"result": {"count": expected + 2}},
        {"result": {"count": expected}},
    ])
    checker = QdrantKnowledgeIndexer(
        embedding_client_factory=lambda _model: embed,
        request_json=lambda _url, _payload: next(responses),
    )
    report = checker.reconcile(
        refreshed_pack,
        fabric,
        source_pack_id=source_pack.id,
    )
    assert report["ok"] is False
    assert report["state"] == "stale_or_mismatched_vectors"
    assert report["stale_or_other_generation_vectors"] == 2
    assert report["mutation_performed"] is False


def test_qdrant_reconciliation_reports_healthy_exact_generation(tmp_path: Path):
    fabric, source_pack, vector_pack = _fabric(tmp_path)
    embed = _EmbeddingClient()

    indexer = QdrantKnowledgeIndexer(
        embedding_client_factory=lambda _model: embed,
        write_json=lambda _method, _url, _payload: {"status": "ok"},
        request_json=lambda _url, _payload: {"result": {"count": 0}},
    )
    assert indexer.rebuild(
        vector_pack,
        fabric,
        source_pack_id=source_pack.id,
    )["ok"] is True

    refreshed_pack = fabric.get(vector_pack.id)
    expected = len(fabric.indexed_chunks(source_pack.id))
    checker = QdrantKnowledgeIndexer(
        embedding_client_factory=lambda _model: embed,
        request_json=lambda _url, _payload: {"result": {"count": expected}},
    )
    report = checker.reconcile(
        refreshed_pack,
        fabric,
        source_pack_id=source_pack.id,
    )
    assert report["ok"] is True
    assert report["state"] == "healthy"
    assert report["actual_vectors"] == expected
    assert report["repair"] == "none"



def test_qdrant_rebuild_refuses_stale_local_ingestion_pipeline(tmp_path: Path):
    import json
    import pytest

    fabric, source, vector = _fabric(tmp_path)
    manifest_path = fabric._source_manifest_path(source.id)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["pipeline_fingerprint"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    indexer = QdrantKnowledgeIndexer(
        embedding_client_factory=lambda _model: _EmbeddingClient(),
        write_json=lambda _method, _url, _payload: {"status": "ok"},
    )
    with pytest.raises(RuntimeError, match="current indexed ingestion pipeline"):
        indexer.rebuild(vector, fabric, source_pack_id=source.id)

    assert fabric.derivative_source_fingerprint(source.id) == ""
