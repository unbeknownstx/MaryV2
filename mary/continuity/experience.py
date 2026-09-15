"""Durable experience ledger and conservative consolidation candidates."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .storage import AtomicJsonStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ExperienceEvent:
    id: str
    kind: str
    summary: str
    source: str
    occurred_at: str
    importance: float
    tags: tuple[str, ...]
    trace_id: str = ""
    task_id: str = ""


@dataclass(frozen=True)
class ConsolidationCandidate:
    id: str
    candidate_type: str
    summary: str
    source_experience_ids: tuple[str, ...]
    created_at: str
    status: str = "candidate"


class ExperienceLedger:
    """Bounded durable record of selected experiences and review candidates."""

    VERSION = 1

    def __init__(self, path: Path, *, capacity: int = 2000) -> None:
        self.capacity = max(64, int(capacity))
        self._store = AtomicJsonStore(
            path,
            default={"version": self.VERSION, "events": [], "candidates": [], "consolidated_ids": []},
        )

    def record(
        self,
        *,
        kind: str,
        summary: str,
        source: str,
        importance: float = 0.5,
        tags: Iterable[str] = (),
        trace_id: str = "",
        task_id: str = "",
        occurred_at: str | None = None,
    ) -> ExperienceEvent:
        event = ExperienceEvent(
            id=f"exp_{uuid4().hex}",
            kind=str(kind).strip()[:80] or "event",
            summary=str(summary).strip()[:1200],
            source=str(source).strip()[:160] or "unknown",
            occurred_at=occurred_at or _now(),
            importance=max(0.0, min(float(importance), 1.0)),
            tags=tuple(dict.fromkeys(str(x).strip()[:80] for x in tags if str(x).strip())),
            trace_id=str(trace_id).strip()[:160],
            task_id=str(task_id).strip()[:160],
        )
        if not event.summary:
            raise ValueError("experience summary is required")

        def mutate(data: dict[str, Any]) -> None:
            rows = list(data.get("events") or [])
            rows.append({**asdict(event), "tags": list(event.tags)})
            data["events"] = rows[-self.capacity :]
            data["version"] = self.VERSION

        self._store.mutate(mutate)
        return event

    def recent(self, *, limit: int = 50) -> list[ExperienceEvent]:
        rows = list(self._store.snapshot().get("events") or [])[-max(1, int(limit)) :]
        return [ExperienceEvent(**{**row, "tags": tuple(row.get("tags") or [])}) for row in rows]

    def consolidate(self, *, limit: int = 64) -> list[ConsolidationCandidate]:
        """Create deterministic candidates only; never promote canonical state."""
        snapshot = self._store.snapshot()
        consolidated = set(snapshot.get("consolidated_ids") or [])
        pending = [
            row for row in list(snapshot.get("events") or []) if row.get("id") not in consolidated
        ][-max(1, int(limit)) :]
        if not pending:
            return []

        candidates: list[ConsolidationCandidate] = []
        high = [row for row in pending if float(row.get("importance", 0.0)) >= 0.8]
        if high:
            candidates.append(
                ConsolidationCandidate(
                    id=f"candidate_{uuid4().hex}",
                    candidate_type="reflection",
                    summary=f"{len(high)} high-importance experience(s) merit governed review.",
                    source_experience_ids=tuple(str(row["id"]) for row in high),
                    created_at=_now(),
                )
            )

        tag_to_ids: dict[str, list[str]] = {}
        for row in pending:
            for tag in list(row.get("tags") or []):
                tag_to_ids.setdefault(str(tag), []).append(str(row["id"]))
        for tag, ids in sorted(tag_to_ids.items()):
            if len(ids) >= 3:
                candidates.append(
                    ConsolidationCandidate(
                        id=f"candidate_{uuid4().hex}",
                        candidate_type="pattern",
                        summary=f"Repeated experience pattern: {tag}",
                        source_experience_ids=tuple(ids),
                        created_at=_now(),
                    )
                )

        def mutate(data: dict[str, Any]) -> None:
            rows = list(data.get("candidates") or [])
            rows.extend(
                {**asdict(c), "source_experience_ids": list(c.source_experience_ids)}
                for c in candidates
            )
            data["candidates"] = rows[-1000:]
            done = list(data.get("consolidated_ids") or [])
            done.extend(str(row["id"]) for row in pending)
            data["consolidated_ids"] = list(dict.fromkeys(done))[-self.capacity :]

        self._store.mutate(mutate)
        return candidates

    def candidates(self, *, status: str = "candidate") -> list[ConsolidationCandidate]:
        rows = list(self._store.snapshot().get("candidates") or [])
        return [
            ConsolidationCandidate(
                **{**row, "source_experience_ids": tuple(row.get("source_experience_ids") or [])}
            )
            for row in rows
            if row.get("status") == status
        ]

    def set_candidate_status(self, candidate_id: str, status: str) -> bool:
        allowed = {"candidate", "approved", "rejected", "archived"}
        if status not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        changed = False

        def mutate(data: dict[str, Any]) -> None:
            nonlocal changed
            for row in list(data.get("candidates") or []):
                if row.get("id") == candidate_id:
                    row["status"] = status
                    changed = True
                    break

        self._store.mutate(mutate)
        return changed

    def status(self) -> dict[str, Any]:
        data = self._store.snapshot()
        return {
            "version": self.VERSION,
            "events": len(data.get("events") or []),
            "candidates": len(data.get("candidates") or []),
            "pending_candidates": sum(
                1 for row in list(data.get("candidates") or []) if row.get("status") == "candidate"
            ),
            "promotion": "explicit/governed only",
        }
