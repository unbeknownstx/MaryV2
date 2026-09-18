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
    preconditions: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    origin_experience_ids: tuple[str, ...] = ()
    success_count: int = 0
    failure_count: int = 0
    confidence: float = 0.5
    last_used_at: str | None = None
    last_result: str = ""
    supersedes: str | None = None
    superseded_by: str | None = None
    revision_reason: str = ""


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
        preconditions: Iterable[str] = (),
        inputs: Iterable[str] = (),
        outputs: Iterable[str] = (),
        tags: Iterable[str] = (),
        origin_experience_ids: Iterable[str] = (),
        confidence: float = 0.5,
        supersedes: str | None = None,
        revision_reason: str = "",
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
            preconditions=_tuple(preconditions),
            inputs=_tuple(inputs),
            outputs=_tuple(outputs),
            tags=_tuple(tags),
            origin_experience_ids=_tuple(origin_experience_ids),
            confidence=max(0.0, min(1.0, float(confidence))),
            supersedes=(str(supersedes).strip()[:180] if supersedes else None),
            revision_reason=str(revision_reason or "").strip()[:600],
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
                "preconditions",
                "inputs",
                "outputs",
                "tags",
                "origin_experience_ids",
            ):
                payload[key] = list(payload[key])
            rows.append(payload)
            data["skills"] = rows[-self.capacity :]
            data["version"] = self.VERSION

        self._store.mutate(mutate)
        return record

    def approve(self, skill_id: str, *, approved_by: str = "creator") -> SkillRecord:
        candidate = self.get(skill_id)
        if candidate.status not in {"candidate", "approved"}:
            raise ValueError("only a candidate skill may be approved")
        predecessor_id = str(candidate.supersedes or "").strip()
        if predecessor_id:
            predecessor = self.get(predecessor_id)
            if predecessor.status != "approved":
                raise ValueError(
                    "skill revision may replace only the currently approved predecessor"
                )

        found = False
        approved_at = _now()

        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            rows = list(data.get("skills") or [])
            target = None
            predecessor = None
            for row in rows:
                if row.get("id") == skill_id:
                    target = row
                if predecessor_id and row.get("id") == predecessor_id:
                    predecessor = row
            if target is None:
                return
            target["status"] = "approved"
            target["approved_at"] = approved_at
            target["approved_by"] = str(approved_by).strip()[:160] or "creator"
            if predecessor is not None:
                predecessor["status"] = "superseded"
                predecessor["superseded_by"] = skill_id
            found = True

        self._store.mutate(mutate)
        if not found:
            raise KeyError(skill_id)
        return self.get(skill_id)

    def register_revision(
        self,
        skill_id: str,
        *,
        reason: str,
        description: str | None = None,
        steps: Iterable[str] | None = None,
        verification: Iterable[str] | None = None,
        failure_recovery: Iterable[str] | None = None,
        preconditions: Iterable[str] | None = None,
        inputs: Iterable[str] | None = None,
        outputs: Iterable[str] | None = None,
        tags: Iterable[str] | None = None,
        source: str = "creator_revision",
    ) -> SkillRecord:
        """Create a review-only revision without changing the approved procedure.

        A revision inherits capabilities and permissions from its approved
        predecessor. This prevents a seemingly harmless procedure edit from
        widening execution authority. The predecessor remains eligible until
        the creator explicitly approves the new candidate.
        """

        base = self.get(skill_id)
        if base.status != "approved":
            raise ValueError("only an approved skill may be revised")
        clean_reason = str(reason or "").strip()[:600]
        if not clean_reason:
            raise ValueError("skill revision reason is required")
        return self.register_candidate(
            name=base.name,
            description=base.description if description is None else str(description),
            source=str(source or "creator_revision"),
            required_capabilities=base.required_capabilities,
            required_permissions=base.required_permissions,
            steps=base.steps if steps is None else steps,
            verification=base.verification if verification is None else verification,
            failure_recovery=(
                base.failure_recovery
                if failure_recovery is None
                else failure_recovery
            ),
            preconditions=base.preconditions if preconditions is None else preconditions,
            inputs=base.inputs if inputs is None else inputs,
            outputs=base.outputs if outputs is None else outputs,
            tags=base.tags if tags is None else tags,
            origin_experience_ids=base.origin_experience_ids,
            confidence=base.confidence,
            supersedes=base.id,
            revision_reason=clean_reason,
        )

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

    def retrieve(
        self,
        query: str,
        *,
        capabilities: Iterable[str] = (),
        permissions: Iterable[str] = (),
        limit: int = 8,
        approved_only: bool = True,
    ) -> list[SkillRecord]:
        """Retrieve reusable know-how without granting execution authority."""

        terms = {
            token.casefold()
            for token in str(query or "").replace("/", " ").replace("_", " ").split()
            if len(token) >= 3
        }
        capabilities_set = set(_tuple(capabilities))
        permissions_set = set(_tuple(permissions))
        scored: list[tuple[float, SkillRecord]] = []
        for row in self._store.snapshot().get("skills", []):
            skill = self._decode(row)
            if approved_only and skill.status != "approved":
                continue
            if not set(skill.required_capabilities).issubset(capabilities_set):
                continue
            if not set(skill.required_permissions).issubset(permissions_set):
                continue
            haystack = " ".join((
                skill.name,
                skill.description,
                " ".join(skill.tags),
                " ".join(skill.preconditions),
                " ".join(skill.steps),
            )).casefold()
            lexical = sum(1.0 for term in terms if term in haystack)
            if terms and lexical <= 0:
                continue
            attempts = skill.success_count + skill.failure_count
            observed_quality = (
                skill.success_count / attempts
                if attempts > 0
                else skill.confidence
            )
            score = lexical + observed_quality * 0.5 + skill.confidence * 0.2
            scored.append((score, skill))
        scored.sort(
            key=lambda item: (
                item[0],
                item[1].success_count,
                item[1].last_used_at or "",
            ),
            reverse=True,
        )
        return [item[1] for item in scored[: max(1, min(50, int(limit)))]]

    def record_outcome(
        self,
        skill_id: str,
        *,
        success: bool,
        result: str = "",
        evidence_ids: Iterable[str] = (),
    ) -> SkillRecord:
        """Update procedural evidence; this never changes execution permissions."""

        found = False
        now = _now()
        evidence = _tuple(evidence_ids)

        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            for row in list(data.get("skills") or []):
                if row.get("id") != skill_id:
                    continue
                successes = int(row.get("success_count", 0) or 0)
                failures = int(row.get("failure_count", 0) or 0)
                if success:
                    successes += 1
                else:
                    failures += 1
                attempts = successes + failures
                empirical = successes / attempts if attempts else 0.5
                prior = max(0.0, min(1.0, float(row.get("confidence", 0.5) or 0.5)))
                # Bounded evidence update: repeated outcomes matter while a
                # creator-approved skill never silently changes authority.
                row["success_count"] = successes
                row["failure_count"] = failures
                row["confidence"] = round(prior * 0.35 + empirical * 0.65, 4)
                row["last_used_at"] = now
                row["last_result"] = str(result).strip()[:1200]
                row["origin_experience_ids"] = list(_tuple([
                    *(row.get("origin_experience_ids") or []),
                    *evidence,
                ]))
                found = True
                break

        self._store.mutate(mutate)
        if not found:
            raise KeyError(skill_id)
        return self.get(skill_id)

    def candidates(self) -> list[SkillRecord]:
        return [
            self._decode(row)
            for row in self._store.snapshot().get("skills", [])
            if row.get("status") == "candidate"
        ]

    def approved(self) -> list[SkillRecord]:
        return [
            self._decode(row)
            for row in self._store.snapshot().get("skills", [])
            if row.get("status") == "approved"
        ]

    def status(self) -> dict[str, Any]:
        rows = list(self._store.snapshot().get("skills") or [])
        return {
            "version": self.VERSION,
            "skills": len(rows),
            "approved": sum(1 for row in rows if row.get("status") == "approved"),
            "candidates": sum(1 for row in rows if row.get("status") == "candidate"),
            "successful_uses": sum(int(row.get("success_count", 0) or 0) for row in rows),
            "failed_uses": sum(int(row.get("failure_count", 0) or 0) for row in rows),
            "superseded": sum(1 for row in rows if row.get("status") == "superseded"),
            "revision_candidates": sum(
                1 for row in rows
                if row.get("status") == "candidate" and row.get("supersedes")
            ),
            "execution": "descriptive only; ToolManager/device capability fabric retains execution authority",
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
            "preconditions",
            "inputs",
            "outputs",
            "tags",
            "origin_experience_ids",
        ):
            values[key] = tuple(values.get(key) or [])
        values.setdefault("success_count", 0)
        values.setdefault("failure_count", 0)
        values.setdefault("confidence", 0.5)
        values.setdefault("last_used_at", None)
        values.setdefault("last_result", "")
        values.setdefault("supersedes", None)
        values.setdefault("superseded_by", None)
        values.setdefault("revision_reason", "")
        return SkillRecord(**values)
