"""Rebuildable SQLite cognitive reservoir for fast local retrieval.

The reservoir is a *derived index*, not an authority.  Mary's canonical
identity, relationship, memory, knowledge, preference, and developed-self
systems remain the sources of truth.  Losing this database must be recoverable
by rebuilding it from those systems.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sqlite3
from threading import RLock
from time import time
from typing import Any, Iterable


@dataclass(frozen=True)
class ReservoirRecord:
    record_id: str
    kind: str
    subject: str
    predicate: str
    content: str
    source: str
    authority: str
    confidence: float = 1.0
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: float = field(default_factory=time)


@dataclass(frozen=True)
class ReservoirHit:
    record_id: str
    kind: str
    subject: str
    predicate: str
    content: str
    source: str
    authority: str
    confidence: float
    score: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "kind": self.kind,
            "subject": self.subject,
            "predicate": self.predicate,
            "content": self.content,
            "source": self.source,
            "authority": self.authority,
            "confidence": round(self.confidence, 3),
            "score": round(self.score, 4),
            "metadata": dict(self.metadata),
        }


class CognitiveReservoir:
    """Fast local searchable projection over authoritative Mary state."""

    SCHEMA_VERSION = 1

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        max_records: int = 50_000,
        max_megabytes: int = 512,
    ) -> None:
        self.path = Path(path).expanduser().resolve() if path else None
        self.max_records = max(1_000, int(max_records))
        self.max_megabytes = max(32, int(max_megabytes))
        self._fts = False
        # Desktop turns run on a worker QThread while dashboard/status calls can
        # arrive from the GUI thread. SQLite connections are thread-affine by
        # default, so the reservoir owns one cross-thread connection protected
        # by a re-entrant lock. The reservoir is derived/cache state only.
        self._lock = RLock()
        self._connection = self._connect()
        self._initialize()

    @classmethod
    def in_memory(cls) -> "CognitiveReservoir":
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
        connection.execute("PRAGMA temp_store=MEMORY")
        return connection

    def _initialize(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS reservoir_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reservoir_records (
                record_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                authority TEXT NOT NULL,
                confidence REAL NOT NULL,
                tags TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_reservoir_subject_predicate
                ON reservoir_records(subject, predicate);
            CREATE INDEX IF NOT EXISTS idx_reservoir_kind
                ON reservoir_records(kind);
            CREATE INDEX IF NOT EXISTS idx_reservoir_authority
                ON reservoir_records(authority);
            """
        )
        try:
            self._connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS reservoir_fts USING fts5(
                    record_id UNINDEXED,
                    content,
                    subject,
                    predicate,
                    tags
                )
                """
            )
            self._fts = True
        except sqlite3.OperationalError:
            self._fts = False
        self._connection.execute(
            "INSERT OR REPLACE INTO reservoir_meta(key, value) VALUES('schema_version', ?)",
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

    def clear(self) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM reservoir_records")
            if self._fts:
                self._connection.execute("DELETE FROM reservoir_fts")

    def rebuild(self, records: Iterable[ReservoirRecord]) -> int:
        """Atomically replace the derived index with supplied records."""
        materialized = list(records)[: self.max_records]
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM reservoir_records")
            if self._fts:
                self._connection.execute("DELETE FROM reservoir_fts")
            for record in materialized:
                self._upsert_no_commit(record)
        self._enforce_file_budget()
        return len(materialized)

    def upsert(self, record: ReservoirRecord) -> None:
        with self._lock:
            with self._connection:
                self._upsert_no_commit(record)
            self._enforce_record_budget()
            self._enforce_file_budget()

    def _upsert_no_commit(self, record: ReservoirRecord) -> None:
        tags = " ".join(str(item).strip() for item in record.tags if str(item).strip())
        metadata_json = json.dumps(record.metadata, ensure_ascii=False, sort_keys=True, default=str)
        self._connection.execute(
            """
            INSERT INTO reservoir_records(
                record_id, kind, subject, predicate, content, source, authority,
                confidence, tags, metadata_json, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(record_id) DO UPDATE SET
                kind=excluded.kind,
                subject=excluded.subject,
                predicate=excluded.predicate,
                content=excluded.content,
                source=excluded.source,
                authority=excluded.authority,
                confidence=excluded.confidence,
                tags=excluded.tags,
                metadata_json=excluded.metadata_json,
                updated_at=excluded.updated_at
            """,
            (
                record.record_id,
                record.kind,
                record.subject,
                record.predicate,
                record.content,
                record.source,
                record.authority,
                max(0.0, min(1.0, float(record.confidence))),
                tags,
                metadata_json,
                float(record.updated_at),
            ),
        )
        if self._fts:
            self._connection.execute("DELETE FROM reservoir_fts WHERE record_id = ?", (record.record_id,))
            self._connection.execute(
                "INSERT INTO reservoir_fts(record_id,content,subject,predicate,tags) VALUES(?,?,?,?,?)",
                (record.record_id, record.content, record.subject, record.predicate, tags),
            )

    def exact(self, *, subject: str, predicate: str) -> ReservoirHit | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM reservoir_records
                WHERE lower(subject)=lower(?) AND lower(predicate)=lower(?)
                ORDER BY confidence DESC, updated_at DESC LIMIT 1
                """,
                (str(subject), str(predicate)),
            ).fetchone()
            return self._row_to_hit(row, score=1.0) if row else None

    def get(self, record_id: str) -> ReservoirHit | None:
        """Return one derived record by id for hybrid/vector validation."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM reservoir_records WHERE record_id=? LIMIT 1",
                (str(record_id),),
            ).fetchone()
            return self._row_to_hit(row, score=0.0) if row else None

    def records(self, *, limit: int | None = None) -> list[ReservoirRecord]:
        """Return bounded records for explicit maintenance/index rebuild jobs."""
        resolved = self.max_records if limit is None else max(1, min(self.max_records, int(limit)))
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM reservoir_records
                ORDER BY confidence DESC, updated_at DESC
                LIMIT ?
                """,
                (resolved,),
            ).fetchall()
        output: list[ReservoirRecord] = []
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except Exception:
                metadata = {}
            output.append(
                ReservoirRecord(
                    record_id=str(row["record_id"]),
                    kind=str(row["kind"]),
                    subject=str(row["subject"]),
                    predicate=str(row["predicate"]),
                    content=str(row["content"]),
                    source=str(row["source"]),
                    authority=str(row["authority"]),
                    confidence=float(row["confidence"]),
                    tags=tuple(str(row["tags"] or "").split()),
                    metadata=dict(metadata) if isinstance(metadata, dict) else {},
                    updated_at=float(row["updated_at"]),
                )
            )
        return output

    def search(self, query: str, *, limit: int = 8, minimum_confidence: float = 0.0) -> list[ReservoirHit]:
        with self._lock:
            text = " ".join(str(query or "").split()).strip()
            if not text:
                return []
            limit = max(1, min(50, int(limit)))
            hits: list[ReservoirHit] = []
            if self._fts:
                # Quote tokens to avoid user punctuation becoming FTS syntax.
                tokens = [token for token in _query_tokens(text) if token]
                if tokens:
                    fts_query = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens[:12])
                    try:
                        rows = self._connection.execute(
                            """
                            SELECT r.*, bm25(reservoir_fts) AS rank
                            FROM reservoir_fts
                            JOIN reservoir_records r ON r.record_id = reservoir_fts.record_id
                            WHERE reservoir_fts MATCH ? AND r.confidence >= ?
                            ORDER BY rank ASC, r.confidence DESC
                            LIMIT ?
                            """,
                            (fts_query, float(minimum_confidence), limit),
                        ).fetchall()
                        for row in rows:
                            rank = float(row["rank"] if row["rank"] is not None else 0.0)
                            score = 1.0 / (1.0 + max(0.0, rank))
                            hits.append(self._row_to_hit(row, score=score))
                        return hits
                    except sqlite3.OperationalError:
                        pass
    
            like = f"%{text.lower()}%"
            rows = self._connection.execute(
                """
                SELECT * FROM reservoir_records
                WHERE confidence >= ? AND (
                    lower(content) LIKE ? OR lower(subject) LIKE ? OR
                    lower(predicate) LIKE ? OR lower(tags) LIKE ?
                )
                ORDER BY confidence DESC, updated_at DESC
                LIMIT ?
                """,
                (float(minimum_confidence), like, like, like, like, limit),
            ).fetchall()
            return [self._row_to_hit(row, score=0.5) for row in rows]
    

    def _row_to_hit(self, row: sqlite3.Row, *, score: float) -> ReservoirHit:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except Exception:
            metadata = {}
        return ReservoirHit(
            record_id=str(row["record_id"]),
            kind=str(row["kind"]),
            subject=str(row["subject"]),
            predicate=str(row["predicate"]),
            content=str(row["content"]),
            source=str(row["source"]),
            authority=str(row["authority"]),
            confidence=float(row["confidence"]),
            score=float(score),
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
        )

    def _enforce_record_budget(self) -> None:
        with self._lock:
            count = int(self._connection.execute("SELECT COUNT(*) FROM reservoir_records").fetchone()[0])
            if count <= self.max_records:
                return
            excess = count - self.max_records
            # The reservoir is derived; prune lowest-confidence/non-authoritative
            # cache entries first. Canonical state itself is never touched.
            with self._connection:
                rows = self._connection.execute(
                    """
                    SELECT record_id FROM reservoir_records
                    ORDER BY CASE WHEN authority IN ('creator_explicit','mary_canonical','mary_developed','knowledge_verified') THEN 1 ELSE 0 END ASC,
                             confidence ASC, updated_at ASC
                    LIMIT ?
                    """,
                    (excess,),
                ).fetchall()
                for row in rows:
                    rid = str(row[0])
                    self._connection.execute("DELETE FROM reservoir_records WHERE record_id=?", (rid,))
                    if self._fts:
                        self._connection.execute("DELETE FROM reservoir_fts WHERE record_id=?", (rid,))
    

    def _enforce_file_budget(self) -> None:
        with self._lock:
            if self.path is None or not self.path.exists():
                return
            maximum = self.max_megabytes * 1024 * 1024
            if self.path.stat().st_size <= maximum:
                return
            # Do not risk deleting high-authority state to hit a derived-cache
            # budget. Remove low-authority entries, then compact the database.
            with self._connection:
                rows = self._connection.execute(
                    """
                    SELECT record_id FROM reservoir_records
                    WHERE authority NOT IN ('creator_explicit','mary_canonical','mary_developed','knowledge_verified')
                    ORDER BY confidence ASC, updated_at ASC
                    LIMIT 2000
                    """
                ).fetchall()
                for row in rows:
                    rid = str(row[0])
                    self._connection.execute("DELETE FROM reservoir_records WHERE record_id=?", (rid,))
                    if self._fts:
                        self._connection.execute("DELETE FROM reservoir_fts WHERE record_id=?", (rid,))
            try:
                self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self._connection.execute("VACUUM")
            except sqlite3.OperationalError:
                pass
    

    def status(self) -> dict[str, Any]:
        with self._lock:
            count = int(self._connection.execute("SELECT COUNT(*) FROM reservoir_records").fetchone()[0])
            size = 0
            if self.path is not None and self.path.exists():
                size = int(self.path.stat().st_size)
            return {
                "enabled": True,
                "persistent": self.path is not None,
                "path": str(self.path) if self.path is not None else ":memory:",
                "records": count,
                "fts5": self._fts,
                "size_bytes": size,
                "max_records": self.max_records,
                "max_megabytes": self.max_megabytes,
                "schema_version": self.SCHEMA_VERSION,
            }


def _query_tokens(text: str) -> list[str]:
    stop = {
        "the", "a", "an", "and", "or", "to", "of", "is", "are", "was", "were",
        "do", "does", "did", "you", "your", "my", "me", "mary", "what", "who",
        "when", "where", "why", "how", "about", "that", "this", "it", "i", "we",
    }
    cleaned = "".join(ch.lower() if ch.isalnum() or ch in "_-'" else " " for ch in text)
    return [token for token in cleaned.split() if len(token) > 1 and token not in stop]
