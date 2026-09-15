"""Closed-loop action verification for MaryV2."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .storage import AtomicJsonStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class VerificationRecord:
    id: str
    intent: str
    action_type: str
    expected_state: dict[str, Any]
    source: str
    status: str
    created_at: str
    updated_at: str
    task_id: str = ""
    trace_id: str = ""
    action_result: str = ""
    observation: dict[str, Any] | None = None
    verdict: str = "pending"


class ActionVerificationManager:
    """Separate action acceptance from evidence that the intended effect occurred."""

    VERSION = 1

    def __init__(self, path: Path, *, capacity: int = 2000) -> None:
        self.capacity = max(64, int(capacity))
        self._store = AtomicJsonStore(path, default={"version": self.VERSION, "records": []})

    def begin(
        self,
        *,
        intent: str,
        action_type: str,
        expected_state: dict[str, Any],
        source: str,
        task_id: str = "",
        trace_id: str = "",
    ) -> VerificationRecord:
        now = _now()
        record = VerificationRecord(
            id=f"verify_{uuid4().hex}",
            intent=str(intent).strip()[:1200],
            action_type=str(action_type).strip()[:160],
            expected_state=dict(expected_state),
            source=str(source).strip()[:160] or "unknown",
            status="awaiting_action",
            created_at=now,
            updated_at=now,
            task_id=str(task_id).strip()[:160],
            trace_id=str(trace_id).strip()[:160],
        )
        if not record.intent or not record.action_type:
            raise ValueError("intent and action_type are required")
        self._append(record)
        return record

    def record_action_result(self, record_id: str, *, result: str) -> VerificationRecord:
        return self._update(
            record_id,
            status="awaiting_observation",
            action_result=str(result).strip()[:1200],
        )

    def verify(self, record_id: str, *, observation: dict[str, Any]) -> VerificationRecord:
        current = self.get(record_id)
        observed = dict(observation)
        matches = all(observed.get(key) == value for key, value in current.expected_state.items())
        verdict = "confirmed" if matches else "failed"
        return self._update(
            record_id,
            status="verified",
            observation=observed,
            verdict=verdict,
        )

    def mark_uncertain(self, record_id: str, *, observation: dict[str, Any] | None = None) -> VerificationRecord:
        return self._update(
            record_id,
            status="verified",
            observation=dict(observation or {}),
            verdict="uncertain",
        )

    def pending(self) -> list[VerificationRecord]:
        return [
            self._decode(row)
            for row in self._store.snapshot().get("records", [])
            if row.get("verdict") == "pending"
        ]

    def get(self, record_id: str) -> VerificationRecord:
        for row in self._store.snapshot().get("records", []):
            if row.get("id") == record_id:
                return self._decode(row)
        raise KeyError(record_id)

    def status(self) -> dict[str, Any]:
        rows = list(self._store.snapshot().get("records") or [])
        return {
            "version": self.VERSION,
            "records": len(rows),
            "pending": sum(1 for row in rows if row.get("verdict") == "pending"),
            "confirmed": sum(1 for row in rows if row.get("verdict") == "confirmed"),
            "failed": sum(1 for row in rows if row.get("verdict") == "failed"),
        }

    def _append(self, record: VerificationRecord) -> None:
        def mutate(data: dict[str, Any]) -> None:
            rows = list(data.get("records") or [])
            rows.append(asdict(record))
            data["records"] = rows[-self.capacity :]
            data["version"] = self.VERSION
        self._store.mutate(mutate)

    def _update(self, record_id: str, **changes: Any) -> VerificationRecord:
        found = False
        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            for row in list(data.get("records") or []):
                if row.get("id") == record_id:
                    row.update(changes)
                    row["updated_at"] = _now()
                    found = True
                    break
        self._store.mutate(mutate)
        if not found:
            raise KeyError(record_id)
        return self.get(record_id)

    @staticmethod
    def _decode(row: dict[str, Any]) -> VerificationRecord:
        return VerificationRecord(**dict(row))
