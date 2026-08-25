"""Optional semantic vector index for Mary's rebuildable cognitive reservoir.

The index is derived cache state. It never owns memory or decides what is true.
Vectors only help locate candidate records; the canonical reservoir record still
carries authority/provenance and remains the returned content.

The implementation intentionally uses SQLite + Python cosine similarity so
MaryV2 can gain real embedding-based recall without a vector-database server or
new mandatory Python dependency. It is appropriate for Mary's current personal
scale; a future large multi-character service can swap the backend behind the
same interface.
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "score": round(float(self.score), 5),
            "model": self.model,
            "content_hash": self.content_hash,
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
    SCHEMA_VERSION = 1

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
                PRIMARY KEY(record_id, model)
            );
            CREATE INDEX IF NOT EXISTS idx_reservoir_vectors_model
                ON reservoir_vectors(model);
            """
        )
        self._connection.execute(
            "INSERT OR REPLACE INTO vector_meta(key,value) VALUES('schema_version',?)",
            (str(self.SCHEMA_VERSION),),
        )
        self._connection.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._connection.commit()
                self._connection.close()
            except Exception:
                pass

    def clear(self, *, model: str | None = None) -> None:
        with self._lock, self._connection:
            if model:
                self._connection.execute("DELETE FROM reservoir_vectors WHERE model=?", (str(model),))
            else:
                self._connection.execute("DELETE FROM reservoir_vectors")

    def upsert(self, *, record_id: str, model: str, vector: list[float], content: str) -> bool:
        values = [float(value) for value in vector]
        if not values:
            return False
        norm = _norm(values)
        if norm <= 0.0:
            return False
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO reservoir_vectors(record_id,model,dimensions,vector_json,vector_norm,content_hash,updated_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(record_id,model) DO UPDATE SET
                    dimensions=excluded.dimensions,
                    vector_json=excluded.vector_json,
                    vector_norm=excluded.vector_norm,
                    content_hash=excluded.content_hash,
                    updated_at=excluded.updated_at
                """,
                (
                    str(record_id), str(model), len(values),
                    json.dumps(values, separators=(",", ":")), norm,
                    content_hash(content), time(),
                ),
            )
        return True

    def remove_missing(self, record_ids: Iterable[str], *, model: str) -> int:
        allowed = {str(item) for item in record_ids}
        with self._lock:
            rows = self._connection.execute(
                "SELECT record_id FROM reservoir_vectors WHERE model=?", (str(model),)
            ).fetchall()
            stale = [str(row[0]) for row in rows if str(row[0]) not in allowed]
            if not stale:
                return 0
            with self._connection:
                self._connection.executemany(
                    "DELETE FROM reservoir_vectors WHERE record_id=? AND model=?",
                    [(rid, str(model)) for rid in stale],
                )
            return len(stale)

    def search(self, query_vector: list[float], *, model: str, limit: int = 8) -> list[VectorHit]:
        query = [float(value) for value in query_vector]
        if not query:
            return []
        limit = max(1, min(50, int(limit)))
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT record_id,model,dimensions,vector_json,vector_norm,content_hash
                FROM reservoir_vectors
                WHERE model=? AND dimensions=?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (str(model), len(query), self.max_scan),
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
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def count(self, *, model: str | None = None) -> int:
        with self._lock:
            if model:
                row = self._connection.execute(
                    "SELECT COUNT(*) FROM reservoir_vectors WHERE model=?", (str(model),)
                ).fetchone()
            else:
                row = self._connection.execute("SELECT COUNT(*) FROM reservoir_vectors").fetchone()
            return int(row[0])

    def status(self, *, model: str | None = None) -> dict[str, Any]:
        with self._lock:
            size = int(self.path.stat().st_size) if self.path is not None and self.path.exists() else 0
            return {
                "enabled": True,
                "persistent": self.path is not None,
                "path": str(self.path) if self.path is not None else ":memory:",
                "vectors": self.count(model=model),
                "model": str(model or "all"),
                "max_scan": self.max_scan,
                "size_bytes": size,
                "schema_version": self.SCHEMA_VERSION,
                "authority": "derived retrieval cache only",
            }
