"""Optional semantic vector index for Mary's rebuildable cognitive reservoir.

The index is derived cache state. It never owns memory or decides what is true.
Embedding identity is stored beside every vector so vectors from incompatible
model/runtime spaces are never compared silently.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from threading import RLock
from time import time
from typing import Any, Iterable


@dataclass(frozen=True)
class VectorHit:
    record_id: str
    score: float
    model: str
    content_hash: str
    embedding_identity: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "score": round(float(self.score), 5),
            "model": self.model,
            "content_hash": self.content_hash,
            "embedding_identity": self.embedding_identity,
        }


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(str(text or "").split()).encode("utf-8")).hexdigest()


def _norm(vector: Iterable[float]) -> float:
    return math.sqrt(sum(float(value) * float(value) for value in vector))


def cosine_similarity(a: list[float], b: list[float], *, b_norm: float | None = None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    an = _norm(a)
    bn = float(b_norm) if b_norm is not None else _norm(b)
    if an <= 0.0 or bn <= 0.0:
        return 0.0
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    return max(-1.0, min(1.0, dot / (an * bn)))


class SemanticVectorIndex:
    SCHEMA_VERSION = 2

    def __init__(self, path: str | Path | None = None, *, max_scan: int = 5000) -> None:
        self.path = Path(path).expanduser().resolve() if path else None
        self.max_scan = max(100, min(100_000, int(max_scan)))
        self._lock = RLock()
        self._connection = self._connect()
        self._initialize()

    @classmethod
    def in_memory(cls) -> "SemanticVectorIndex":
        return cls(None)

    def _connect(self) -> sqlite3.Connection:
        if self.path is None:
            connection = sqlite3.connect(":memory:", timeout=2.0, check_same_thread=False)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(str(self.path), timeout=2.0, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _initialize(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS vector_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reservoir_vectors (
                record_id TEXT NOT NULL,
                model TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                vector_json TEXT NOT NULL,
                vector_norm REAL NOT NULL,
                content_hash TEXT NOT NULL,
                updated_at REAL NOT NULL,
                embedding_identity TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(record_id, model)
            );
            """
        )
        columns = {str(row[1]) for row in self._connection.execute("PRAGMA table_info(reservoir_vectors)").fetchall()}
        if "embedding_identity" not in columns:
            self._connection.execute(
                "ALTER TABLE reservoir_vectors ADD COLUMN embedding_identity TEXT NOT NULL DEFAULT ''"
            )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_reservoir_vectors_model ON reservoir_vectors(model)"
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_reservoir_vectors_space ON reservoir_vectors(model, embedding_identity)"
        )
        self._connection.execute(
            "INSERT OR REPLACE INTO vector_meta(key,value) VALUES('schema_version',?)",
            (str(self.SCHEMA_VERSION),),
        )
        self._connection.commit()

    @staticmethod
    def _identity_meta_key(model: str) -> str:
        return f"embedding_identity:{str(model)}"

    def _meta_get(self, key: str) -> str | None:
        row = self._connection.execute("SELECT value FROM vector_meta WHERE key=?", (str(key),)).fetchone()
        return str(row[0]) if row is not None else None

    def _meta_set(self, key: str, value: str) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO vector_meta(key,value) VALUES(?,?)",
            (str(key), str(value)),
        )

    def registered_identity(self, model: str) -> str | None:
        with self._lock:
            value = self._meta_get(self._identity_meta_key(model))
            return value or None

    def register_identity(self, *, model: str, embedding_identity: str) -> dict[str, Any]:
        """Register the current embedding space and invalidate incompatible rows.

        This only deletes rebuildable vector-cache rows. Canonical reservoir or
        memory records are never touched.
        """
        model_value = str(model)
        identity = str(embedding_identity or "").strip()
        if not identity:
            raise ValueError("embedding_identity cannot be empty")
        with self._lock, self._connection:
            previous = self._meta_get(self._identity_meta_key(model_value))
            changed = previous != identity
            invalidated = 0
            if changed:
                row = self._connection.execute(
                    "SELECT COUNT(*) FROM reservoir_vectors WHERE model=? AND embedding_identity<>?",
                    (model_value, identity),
                ).fetchone()
                invalidated = int(row[0])
                self._connection.execute(
                    "DELETE FROM reservoir_vectors WHERE model=? AND embedding_identity<>?",
                    (model_value, identity),
                )
                self._meta_set(self._identity_meta_key(model_value), identity)
            return {
                "changed": changed,
                "previous": previous,
                "current": identity,
                "invalidated": invalidated,
            }

    def close(self) -> None:
        with self._lock:
            try:
                self._connection.commit()
                self._connection.close()
            except Exception:
                pass

    def clear(self, *, model: str | None = None, embedding_identity: str | None = None) -> None:
        with self._lock, self._connection:
            if model and embedding_identity:
                self._connection.execute(
                    "DELETE FROM reservoir_vectors WHERE model=? AND embedding_identity=?",
                    (str(model), str(embedding_identity)),
                )
            elif model:
                self._connection.execute("DELETE FROM reservoir_vectors WHERE model=?", (str(model),))
            else:
                self._connection.execute("DELETE FROM reservoir_vectors")

    def upsert(
        self,
        *,
        record_id: str,
        model: str,
        vector: list[float],
        content: str,
        embedding_identity: str = "",
    ) -> bool:
        values = [float(value) for value in vector]
        if not values:
            return False
        norm = _norm(values)
        if norm <= 0.0:
            return False
        identity = str(embedding_identity or "")
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO reservoir_vectors(
                    record_id,model,dimensions,vector_json,vector_norm,content_hash,updated_at,embedding_identity
                ) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(record_id,model) DO UPDATE SET
                    dimensions=excluded.dimensions,
                    vector_json=excluded.vector_json,
                    vector_norm=excluded.vector_norm,
                    content_hash=excluded.content_hash,
                    updated_at=excluded.updated_at,
                    embedding_identity=excluded.embedding_identity
                """,
                (
                    str(record_id), str(model), len(values),
                    json.dumps(values, separators=(",", ":")), norm,
                    content_hash(content), time(), identity,
                ),
            )
        return True

    def remove_missing(
        self,
        record_ids: Iterable[str],
        *,
        model: str,
        embedding_identity: str | None = None,
    ) -> int:
        allowed = {str(item) for item in record_ids}
        with self._lock:
            if embedding_identity is None:
                rows = self._connection.execute(
                    "SELECT record_id FROM reservoir_vectors WHERE model=?", (str(model),)
                ).fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT record_id FROM reservoir_vectors WHERE model=? AND embedding_identity=?",
                    (str(model), str(embedding_identity)),
                ).fetchall()
            stale = [str(row[0]) for row in rows if str(row[0]) not in allowed]
            if not stale:
                return 0
            with self._connection:
                if embedding_identity is None:
                    self._connection.executemany(
                        "DELETE FROM reservoir_vectors WHERE record_id=? AND model=?",
                        [(rid, str(model)) for rid in stale],
                    )
                else:
                    self._connection.executemany(
                        "DELETE FROM reservoir_vectors WHERE record_id=? AND model=? AND embedding_identity=?",
                        [(rid, str(model), str(embedding_identity)) for rid in stale],
                    )
            return len(stale)

    def search(
        self,
        query_vector: list[float],
        *,
        model: str,
        limit: int = 8,
        embedding_identity: str | None = None,
    ) -> list[VectorHit]:
        query = [float(value) for value in query_vector]
        if not query:
            return []
        limit = max(1, min(50, int(limit)))
        with self._lock:
            if embedding_identity is None:
                rows = self._connection.execute(
                    """
                    SELECT record_id,model,dimensions,vector_json,vector_norm,content_hash,embedding_identity
                    FROM reservoir_vectors
                    WHERE model=? AND dimensions=?
                    ORDER BY updated_at DESC LIMIT ?
                    """,
                    (str(model), len(query), self.max_scan),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """
                    SELECT record_id,model,dimensions,vector_json,vector_norm,content_hash,embedding_identity
                    FROM reservoir_vectors
                    WHERE model=? AND dimensions=? AND embedding_identity=?
                    ORDER BY updated_at DESC LIMIT ?
                    """,
                    (str(model), len(query), str(embedding_identity), self.max_scan),
                ).fetchall()
        hits: list[VectorHit] = []
        for row in rows:
            try:
                vector = [float(value) for value in json.loads(row["vector_json"])]
            except Exception:
                continue
            score = cosine_similarity(query, vector, b_norm=float(row["vector_norm"]))
            hits.append(
                VectorHit(
                    record_id=str(row["record_id"]),
                    score=score,
                    model=str(row["model"]),
                    content_hash=str(row["content_hash"]),
                    embedding_identity=str(row["embedding_identity"] or ""),
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def count(self, *, model: str | None = None, embedding_identity: str | None = None) -> int:
        with self._lock:
            if model and embedding_identity:
                row = self._connection.execute(
                    "SELECT COUNT(*) FROM reservoir_vectors WHERE model=? AND embedding_identity=?",
                    (str(model), str(embedding_identity)),
                ).fetchone()
            elif model:
                row = self._connection.execute(
                    "SELECT COUNT(*) FROM reservoir_vectors WHERE model=?", (str(model),)
                ).fetchone()
            else:
                row = self._connection.execute("SELECT COUNT(*) FROM reservoir_vectors").fetchone()
            return int(row[0])

    def status(self, *, model: str | None = None, embedding_identity: str | None = None) -> dict[str, Any]:
        with self._lock:
            size = int(self.path.stat().st_size) if self.path is not None and self.path.exists() else 0
            return {
                "enabled": True,
                "persistent": self.path is not None,
                "path": str(self.path) if self.path is not None else ":memory:",
                "vectors": self.count(model=model, embedding_identity=embedding_identity),
                "model": str(model or "all"),
                "embedding_identity": str(embedding_identity or ""),
                "registered_identity": self.registered_identity(model) if model else None,
                "max_scan": self.max_scan,
                "size_bytes": size,
                "schema_version": self.SCHEMA_VERSION,
                "authority": "derived retrieval cache only",
            }
