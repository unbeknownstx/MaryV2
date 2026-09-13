"""Optional semantic vector index for Mary's rebuildable cognitive reservoir.

The index is derived cache state. It never owns memory or decides what is true.
Embedding identity is stored beside every vector so vectors from incompatible
model/runtime spaces are never compared silently.

When the optional ``sqlite-vec`` package is installed, the index can maintain a
native vec0 sidecar for fast exact KNN search. The canonical SQLite rows and the
pure-Python cosine path remain the reference/fallback implementation. Native
acceleration is therefore a performance choice, never a memory dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
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
    BACKENDS = {"auto", "python", "sqlite_vec"}

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        max_scan: int = 5000,
        backend: str | None = None,
    ) -> None:
        self.path = Path(path).expanduser().resolve() if path else None
        self.max_scan = max(100, min(100_000, int(max_scan)))
        requested = str(backend or os.getenv("MARY_VECTOR_BACKEND", "auto") or "auto").strip().lower()
        self.backend_requested = requested if requested in self.BACKENDS else "auto"
        self._backend_active = "python"
        self._backend_error: str | None = None
        self._sqlite_vec: Any | None = None
        self._lock = RLock()
        self._connection = self._connect()
        self._initialize()
        self._configure_optional_backend()

    @classmethod
    def in_memory(cls, *, backend: str | None = None) -> "SemanticVectorIndex":
        return cls(None, backend=backend)

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

    def _configure_optional_backend(self) -> None:
        if self.backend_requested == "python":
            return
        try:
            import sqlite_vec  # type: ignore[import-not-found]

            sqlite_vec.load(self._connection)
            self._sqlite_vec = sqlite_vec
            self._backend_active = "sqlite_vec"
            self._backend_error = None
        except Exception as exc:  # noqa: BLE001 - optional accelerator
            self._sqlite_vec = None
            self._backend_active = "python"
            self._backend_error = f"{type(exc).__name__}: {exc}"

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

    @staticmethod
    def _native_table_name(model: str, embedding_identity: str, dimensions: int) -> str:
        key = f"{model}\0{embedding_identity}\0{int(dimensions)}".encode("utf-8")
        digest = hashlib.sha256(key).hexdigest()[:20]
        return f"reservoir_vec_{digest}"

    def _native_table_exists(self, table: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,)
        ).fetchone()
        return row is not None

    def _ensure_native_table(self, *, model: str, embedding_identity: str, dimensions: int) -> str | None:
        if self._backend_active != "sqlite_vec" or self._sqlite_vec is None:
            return None
        table = self._native_table_name(model, embedding_identity, dimensions)
        if self._native_table_exists(table):
            return table
        try:
            self._connection.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {table} USING vec0(embedding float[{int(dimensions)}] distance_metric=cosine)"
            )
            return table
        except Exception as exc:  # noqa: BLE001 - accelerator fallback
            self._backend_error = f"native_table:{type(exc).__name__}: {exc}"
            return None

    def _native_delete_rowids(self, rows: list[sqlite3.Row]) -> None:
        if self._backend_active != "sqlite_vec":
            return
        grouped: dict[tuple[str, str, int], list[int]] = {}
        for row in rows:
            key = (str(row["model"]), str(row["embedding_identity"] or ""), int(row["dimensions"]))
            grouped.setdefault(key, []).append(int(row["rowid"]))
        for (model, identity, dimensions), rowids in grouped.items():
            table = self._native_table_name(model, identity, dimensions)
            if not self._native_table_exists(table):
                continue
            try:
                self._connection.executemany(
                    f"DELETE FROM {table} WHERE rowid=?", [(rowid,) for rowid in rowids]
                )
            except Exception as exc:  # noqa: BLE001
                self._backend_error = f"native_delete:{type(exc).__name__}: {exc}"

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
                stale_rows = self._connection.execute(
                    """
                    SELECT rowid,model,embedding_identity,dimensions
                    FROM reservoir_vectors WHERE model=? AND embedding_identity<>?
                    """,
                    (model_value, identity),
                ).fetchall()
                invalidated = len(stale_rows)
                self._native_delete_rowids(list(stale_rows))
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
            sql = "SELECT rowid,model,embedding_identity,dimensions FROM reservoir_vectors"
            params: tuple[Any, ...] = ()
            if model and embedding_identity:
                sql += " WHERE model=? AND embedding_identity=?"
                params = (str(model), str(embedding_identity))
            elif model:
                sql += " WHERE model=?"
                params = (str(model),)
            rows = list(self._connection.execute(sql, params).fetchall())
            self._native_delete_rowids(rows)
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
        model_value = str(model)
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
                    str(record_id), model_value, len(values),
                    json.dumps(values, separators=(",", ":")), norm,
                    content_hash(content), time(), identity,
                ),
            )
            row = self._connection.execute(
                "SELECT rowid FROM reservoir_vectors WHERE record_id=? AND model=?",
                (str(record_id), model_value),
            ).fetchone()
            if row is not None and self._backend_active == "sqlite_vec" and self._sqlite_vec is not None:
                table = self._ensure_native_table(
                    model=model_value, embedding_identity=identity, dimensions=len(values)
                )
                if table is not None:
                    try:
                        packed = self._sqlite_vec.serialize_float32(values)
                        self._connection.execute(
                            f"INSERT OR REPLACE INTO {table}(rowid,embedding) VALUES(?,?)",
                            (int(row[0]), packed),
                        )
                    except Exception as exc:  # noqa: BLE001
                        self._backend_error = f"native_upsert:{type(exc).__name__}: {exc}"
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
                    "SELECT rowid,record_id,model,embedding_identity,dimensions FROM reservoir_vectors WHERE model=?",
                    (str(model),),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """
                    SELECT rowid,record_id,model,embedding_identity,dimensions
                    FROM reservoir_vectors WHERE model=? AND embedding_identity=?
                    """,
                    (str(model), str(embedding_identity)),
                ).fetchall()
            stale_rows = [row for row in rows if str(row["record_id"]) not in allowed]
            if not stale_rows:
                return 0
            with self._connection:
                self._native_delete_rowids(stale_rows)
                self._connection.executemany(
                    "DELETE FROM reservoir_vectors WHERE rowid=?",
                    [(int(row["rowid"]),) for row in stale_rows],
                )
            return len(stale_rows)

    def _native_search(
        self,
        query: list[float],
        *,
        model: str,
        embedding_identity: str,
        limit: int,
    ) -> list[VectorHit] | None:
        if self._backend_active != "sqlite_vec" or self._sqlite_vec is None:
            return None
        table = self._native_table_name(model, embedding_identity, len(query))
        if not self._native_table_exists(table):
            return None
        try:
            packed = self._sqlite_vec.serialize_float32(query)
            native_rows = self._connection.execute(
                f"SELECT rowid,distance FROM {table} WHERE embedding MATCH ? AND k=? ORDER BY distance",
                (packed, int(limit)),
            ).fetchall()
            if not native_rows:
                return None
            hits: list[VectorHit] = []
            for native in native_rows:
                row = self._connection.execute(
                    """
                    SELECT record_id,model,content_hash,embedding_identity,dimensions
                    FROM reservoir_vectors WHERE rowid=?
                    """,
                    (int(native["rowid"]),),
                ).fetchone()
                if row is None:
                    continue
                if (
                    str(row["model"]) != str(model)
                    or str(row["embedding_identity"] or "") != str(embedding_identity)
                    or int(row["dimensions"]) != len(query)
                ):
                    continue
                score = max(-1.0, min(1.0, 1.0 - float(native["distance"])))
                hits.append(
                    VectorHit(
                        record_id=str(row["record_id"]),
                        score=score,
                        model=str(row["model"]),
                        content_hash=str(row["content_hash"]),
                        embedding_identity=str(row["embedding_identity"] or ""),
                    )
                )
            return hits[:limit] if hits else None
        except Exception as exc:  # noqa: BLE001 - fail open to reference search
            self._backend_error = f"native_search:{type(exc).__name__}: {exc}"
            return None

    def _python_search(
        self,
        query: list[float],
        *,
        model: str,
        limit: int,
        embedding_identity: str | None,
    ) -> list[VectorHit]:
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
            if embedding_identity is not None:
                registered = self._meta_get(self._identity_meta_key(str(model)))
                # A registered model space is authoritative for compatibility.
                # Direct identity-scoped index use without prior registration
                # remains supported; SQL still restricts candidates to the
                # supplied identity, so vectors never cross spaces.
                if registered is not None and registered != str(embedding_identity):
                    return []
                native = self._native_search(
                    query,
                    model=str(model),
                    embedding_identity=str(embedding_identity),
                    limit=limit,
                )
                if native is not None:
                    return native
            return self._python_search(
                query,
                model=str(model),
                limit=limit,
                embedding_identity=embedding_identity,
            )

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
            sqlite_vec_version = None
            if self._backend_active == "sqlite_vec":
                try:
                    row = self._connection.execute("SELECT vec_version()").fetchone()
                    sqlite_vec_version = str(row[0]) if row else None
                except Exception:
                    pass
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
                "backend": {
                    "requested": self.backend_requested,
                    "active": self._backend_active,
                    "sqlite_vec_version": sqlite_vec_version,
                    "last_error": self._backend_error,
                    "fallback": "python_cosine",
                },
                "authority": "derived retrieval cache only",
            }
