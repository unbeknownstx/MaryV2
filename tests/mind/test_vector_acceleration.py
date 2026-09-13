from __future__ import annotations

import importlib.util

import pytest

from mary.mind.vector_index import SemanticVectorIndex


MODEL = "fake-embed"
IDENTITY = "space:test-v1"


def _seed(index: SemanticVectorIndex) -> None:
    index.register_identity(model=MODEL, embedding_identity=IDENTITY)
    rows = {
        "north": [1.0, 0.0, 0.0, 0.0],
        "east": [0.0, 1.0, 0.0, 0.0],
        "near_north": [0.95, 0.05, 0.0, 0.0],
    }
    for record_id, vector in rows.items():
        assert index.upsert(
            record_id=record_id,
            model=MODEL,
            embedding_identity=IDENTITY,
            vector=vector,
            content=f"content:{record_id}",
        )


def test_python_backend_remains_reference_path() -> None:
    index = SemanticVectorIndex.in_memory(backend="python")
    _seed(index)
    hits = index.search(
        [1.0, 0.0, 0.0, 0.0],
        model=MODEL,
        embedding_identity=IDENTITY,
        limit=3,
    )
    assert [hit.record_id for hit in hits[:2]] == ["north", "near_north"]
    assert index.status(model=MODEL, embedding_identity=IDENTITY)["backend"]["active"] == "python"
    index.close()


def test_auto_backend_is_safe_when_optional_extension_is_unavailable() -> None:
    index = SemanticVectorIndex.in_memory(backend="auto")
    _seed(index)
    hits = index.search(
        [1.0, 0.0, 0.0, 0.0],
        model=MODEL,
        embedding_identity=IDENTITY,
        limit=3,
    )
    assert hits and hits[0].record_id == "north"
    status = index.status(model=MODEL, embedding_identity=IDENTITY)
    assert status["backend"]["active"] in {"python", "sqlite_vec"}
    assert status["backend"]["fallback"] == "python_cosine"
    index.close()


def test_embedding_identity_mismatch_fails_closed_before_backend_search() -> None:
    index = SemanticVectorIndex.in_memory(backend="auto")
    _seed(index)
    assert index.search(
        [1.0, 0.0, 0.0, 0.0],
        model=MODEL,
        embedding_identity="space:different",
        limit=3,
    ) == []
    index.close()


def test_registering_new_identity_invalidates_only_derived_vectors() -> None:
    index = SemanticVectorIndex.in_memory(backend="python")
    _seed(index)
    result = index.register_identity(model=MODEL, embedding_identity="space:test-v2")
    assert result["changed"] is True
    assert result["invalidated"] == 3
    assert index.count(model=MODEL) == 0
    index.close()


@pytest.mark.skipif(importlib.util.find_spec("sqlite_vec") is None, reason="optional sqlite-vec package not installed")
def test_sqlite_vec_native_path_matches_python_reference_ordering() -> None:
    python_index = SemanticVectorIndex.in_memory(backend="python")
    native_index = SemanticVectorIndex.in_memory(backend="sqlite_vec")
    _seed(python_index)
    _seed(native_index)

    query = [1.0, 0.0, 0.0, 0.0]
    expected = python_index.search(query, model=MODEL, embedding_identity=IDENTITY, limit=3)
    actual = native_index.search(query, model=MODEL, embedding_identity=IDENTITY, limit=3)

    assert native_index.status(model=MODEL, embedding_identity=IDENTITY)["backend"]["active"] == "sqlite_vec"
    assert [hit.record_id for hit in actual] == [hit.record_id for hit in expected]
    assert [hit.score for hit in actual] == pytest.approx([hit.score for hit in expected], abs=1e-5)

    python_index.close()
    native_index.close()
