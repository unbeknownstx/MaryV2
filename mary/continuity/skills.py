"""Procedural skill memory for MaryV2.

A skill describes reusable know-how. It does not execute tools and does not
become eligible until explicitly approved.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .storage import AtomicJsonStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(v).strip()[:240] for v in values if str(v).strip()))


@dataclass(frozen=True)
class SkillRecord:
    id: str
    name: str
    version: int
    status: str
    source: str
    description: str
    required_capabilities: tuple[str, ...]
    required_permissions: tuple[str, ...]
    steps: tuple[str, ...]
    verification: tuple[str, ...]
    failure_recovery: tuple[str, ...]
    created_at: str
    approved_at: str | None = None
    approved_by: str | None = None


class SkillLibrary:
    VERSION = 1

    def __init__(self, path: Path, *, capacity: int = 1000) -> None:
        self.capacity = max(32, int(capacity))
        self._store = AtomicJsonStore(path, default={"version": self.VERSION, "skills": []})

    def register_candidate(
        self,
        *,
        name: str,
        description: str,
        source: str,
        required_capabilities: Iterable[str] = (),
        required_permissions: Iterable[str] = (),
        steps: Iterable[str] = (),
        verification: Iterable[str] = (),
        failure_recovery: Iterable[str] = (),
    ) -> SkillRecord:
        name = str(name).strip()[:160]
        if not name:
            raise ValueError("skill name is required")
        snapshot = self._store.snapshot()
        versions = [
            int(row.get("version", 0))
            for row in snapshot.get("skills", [])
            if row.get("name") == name
        ]
        record = SkillRecord(
            id=f"skill_{uuid4().hex}",
            name=name,
            version=(max(versions) + 1) if versions else 1,
            status="candidate",
            source=str(source).strip()[:240] or "unknown",
            description=str(description).strip()[:1200],
            required_capabilities=_tuple(required_capabilities),
            required_permissions=_tuple(required_permissions),
            steps=_tuple(steps),
            verification=_tuple(verification),
            failure_recovery=_tuple(failure_recovery),
            created_at=_now(),
        )

        def mutate(data: dict[str, Any]) -> None:
            rows = list(data.get("skills") or [])
            payload = asdict(record)
            for key in (
                "required_capabilities",
                "required_permissions",
                "steps",
                "verification",
                "failure_recovery",
            ):
                payload[key] = list(payload[key])
            rows.append(payload)
            data["skills"] = rows[-self.capacity :]
            data["version"] = self.VERSION

        self._store.mutate(mutate)
        return record

    def approve(self, skill_id: str, *, approved_by: str = "creator") -> SkillRecord:
        found = False
        approved_at = _now()

        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            for row in list(data.get("skills") or []):
                if row.get("id") == skill_id:
                    row["status"] = "approved"
                    row["approved_at"] = approved_at
                    row["approved_by"] = str(approved_by).strip()[:160] or "creator"
                    found = True
                    break

        self._store.mutate(mutate)
        if not found:
            raise KeyError(skill_id)
        return self.get(skill_id)

    def reject(self, skill_id: str) -> SkillRecord:
        found = False

        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            for row in list(data.get("skills") or []):
                if row.get("id") == skill_id:
                    row["status"] = "rejected"
                    found = True
                    break

        self._store.mutate(mutate)
        if not found:
            raise KeyError(skill_id)
        return self.get(skill_id)

    def get(self, skill_id: str) -> SkillRecord:
        for row in self._store.snapshot().get("skills", []):
            if row.get("id") == skill_id:
                return self._decode(row)
        raise KeyError(skill_id)

    def eligible(self, *, capabilities: Iterable[str], permissions: Iterable[str]) -> list[SkillRecord]:
        capabilities_set = set(_tuple(capabilities))
        permissions_set = set(_tuple(permissions))
        result: list[SkillRecord] = []
        for row in self._store.snapshot().get("skills", []):
            skill = self._decode(row)
            if skill.status != "approved":
                continue
            if not set(skill.required_capabilities).issubset(capabilities_set):
                continue
            if not set(skill.required_permissions).issubset(permissions_set):
                continue
            result.append(skill)
        return result

    def status(self) -> dict[str, Any]:
        rows = list(self._store.snapshot().get("skills") or [])
        return {
            "version": self.VERSION,
            "skills": len(rows),
            "approved": sum(1 for row in rows if row.get("status") == "approved"),
            "candidates": sum(1 for row in rows if row.get("status") == "candidate"),
            "execution": "descriptive only; ToolManager retains execution authority",
        }

    @staticmethod
    def _decode(row: dict[str, Any]) -> SkillRecord:
        values = dict(row)
        for key in (
            "required_capabilities",
            "required_permissions",
            "steps",
            "verification",
            "failure_recovery",
        ):
            values[key] = tuple(values.get(key) or [])
        return SkillRecord(**values)
