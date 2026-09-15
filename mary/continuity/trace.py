"""Bounded end-to-end causal trace metadata for MaryV2."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from .storage import AtomicJsonStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_labels(labels: dict[str, Any] | None) -> dict[str, str | int | float | bool | None]:
    result: dict[str, str | int | float | bool | None] = {}
    for key, value in dict(labels or {}).items():
        name = str(key).strip()[:80]
        if not name:
            continue
        if isinstance(value, (bool, int, float)) or value is None:
            result[name] = value
        else:
            result[name] = str(value).strip()[:240]
    return result


@dataclass(frozen=True)
class TraceSpan:
    id: str
    trace_id: str
    stage: str
    status: str
    started_at: str
    finished_at: str | None
    duration_ms: float | None
    surface_id: str = ""
    task_id: str = ""
    node_id: str = ""
    labels: dict[str, Any] | None = None


class CausalTraceLedger:
    """Operational traces only: no prompts, private content, or hidden reasoning."""

    VERSION = 1

    def __init__(self, path: Path, *, capacity: int = 5000) -> None:
        self.capacity = max(128, int(capacity))
        self._store = AtomicJsonStore(path, default={"version": self.VERSION, "spans": []})
        self._monotonic_started: dict[str, float] = {}

    def start(
        self,
        *,
        trace_id: str,
        stage: str,
        surface_id: str = "",
        task_id: str = "",
        node_id: str = "",
        labels: dict[str, Any] | None = None,
    ) -> TraceSpan:
        span = TraceSpan(
            id=f"span_{uuid4().hex}",
            trace_id=str(trace_id).strip()[:160] or f"trace_{uuid4().hex}",
            stage=str(stage).strip()[:160] or "unknown",
            status="running",
            started_at=_now(),
            finished_at=None,
            duration_ms=None,
            surface_id=str(surface_id).strip()[:160],
            task_id=str(task_id).strip()[:160],
            node_id=str(node_id).strip()[:160],
            labels=_safe_labels(labels),
        )
        self._monotonic_started[span.id] = monotonic()

        def mutate(data: dict[str, Any]) -> None:
            rows = list(data.get("spans") or [])
            rows.append(asdict(span))
            data["spans"] = rows[-self.capacity :]
            data["version"] = self.VERSION
        self._store.mutate(mutate)
        return span

    def finish(self, span_id: str, *, status: str = "ok", labels: dict[str, Any] | None = None) -> TraceSpan:
        found = False
        finished_at = _now()
        started = self._monotonic_started.pop(span_id, None)
        duration_ms = None if started is None else round(max(0.0, (monotonic() - started) * 1000.0), 3)

        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            for row in list(data.get("spans") or []):
                if row.get("id") == span_id:
                    row["status"] = str(status).strip()[:80] or "ok"
                    row["finished_at"] = finished_at
                    row["duration_ms"] = duration_ms
                    merged = dict(row.get("labels") or {})
                    merged.update(_safe_labels(labels))
                    row["labels"] = merged
                    found = True
                    break
        self._store.mutate(mutate)
        if not found:
            raise KeyError(span_id)
        return self.get(span_id)

    def get(self, span_id: str) -> TraceSpan:
        for row in self._store.snapshot().get("spans", []):
            if row.get("id") == span_id:
                return TraceSpan(**row)
        raise KeyError(span_id)

    def trace(self, trace_id: str) -> list[TraceSpan]:
        return [
            TraceSpan(**row)
            for row in self._store.snapshot().get("spans", [])
            if row.get("trace_id") == trace_id
        ]

    def status(self) -> dict[str, Any]:
        rows = list(self._store.snapshot().get("spans") or [])
        return {
            "version": self.VERSION,
            "spans": len(rows),
            "running": sum(1 for row in rows if row.get("status") == "running"),
            "privacy": "metadata only; no raw prompts/audio/images/hidden reasoning",
        }
