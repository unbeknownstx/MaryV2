"""Durable executive plan graph for MaryV2.

Plans are explicit task state, not hidden chain-of-thought. They connect goals,
subgoals, dependencies, approvals, capabilities and verification evidence so
work can survive model swaps, device disconnects and Core restarts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Iterable
from uuid import uuid4

from .storage import AtomicJsonStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _tuple(values: Iterable[str], *, limit: int = 50, item_limit: int = 240) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            _text(item, item_limit)
            for item in list(values)[:limit]
            if _text(item, item_limit)
        )
    )


@dataclass(frozen=True)
class PlanStep:
    id: str
    title: str
    status: str
    order: int
    depends_on: tuple[str, ...]
    blockers: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    required_approvals: tuple[str, ...]
    verification: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    assigned_node_id: str
    skill_id: str
    created_at: str
    updated_at: str
    last_result: str = ""


@dataclass(frozen=True)
class ExecutivePlan:
    id: str
    objective: str
    source: str
    status: str
    priority: float
    goal_id: str
    workflow_id: str
    parent_plan_id: str
    tags: tuple[str, ...]
    created_at: str
    updated_at: str
    steps: tuple[PlanStep, ...]


class ExecutivePlanGraph:
    """Persistent DAG-ish plan state with deterministic next-action selection."""

    VERSION = 1
    PLAN_STATUSES = {"draft", "active", "waiting", "paused", "completed", "failed", "cancelled"}
    STEP_STATUSES = {"pending", "ready", "running", "waiting", "completed", "failed", "cancelled"}

    def __init__(self, path: Path, *, capacity: int = 512, step_capacity: int = 128) -> None:
        self.capacity = max(32, int(capacity))
        self.step_capacity = max(8, min(512, int(step_capacity)))
        self._store = AtomicJsonStore(
            path,
            default={"version": self.VERSION, "plans": []},
        )

    def create(
        self,
        *,
        objective: str,
        source: str,
        steps: Iterable[str] = (),
        priority: float = 0.5,
        goal_id: str = "",
        workflow_id: str = "",
        parent_plan_id: str = "",
        tags: Iterable[str] = (),
    ) -> ExecutivePlan:
        objective = _text(objective, 1600)
        if not objective:
            raise ValueError("plan objective is required")
        now = _now()
        plan_id = f"plan_{uuid4().hex}"
        step_rows: list[dict[str, Any]] = []
        for index, title in enumerate(list(steps)[: self.step_capacity]):
            clean = _text(title, 800)
            if not clean:
                continue
            step_rows.append(self._step_payload(
                title=clean,
                order=index,
                created_at=now,
            ))
        payload = {
            "id": plan_id,
            "objective": objective,
            "source": _text(source, 180) or "unknown",
            "status": "draft" if not step_rows else "active",
            "priority": max(0.0, min(1.0, float(priority))),
            "goal_id": _text(goal_id, 160),
            "workflow_id": _text(workflow_id, 160),
            "parent_plan_id": _text(parent_plan_id, 160),
            "tags": list(_tuple(tags, limit=24, item_limit=80)),
            "created_at": now,
            "updated_at": now,
            "steps": step_rows,
        }

        def mutate(data: dict[str, Any]) -> None:
            rows = list(data.get("plans") or [])
            rows.append(payload)
            data["plans"] = rows[-self.capacity :]
            data["version"] = self.VERSION

        self._store.mutate(mutate)
        return self.get(plan_id)

    def add_step(
        self,
        plan_id: str,
        *,
        title: str,
        depends_on: Iterable[str] = (),
        blockers: Iterable[str] = (),
        required_capabilities: Iterable[str] = (),
        required_approvals: Iterable[str] = (),
        verification: Iterable[str] = (),
        skill_id: str = "",
    ) -> PlanStep:
        current = self.get(plan_id)
        if current.status in {"completed", "cancelled"}:
            raise ValueError("terminal plan cannot accept new steps")
        step_id = f"step_{uuid4().hex}"
        now = _now()
        payload = self._step_payload(
            title=_text(title, 800),
            order=len(current.steps),
            created_at=now,
            step_id=step_id,
            depends_on=depends_on,
            blockers=blockers,
            required_capabilities=required_capabilities,
            required_approvals=required_approvals,
            verification=verification,
            skill_id=skill_id,
        )
        if not payload["title"]:
            raise ValueError("step title is required")

        def mutate(data: dict[str, Any]) -> None:
            for row in list(data.get("plans") or []):
                if row.get("id") != plan_id:
                    continue
                steps = list(row.get("steps") or [])
                steps.append(payload)
                row["steps"] = steps[-self.step_capacity :]
                row["status"] = "active"
                row["updated_at"] = now
                return
            raise KeyError(plan_id)

        self._store.mutate(mutate)
        return self.get_step(plan_id, step_id)

    def start_step(self, plan_id: str, step_id: str, *, node_id: str = "") -> PlanStep:
        return self._update_step(
            plan_id,
            step_id,
            status="running",
            assigned_node_id=_text(node_id, 180),
        )

    def complete_step(
        self,
        plan_id: str,
        step_id: str,
        *,
        result: str = "",
        evidence_ids: Iterable[str] = (),
    ) -> PlanStep:
        step = self._update_step(
            plan_id,
            step_id,
            status="completed",
            last_result=_text(result, 1600),
            evidence_ids=list(_tuple(evidence_ids, limit=32, item_limit=180)),
        )
        self._refresh_plan_status(plan_id)
        return step

    def fail_step(self, plan_id: str, step_id: str, *, reason: str) -> PlanStep:
        step = self._update_step(
            plan_id,
            step_id,
            status="failed",
            last_result=_text(reason, 1600),
        )
        self._update_plan(plan_id, status="failed")
        return step

    def wait_step(
        self,
        plan_id: str,
        step_id: str,
        *,
        reason: str,
        evidence_ids: Iterable[str] = (),
    ) -> PlanStep:
        """Pause one step after a recoverable failure without killing the plan."""

        current = self.get_step(plan_id, step_id)
        blockers = _tuple(
            [*current.blockers, _text(reason, 240)],
            limit=32,
            item_limit=240,
        )
        evidence = _tuple(
            [*current.evidence_ids, *list(evidence_ids)],
            limit=32,
            item_limit=180,
        )
        step = self._update_step(
            plan_id,
            step_id,
            status="waiting",
            blockers=list(blockers),
            evidence_ids=list(evidence),
            last_result=_text(reason, 1600),
        )
        self._update_plan(plan_id, status="waiting")
        return step

    def recover_running_steps(
        self,
        *,
        reason: str = "runtime restarted before terminal task evidence was received",
    ) -> int:
        """Move orphanable running steps to waiting on Core reconstruction.

        Device tasks are process-local by design. A durable plan step therefore
        cannot remain "running" after the process that owned its task broker has
        disappeared. Recovery preserves the plan and makes the missing terminal
        evidence explicit instead of pretending the action completed.
        """

        changed = 0
        now = _now()
        clean_reason = _text(reason, 240)

        def mutate(data: dict[str, Any]) -> None:
            nonlocal changed
            for plan in list(data.get("plans") or []):
                plan_changed = False
                for step in list(plan.get("steps") or []):
                    if str(step.get("status") or "") != "running":
                        continue
                    blockers = list(step.get("blockers") or [])
                    if clean_reason and clean_reason not in blockers:
                        blockers.append(clean_reason)
                    step["blockers"] = blockers[-32:]
                    step["status"] = "waiting"
                    step["assigned_node_id"] = ""
                    step["last_result"] = clean_reason
                    step["updated_at"] = now
                    changed += 1
                    plan_changed = True
                if plan_changed:
                    plan["status"] = "waiting"
                    plan["updated_at"] = now

        self._store.mutate(mutate)
        return changed

    def block_step(self, plan_id: str, step_id: str, *, blocker: str) -> PlanStep:
        current = self.get_step(plan_id, step_id)
        blockers = _tuple([*current.blockers, blocker], limit=32, item_limit=240)
        return self._update_step(
            plan_id,
            step_id,
            status="waiting",
            blockers=list(blockers),
        )

    def resolve_blocker(self, plan_id: str, step_id: str, blocker: str) -> PlanStep:
        current = self.get_step(plan_id, step_id)
        blockers = tuple(item for item in current.blockers if item != blocker)
        return self._update_step(
            plan_id,
            step_id,
            status="pending" if blockers else "ready",
            blockers=list(blockers),
        )

    def satisfy_approval(self, plan_id: str, step_id: str, approval: str) -> PlanStep:
        current = self.get_step(plan_id, step_id)
        approvals = tuple(item for item in current.required_approvals if item != approval)
        return self._update_step(
            plan_id,
            step_id,
            required_approvals=list(approvals),
        )

    def pause(self, plan_id: str) -> ExecutivePlan:
        return self._update_plan(plan_id, status="paused")

    def resume(self, plan_id: str) -> ExecutivePlan:
        plan = self.get(plan_id)
        if plan.status in {"completed", "cancelled"}:
            return plan
        return self._update_plan(plan_id, status="active")

    def cancel(self, plan_id: str) -> ExecutivePlan:
        return self._update_plan(plan_id, status="cancelled")

    def get(self, plan_id: str) -> ExecutivePlan:
        for row in list(self._store.snapshot().get("plans") or []):
            if row.get("id") == plan_id:
                return self._decode_plan(row)
        raise KeyError(plan_id)

    def get_step(self, plan_id: str, step_id: str) -> PlanStep:
        for step in self.get(plan_id).steps:
            if step.id == step_id:
                return step
        raise KeyError(step_id)

    def active(self) -> list[ExecutivePlan]:
        rows = [
            self._decode_plan(row)
            for row in list(self._store.snapshot().get("plans") or [])
            if row.get("status") in {"draft", "active", "waiting", "paused"}
        ]
        rows.sort(key=lambda item: (item.priority, item.updated_at), reverse=True)
        return rows

    def next_actions(
        self,
        *,
        available_capabilities: Iterable[str] = (),
        granted_approvals: Iterable[str] = (),
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        capabilities = set(_tuple(available_capabilities, limit=256))
        approvals = set(_tuple(granted_approvals, limit=128))
        output: list[dict[str, Any]] = []
        for plan in self.active():
            if plan.status in {"paused", "waiting"}:
                continue
            completed = {step.id for step in plan.steps if step.status == "completed"}
            for step in sorted(plan.steps, key=lambda item: item.order):
                if step.status in {"running", "completed", "failed", "cancelled"}:
                    continue
                deps_met = set(step.depends_on).issubset(completed)
                blockers_clear = not step.blockers
                capabilities_met = set(step.required_capabilities).issubset(capabilities)
                approvals_met = set(step.required_approvals).issubset(approvals)
                executable = deps_met and blockers_clear and capabilities_met and approvals_met
                if not executable:
                    continue
                output.append({
                    "plan_id": plan.id,
                    "objective": plan.objective,
                    "priority": plan.priority,
                    "step_id": step.id,
                    "step": step.title,
                    "order": step.order,
                    "skill_id": step.skill_id,
                    "required_capabilities": list(step.required_capabilities),
                    "verification": list(step.verification),
                    "authority": "plan_candidate_only; execution remains capability/tool governed",
                })
                if len(output) >= max(1, min(50, int(limit))):
                    return output
        return output

    def relevant(self, query: str, *, limit: int = 8) -> list[ExecutivePlan]:
        terms = {
            token.casefold()
            for token in re.findall(r"[\w'-]{3,}", str(query or ""))
        }
        if not terms:
            return self.active()[:limit]
        scored: list[tuple[int, ExecutivePlan]] = []
        for plan in self.active():
            haystack = " ".join([
                plan.objective,
                " ".join(plan.tags),
                " ".join(step.title for step in plan.steps),
            ]).casefold()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, plan))
        scored.sort(key=lambda item: (item[0], item[1].priority, item[1].updated_at), reverse=True)
        return [item[1] for item in scored[: max(1, min(50, int(limit)))]]

    def status(self) -> dict[str, Any]:
        rows = list(self._store.snapshot().get("plans") or [])
        active = [row for row in rows if row.get("status") in {"draft", "active", "waiting", "paused"}]
        steps = [step for row in rows for step in list(row.get("steps") or [])]
        return {
            "version": self.VERSION,
            "plans": len(rows),
            "active_plans": len(active),
            "steps": len(steps),
            "running_steps": sum(1 for step in steps if step.get("status") == "running"),
            "waiting_steps": sum(1 for step in steps if step.get("status") == "waiting"),
            "policy": "explicit progress graph only; no hidden chain-of-thought or execution authority",
        }

    def _refresh_plan_status(self, plan_id: str) -> None:
        plan = self.get(plan_id)
        if plan.steps and all(step.status == "completed" for step in plan.steps):
            self._update_plan(plan_id, status="completed")
        elif any(step.status == "waiting" for step in plan.steps):
            self._update_plan(plan_id, status="waiting")
        else:
            self._update_plan(plan_id, status="active")

    def _update_plan(self, plan_id: str, **changes: Any) -> ExecutivePlan:
        found = False

        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            for row in list(data.get("plans") or []):
                if row.get("id") != plan_id:
                    continue
                row.update(changes)
                row["updated_at"] = _now()
                found = True
                break

        self._store.mutate(mutate)
        if not found:
            raise KeyError(plan_id)
        return self.get(plan_id)

    def _update_step(self, plan_id: str, step_id: str, **changes: Any) -> PlanStep:
        found = False
        now = _now()

        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            for row in list(data.get("plans") or []):
                if row.get("id") != plan_id:
                    continue
                for step in list(row.get("steps") or []):
                    if step.get("id") != step_id:
                        continue
                    step.update(changes)
                    step["updated_at"] = now
                    row["updated_at"] = now
                    found = True
                    return

        self._store.mutate(mutate)
        if not found:
            raise KeyError(step_id)
        return self.get_step(plan_id, step_id)

    @staticmethod
    def _step_payload(
        *,
        title: str,
        order: int,
        created_at: str,
        step_id: str | None = None,
        depends_on: Iterable[str] = (),
        blockers: Iterable[str] = (),
        required_capabilities: Iterable[str] = (),
        required_approvals: Iterable[str] = (),
        verification: Iterable[str] = (),
        skill_id: str = "",
    ) -> dict[str, Any]:
        return {
            "id": step_id or f"step_{uuid4().hex}",
            "title": title,
            "status": "pending",
            "order": int(order),
            "depends_on": list(_tuple(depends_on)),
            "blockers": list(_tuple(blockers)),
            "required_capabilities": list(_tuple(required_capabilities)),
            "required_approvals": list(_tuple(required_approvals)),
            "verification": list(_tuple(verification)),
            "evidence_ids": [],
            "assigned_node_id": "",
            "skill_id": _text(skill_id, 180),
            "created_at": created_at,
            "updated_at": created_at,
            "last_result": "",
        }

    @staticmethod
    def _decode_step(row: dict[str, Any]) -> PlanStep:
        values = dict(row)
        for key in (
            "depends_on",
            "blockers",
            "required_capabilities",
            "required_approvals",
            "verification",
            "evidence_ids",
        ):
            values[key] = tuple(values.get(key) or [])
        return PlanStep(**values)

    @classmethod
    def _decode_plan(cls, row: dict[str, Any]) -> ExecutivePlan:
        values = dict(row)
        values["tags"] = tuple(values.get("tags") or [])
        values["steps"] = tuple(cls._decode_step(step) for step in values.get("steps") or [])
        return ExecutivePlan(**values)
