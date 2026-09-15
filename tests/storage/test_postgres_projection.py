from __future__ import annotations

from dataclasses import dataclass

import pytest

from mary.storage.postgres_projection import (
    PostgresProjection,
    PostgresProjectionConfig,
    ProjectionRecord,
    _safe_endpoint,
    _vector_literal,
    memory_projection_records,
)


@dataclass
class _Episode:
    id: str
    content: str
    importance: float = 0.75
    source: str = "interaction"
    event_type: str = "general"
    participants: tuple[str, ...] = ()
    emotional_context: dict | None = None
    metadata: dict | None = None
    created_at: str = "2026-09-12T00:00:00Z"


class _Episodic:
    def all(self):
        return [
            _Episode(
                id="ep-1",
                content="We tested Mary on the Mac.",
                metadata={"surface": "mac"},
            )
        ]


class _Semantic:
    def all(self):
        return [
            {
                "id": "sem-1",
                "subject": "Mary",
                "predicate": "uses",
                "value": "one canonical Core",
                "confidence": 0.95,
                "source": "approved_fact",
            }
        ]


class _Memory:
    episodic = _Episodic()
    semantic = _Semantic()


def test_config_requires_explicit_enable_even_when_database_url_exists(monkeypatch):
    monkeypatch.delenv("MARY_POSTGRES_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@example.com/mary")
    monkeypatch.delenv("MARY_POSTGRES_ENABLED", raising=False)

    config = PostgresProjectionConfig.from_environment()

    assert config.dsn is not None
    assert config.enabled is False
    assert config.safe_status()["configured"] is True


def test_config_status_redacts_credentials(monkeypatch):
    monkeypatch.setenv(
        "MARY_POSTGRES_URL",
        "postgresql://mary:super-secret@db.example.com:5432/maryv2?sslmode=require",
    )
    monkeypatch.setenv("MARY_POSTGRES_ENABLED", "1")

    status = PostgresProjectionConfig.from_environment().safe_status()
    rendered = repr(status)

    assert status["enabled"] is True
    assert status["endpoint"] == "postgresql://db.example.com:5432/maryv2"
    assert "super-secret" not in rendered
    assert "mary@" not in rendered


def test_safe_endpoint_handles_unparseable_or_missing_values():
    assert _safe_endpoint(None) is None
    assert _safe_endpoint("") is None
    assert _safe_endpoint("not-a-url") == "configured"


def test_projection_records_include_only_durable_memory_types():
    records = memory_projection_records(_Memory())

    assert [record.record_type for record in records] == ["episodic", "semantic"]
    assert records[0].record_id == "ep-1"
    assert records[1].record_id == "sem-1"
    assert "one canonical Core" in records[1].content
    assert all(record.content_hash for record in records)


def test_projection_record_rejects_unknown_authority_type():
    with pytest.raises(ValueError):
        ProjectionRecord(
            record_id="x",
            record_type="working",
            content="ephemeral",
            confidence=1.0,
            source=None,
            metadata={},
        )


def test_vector_literal_is_bounded_and_finite():
    assert _vector_literal([0.5, -1.25, 3]) == "[0.5,-1.25,3]"
    with pytest.raises(ValueError):
        _vector_literal([])
    with pytest.raises(ValueError):
        _vector_literal([float("nan")])
    with pytest.raises(ValueError):
        _vector_literal([0.0] * 16_385)


def test_disabled_projection_has_no_startup_dependency(monkeypatch):
    monkeypatch.delenv("MARY_POSTGRES_ENABLED", raising=False)
    monkeypatch.delenv("MARY_POSTGRES_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    projection = PostgresProjection()

    assert projection.status()["enabled"] is False
    assert projection.ensure_schema()["reason"] == "disabled"
    assert projection.sync_memory(_Memory())["reason"] == "disabled"
    assert projection.lexical_search("anything") == []


def test_retrieval_is_separately_opt_in(monkeypatch):
    monkeypatch.setenv("MARY_POSTGRES_URL", "postgresql://localhost/mary")
    monkeypatch.setenv("MARY_POSTGRES_ENABLED", "1")
    monkeypatch.delenv("MARY_POSTGRES_RETRIEVAL", raising=False)

    projection = PostgresProjection()

    assert projection.config.enabled is True
    assert projection.config.retrieval_enabled is False
    # Must return before attempting a database connection.
    assert projection.lexical_search("Mary") == []
