"""Temporal, provenance-aware relationship facts for MaryV2.

This is not a replacement for canonical MemoryManager. It is a historical
index over time-bounded facts and relationships that canonical owners may
consult or project into retrieval.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from .storage import AtomicJsonStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TemporalRelation:
    id: str
    subject: str
    predicate: str
    value: Any
    valid_from: str
    valid_to: str | None
    source: str
    confidence: float
    authority: str
    supersedes: str | None = None

    @property
    def current(self) -> bool:
        return self.valid_to is None


class TemporalKnowledgeGraph:
    """Small durable temporal graph with explicit source and validity windows."""

    VERSION = 1

    def __init__(self, path: Path, *, capacity: int = 4000) -> None:
        self.capacity = max(64, int(capacity))
        self._store = AtomicJsonStore(path, default={"version": self.VERSION, "relations": []})

    def record(
        self,
        *,
        subject: str,
        predicate: str,
        value: Any,
        source: str,
        confidence: float = 1.0,
        authority: str = "candidate",
        valid_from: str | None = None,
        supersede_current: bool = True,
    ) -> TemporalRelation:
        subject = str(subject).strip()[:240]
        predicate = str(predicate).strip()[:160]
        source = str(source).strip()[:240] or "unknown"
        authority = str(authority).strip()[:80] or "candidate"
        if not subject or not predicate:
            raise ValueError("subject and predicate are required")
        confidence = max(0.0, min(float(confidence), 1.0))
        started = valid_from or _now()
        relation_id = f"temporal_{uuid4().hex}"
        superseded: str | None = None

        def mutate(data: dict[str, Any]) -> None:
            nonlocal superseded
            rows = list(data.get("relations") or [])
            if supersede_current:
                for row in rows:
                    if (
                        row.get("subject") == subject
                        and row.get("predicate") == predicate
                        and row.get("valid_to") is None
                    ):
                        row["valid_to"] = started
                        superseded = str(row.get("id") or "") or None
            relation = TemporalRelation(
                id=relation_id,
                subject=subject,
                predicate=predicate,
                value=value,
                valid_from=started,
                valid_to=None,
                source=source,
                confidence=confidence,
                authority=authority,
                supersedes=superseded,
            )
            rows.append(asdict(relation))
            data["version"] = self.VERSION
            data["relations"] = rows[-self.capacity :]

        self._store.mutate(mutate)
        return self.get(relation_id)

    def close_current(self, subject: str, predicate: str, *, valid_to: str | None = None) -> int:
        ended = valid_to or _now()
        count = 0

        def mutate(data: dict[str, Any]) -> None:
            nonlocal count
            for row in list(data.get("relations") or []):
                if (
                    row.get("subject") == subject
                    and row.get("predicate") == predicate
                    and row.get("valid_to") is None
                ):
                    row["valid_to"] = ended
                    count += 1

        self._store.mutate(mutate)
        return count

    def get(self, relation_id: str) -> TemporalRelation:
        for row in self._store.snapshot().get("relations", []):
            if row.get("id") == relation_id:
                return TemporalRelation(**row)
        raise KeyError(relation_id)

    def current(self, *, subject: str | None = None, predicate: str | None = None) -> list[TemporalRelation]:
        rows = self._store.snapshot().get("relations", [])
        return [
            TemporalRelation(**row)
            for row in rows
            if row.get("valid_to") is None
            and (subject is None or row.get("subject") == subject)
            and (predicate is None or row.get("predicate") == predicate)
        ]

    def history(
        self,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        limit: int = 100,
    ) -> list[TemporalRelation]:
        rows = self._store.snapshot().get("relations", [])
        selected = [
            TemporalRelation(**row)
            for row in rows
            if (subject is None or row.get("subject") == subject)
            and (predicate is None or row.get("predicate") == predicate)
        ]
        return selected[-max(1, int(limit)) :]

    def relevant(
        self,
        query: str,
        *,
        limit: int = 12,
        include_history: bool = True,
        context_floor: int = 2,
    ) -> list[TemporalRelation]:
        """Return bounded temporal evidence without losing current continuity anchors.

        Query matches rank first.  A small recency floor then keeps current
        relations visible even when the user's wording does not repeat the
        relation's subject/predicate (for example a deployment change while
        asking to repair MaryV2).  When history is requested, directly
        superseded rows for those current anchors are carried with them so a
        model never sees a new state without the prior state that explains it.
        """
        bounded_limit = max(1, min(100, int(limit)))
        bounded_floor = max(0, min(bounded_limit, int(context_floor)))
        terms = {
            token.casefold()
            for token in re.findall(r"[A-Za-z0-9_.-]{3,}", str(query or ""))
        }
        rows = [
            TemporalRelation(**row)
            for row in self._store.snapshot().get("relations", [])
            if include_history or row.get("valid_to") is None
        ]
        if not rows:
            return []

        def recency_key(item: TemporalRelation) -> tuple[bool, str, float]:
            return (item.current, item.valid_from, item.confidence)

        if not terms:
            rows.sort(key=recency_key, reverse=True)
            return rows[:bounded_limit]

        scored: list[tuple[float, TemporalRelation]] = []
        for item in rows:
            haystack = " ".join((
                item.subject,
                item.predicate,
                str(item.value),
                item.source,
                item.authority,
            )).casefold()
            lexical = sum(1.0 for term in terms if term in haystack)
            if lexical <= 0:
                continue
            score = lexical + (0.35 if item.current else 0.0) + 0.2 * float(item.confidence)
            scored.append((score, item))
        scored.sort(
            key=lambda pair: (
                pair[0],
                pair[1].current,
                pair[1].valid_from,
            ),
            reverse=True,
        )

        selected: list[TemporalRelation] = []
        selected_ids: set[str] = set()

        def add(item: TemporalRelation) -> None:
            if item.id in selected_ids or len(selected) >= bounded_limit:
                return
            selected.append(item)
            selected_ids.add(item.id)

        for _, item in scored:
            add(item)
            if len(selected) >= bounded_limit:
                return selected

        if bounded_floor:
            current_rows = sorted(
                (item for item in rows if item.current),
                key=recency_key,
                reverse=True,
            )
            anchors_added = 0
            for item in current_rows:
                before = len(selected)
                add(item)
                if len(selected) > before:
                    anchors_added += 1
                if anchors_added >= bounded_floor or len(selected) >= bounded_limit:
                    break

        if include_history and len(selected) < bounded_limit:
            anchor_ids = {
                item.supersedes
                for item in selected
                if item.current and item.supersedes
            }
            for item in sorted(rows, key=recency_key, reverse=True):
                if item.id in anchor_ids:
                    add(item)
                if len(selected) >= bounded_limit:
                    break

        return selected

    def status(self) -> dict[str, Any]:
        rows = list(self._store.snapshot().get("relations") or [])
        return {
            "version": self.VERSION,
            "relations": len(rows),
            "current": sum(1 for row in rows if row.get("valid_to") is None),
            "policy": "historical evidence index; not canonical memory authority",
        }
