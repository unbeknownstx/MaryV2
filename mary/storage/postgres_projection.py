"""Optional PostgreSQL + pgvector projection for MaryV2.

This module is intentionally *not* a canonical state owner.  Mary's memory,
relationship, identity, developed self, agency, and permission systems remain
owned by the canonical Core.  PostgreSQL stores a rebuildable durable
projection of approved memory records and may return lexical/vector retrieval
candidates.

The dependency on psycopg is lazy and optional.  Importing MaryV2 never requires
PostgreSQL to be installed or reachable.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit


_TRUE = {"1", "true", "yes", "on", "enabled"}
_RECORD_TYPES = {"episodic", "semantic"}
_MAX_VECTOR_DIMENSIONS = 16_384


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in _TRUE


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        value = int(default)
    return max(minimum, min(maximum, value))


def _content_hash(content: str) -> str:
    return hashlib.sha256(str(content).encode("utf-8")).hexdigest()


def _safe_endpoint(dsn: str | None) -> str | None:
    """Return a display-safe endpoint with credentials/query fragments removed."""

    value = str(dsn or "").strip()
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except Exception:
        return "configured"
    if not parsed.scheme:
        return "configured"
    host = parsed.hostname or "configured"
    port = f":{parsed.port}" if parsed.port else ""
    database = (parsed.path or "").strip("/")
    suffix = f"/{database}" if database else ""
    return f"{parsed.scheme}://{host}{port}{suffix}"


def _json_safe(value: Any) -> Any:
    """Bound arbitrary metadata to JSON-compatible values without secrets logic."""

    try:
        encoded = json.dumps(value, ensure_ascii=False, default=str)
        return json.loads(encoded)
    except Exception:
        return str(value)


def _vector_literal(vector: Sequence[float]) -> str:
    values = list(vector)
    if not values or len(values) > _MAX_VECTOR_DIMENSIONS:
        raise ValueError("vector dimension is outside the supported bounds")
    normalized: list[str] = []
    for item in values:
        number = float(item)
        if not math.isfinite(number):
            raise ValueError("vector contains a non-finite value")
        normalized.append(format(number, ".12g"))
    return "[" + ",".join(normalized) + "]"


@dataclass(frozen=True)
class PostgresProjectionConfig:
    enabled: bool
    dsn: str | None
    retrieval_enabled: bool = False
    auto_sync: bool = False
    connect_timeout_seconds: int = 5
    statement_timeout_ms: int = 4_000
    max_sync_records: int = 10_000

    @classmethod
    def from_environment(cls) -> "PostgresProjectionConfig":
        dsn = (
            os.getenv("MARY_POSTGRES_URL")
            or os.getenv("DATABASE_URL")
            or ""
        ).strip() or None
        return cls(
            # Explicit opt-in is required even when a platform injects
            # DATABASE_URL automatically.
            enabled=bool(dsn) and _env_bool("MARY_POSTGRES_ENABLED", False),
            dsn=dsn,
            retrieval_enabled=_env_bool("MARY_POSTGRES_RETRIEVAL", False),
            auto_sync=_env_bool("MARY_POSTGRES_AUTO_SYNC", False),
            connect_timeout_seconds=_bounded_int(
                "MARY_POSTGRES_CONNECT_TIMEOUT", 5, 1, 30
            ),
            statement_timeout_ms=_bounded_int(
                "MARY_POSTGRES_STATEMENT_TIMEOUT_MS", 4_000, 250, 60_000
            ),
            max_sync_records=_bounded_int(
                "MARY_POSTGRES_MAX_SYNC_RECORDS", 10_000, 1, 100_000
            ),
        )

    def safe_status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "configured": bool(self.dsn),
            "endpoint": _safe_endpoint(self.dsn),
            "retrieval_enabled": self.retrieval_enabled,
            "auto_sync": self.auto_sync,
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "statement_timeout_ms": self.statement_timeout_ms,
            "max_sync_records": self.max_sync_records,
            "authority": "derived_projection_only",
        }


@dataclass(frozen=True)
class ProjectionRecord:
    record_id: str
    record_type: str
    content: str
    confidence: float
    source: str | None
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.record_type not in _RECORD_TYPES:
            raise ValueError(f"unsupported projection record type: {self.record_type}")
        if not str(self.record_id).strip():
            raise ValueError("projection record_id must not be empty")
        if not str(self.content).strip():
            raise ValueError("projection content must not be empty")

    @property
    def content_hash(self) -> str:
        return _content_hash(self.content)


def _episodic_record(item: Any) -> ProjectionRecord | None:
    if isinstance(item, Mapping):
        get = item.get
    else:
        get = lambda key, default=None: getattr(item, key, default)
    record_id = str(get("id") or get("memory_id") or "").strip()
    content = str(get("content") or "").strip()
    if not record_id or not content:
        return None
    importance = get("importance", 0.5)
    try:
        confidence = float(importance)
    except (TypeError, ValueError):
        confidence = 0.5
    metadata = dict(get("metadata", {}) or {})
    for key in ("event_type", "participants", "emotional_context", "created_at"):
        value = get(key)
        if value is not None:
            metadata.setdefault(key, value)
    return ProjectionRecord(
        record_id=record_id[:240],
        record_type="episodic",
        content=content,
        confidence=max(0.0, min(1.0, confidence)),
        source=str(get("source") or "interaction")[:160],
        metadata=_json_safe(metadata),
    )


def _semantic_record(item: Any) -> ProjectionRecord | None:
    if not isinstance(item, Mapping):
        return None
    record_id = str(item.get("id") or "").strip()
    subject = item.get("subject")
    predicate = item.get("predicate")
    if not record_id or subject is None or predicate is None:
        return None
    value = item.get("value")
    content = f"{subject} {predicate} {value}".strip()
    try:
        confidence = float(item.get("confidence", 1.0))
    except (TypeError, ValueError):
        confidence = 1.0
    metadata = {
        "subject": subject,
        "predicate": predicate,
        "value": value,
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }
    return ProjectionRecord(
        record_id=record_id[:240],
        record_type="semantic",
        content=content,
        confidence=max(0.0, min(1.0, confidence)),
        source=(str(item.get("source"))[:160] if item.get("source") is not None else None),
        metadata=_json_safe(metadata),
    )


def memory_projection_records(memory: Any, *, limit: int | None = None) -> list[ProjectionRecord]:
    """Materialize canonical memory as bounded projection records.

    Working memory is intentionally excluded because it is ephemeral and should
    not become durable solely because a database connection exists.
    """

    records: list[ProjectionRecord] = []
    max_records = max(1, int(limit)) if limit is not None else None

    try:
        episodic = list(memory.episodic.all())
    except Exception:
        episodic = []
    for item in episodic:
        record = _episodic_record(item)
        if record is not None:
            records.append(record)
            if max_records is not None and len(records) >= max_records:
                return records

    try:
        semantic = list(memory.semantic.all())
    except Exception:
        semantic = []
    for item in semantic:
        record = _semantic_record(item)
        if record is not None:
            records.append(record)
            if max_records is not None and len(records) >= max_records:
                break
    return records


class PostgresProjection:
    """Optional write-through projection and lexical/vector candidate store."""

    SCHEMA_VERSION = 1

    def __init__(
        self,
        config: PostgresProjectionConfig | None = None,
        *,
        connection_factory: Any | None = None,
    ) -> None:
        self.config = config or PostgresProjectionConfig.from_environment()
        self._connection_factory = connection_factory
        self.last_error: str | None = None
        self.last_sync: dict[str, Any] = {}
        self.vector_available: bool | None = None

    def _connect(self):
        if not self.config.enabled or not self.config.dsn:
            raise RuntimeError("PostgreSQL projection is disabled")
        if self._connection_factory is not None:
            return self._connection_factory(self.config.dsn)
        try:
            import psycopg  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is not installed; install requirements-postgres.txt"
            ) from exc
        return psycopg.connect(
            self.config.dsn,
            connect_timeout=self.config.connect_timeout_seconds,
        )

    def _configure_session(self, cursor: Any) -> None:
        timeout = int(self.config.statement_timeout_ms)
        cursor.execute(f"SET LOCAL statement_timeout = {timeout}")

    def ensure_schema(self) -> dict[str, Any]:
        if not self.config.enabled:
            return {"ok": False, "reason": "disabled", "vector": False}
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    self._configure_session(cursor)
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS mary_projection_records (
                            record_id TEXT PRIMARY KEY,
                            record_type TEXT NOT NULL,
                            content TEXT NOT NULL,
                            confidence DOUBLE PRECISION NOT NULL,
                            source TEXT,
                            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                            content_hash TEXT NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            CHECK (record_type IN ('episodic', 'semantic'))
                        )
                        """
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS mary_projection_type_idx "
                        "ON mary_projection_records(record_type)"
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS mary_projection_fts_idx "
                        "ON mary_projection_records USING GIN "
                        "(to_tsvector('simple', content))"
                    )
                connection.commit()

                vector_available = False
                try:
                    with connection.cursor() as cursor:
                        self._configure_session(cursor)
                        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                        cursor.execute(
                            """
                            CREATE TABLE IF NOT EXISTS mary_projection_vectors (
                                record_id TEXT NOT NULL REFERENCES mary_projection_records(record_id)
                                    ON DELETE CASCADE,
                                model TEXT NOT NULL,
                                embedding_identity TEXT NOT NULL,
                                content_hash TEXT NOT NULL,
                                embedding VECTOR NOT NULL,
                                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                                PRIMARY KEY (record_id, model, embedding_identity)
                            )
                            """
                        )
                    connection.commit()
                    vector_available = True
                except Exception:
                    try:
                        connection.rollback()
                    except Exception:
                        pass
                    vector_available = False

            self.vector_available = vector_available
            self.last_error = None
            return {
                "ok": True,
                "schema_version": self.SCHEMA_VERSION,
                "vector": vector_available,
            }
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"[:500]
            return {"ok": False, "reason": self.last_error, "vector": False}

    def sync_memory(self, memory: Any) -> dict[str, Any]:
        if not self.config.enabled:
            result = {"ok": False, "reason": "disabled", "synced": 0}
            self.last_sync = result
            return result
        schema = self.ensure_schema()
        if not schema.get("ok"):
            result = {"ok": False, "reason": schema.get("reason"), "synced": 0}
            self.last_sync = result
            return result

        records = memory_projection_records(
            memory,
            limit=self.config.max_sync_records,
        )
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    self._configure_session(cursor)
                    for record in records:
                        cursor.execute(
                            """
                            INSERT INTO mary_projection_records
                                (record_id, record_type, content, confidence, source,
                                 metadata, content_hash, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, NOW())
                            ON CONFLICT (record_id) DO UPDATE SET
                                record_type = EXCLUDED.record_type,
                                content = EXCLUDED.content,
                                confidence = EXCLUDED.confidence,
                                source = EXCLUDED.source,
                                metadata = EXCLUDED.metadata,
                                content_hash = EXCLUDED.content_hash,
                                updated_at = NOW()
                            """,
                            (
                                record.record_id,
                                record.record_type,
                                record.content,
                                record.confidence,
                                record.source,
                                json.dumps(record.metadata, ensure_ascii=False, default=str),
                                record.content_hash,
                            ),
                        )
                connection.commit()
            result = {
                "ok": True,
                "synced": len(records),
                "vector": bool(schema.get("vector")),
                "authority": "derived_projection_only",
            }
            self.last_error = None
            self.last_sync = result
            return result
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"[:500]
            result = {"ok": False, "reason": self.last_error, "synced": 0}
            self.last_sync = result
            return result

    def list_records(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        if not self.config.enabled:
            return []
        bounded = max(1, min(int(limit), self.config.max_sync_records))
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    self._configure_session(cursor)
                    cursor.execute(
                        """
                        SELECT record_id, record_type, content, confidence, source,
                               metadata, content_hash
                        FROM mary_projection_records
                        ORDER BY updated_at DESC
                        LIMIT %s
                        """,
                        (bounded,),
                    )
                    rows = cursor.fetchall()
            return [
                {
                    "record_id": row[0],
                    "record_type": row[1],
                    "content": row[2],
                    "confidence": float(row[3]),
                    "source": row[4],
                    "metadata": row[5] if isinstance(row[5], Mapping) else {},
                    "content_hash": row[6],
                }
                for row in rows
            ]
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"[:500]
            return []

    def upsert_vector(
        self,
        *,
        record_id: str,
        vector: Sequence[float],
        model: str,
        embedding_identity: str,
        content_hash: str,
    ) -> bool:
        if not self.config.enabled:
            return False
        if self.vector_available is not True:
            schema = self.ensure_schema()
            if not schema.get("vector"):
                return False
        literal = _vector_literal(vector)
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    self._configure_session(cursor)
                    cursor.execute(
                        """
                        INSERT INTO mary_projection_vectors
                            (record_id, model, embedding_identity, content_hash,
                             embedding, updated_at)
                        VALUES (%s, %s, %s, %s, %s::vector, NOW())
                        ON CONFLICT (record_id, model, embedding_identity)
                        DO UPDATE SET
                            content_hash = EXCLUDED.content_hash,
                            embedding = EXCLUDED.embedding,
                            updated_at = NOW()
                        """,
                        (
                            str(record_id)[:240],
                            str(model)[:240],
                            str(embedding_identity)[:240],
                            str(content_hash)[:128],
                            literal,
                        ),
                    )
                connection.commit()
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"[:500]
            return False

    def lexical_search(self, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        if not self.config.enabled or not self.config.retrieval_enabled:
            return []
        text = " ".join(str(query or "").split())[:2000]
        if not text:
            return []
        bounded = max(1, min(int(limit), 50))
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    self._configure_session(cursor)
                    cursor.execute(
                        """
                        SELECT record_id, record_type, content, confidence, source,
                               metadata,
                               ts_rank_cd(
                                   to_tsvector('simple', content),
                                   plainto_tsquery('simple', %s)
                               ) AS score
                        FROM mary_projection_records
                        WHERE to_tsvector('simple', content)
                              @@ plainto_tsquery('simple', %s)
                        ORDER BY score DESC, confidence DESC
                        LIMIT %s
                        """,
                        (text, text, bounded),
                    )
                    rows = cursor.fetchall()
            return [
                {
                    "record_id": row[0],
                    "record_type": row[1],
                    "content": row[2],
                    "confidence": float(row[3]),
                    "source": row[4],
                    "metadata": row[5] if isinstance(row[5], Mapping) else {},
                    "score": float(row[6] or 0.0),
                    "retrieval": "postgres_fts",
                }
                for row in rows
            ]
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"[:500]
            return []

    def semantic_search(
        self,
        query_vector: Sequence[float],
        *,
        model: str,
        embedding_identity: str,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        if not self.config.enabled or not self.config.retrieval_enabled:
            return []
        if self.vector_available is not True:
            schema = self.ensure_schema()
            if not schema.get("vector"):
                return []
        literal = _vector_literal(query_vector)
        bounded = max(1, min(int(limit), 50))
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    self._configure_session(cursor)
                    cursor.execute(
                        """
                        SELECT r.record_id, r.record_type, r.content, r.confidence,
                               r.source, r.metadata,
                               1 - (v.embedding <=> %s::vector) AS score
                        FROM mary_projection_vectors v
                        JOIN mary_projection_records r USING (record_id)
                        WHERE v.model = %s
                          AND v.embedding_identity = %s
                          AND v.content_hash = r.content_hash
                        ORDER BY v.embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (
                            literal,
                            str(model)[:240],
                            str(embedding_identity)[:240],
                            literal,
                            bounded,
                        ),
                    )
                    rows = cursor.fetchall()
            return [
                {
                    "record_id": row[0],
                    "record_type": row[1],
                    "content": row[2],
                    "confidence": float(row[3]),
                    "source": row[4],
                    "metadata": row[5] if isinstance(row[5], Mapping) else {},
                    "score": max(-1.0, min(1.0, float(row[6] or 0.0))),
                    "retrieval": "pgvector_cosine",
                }
                for row in rows
            ]
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"[:500]
            return []

    def probe(self) -> dict[str, Any]:
        if not self.config.enabled:
            return {**self.status(), "reachable": False, "reason": "disabled"}
        schema = self.ensure_schema()
        return {
            **self.status(),
            "reachable": bool(schema.get("ok")),
            "vector_available": bool(schema.get("vector")),
        }

    def status(self) -> dict[str, Any]:
        return {
            **self.config.safe_status(),
            "schema_version": self.SCHEMA_VERSION,
            "vector_available": self.vector_available,
            "last_sync": dict(self.last_sync),
            "last_error": self.last_error,
            "policy": (
                "PostgreSQL/pgvector stores a downstream projection and retrieval "
                "candidates only; canonical Mary state remains authoritative."
            ),
        }
