"""Disposable specialist-worker envelopes for MaryV2.

Workers are task-local helpers, never alternate Mary identities. The parent
explicitly delegates a narrowed capability set; a worker cannot widen it.
This module provides lifecycle, budget, cancellation, and permission contracts.
It does not create threads/processes or bypass the existing ToolManager,
DeviceTaskBroker, provider router, or creator approval boundaries.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import monotonic
from typing import Any, Iterable
import uuid

VERSION = "13.41"

_TERMINAL = {"completed", "failed", "cancelled", "budget_exhausted"}


def _normalized_capabilities(values: Iterable[str] | None) -> frozenset[str]:
    output = {
        str(value or "").strip().lower()
        for value in (values or ())
        if str(value or "").strip()
    }
    return frozenset(sorted(output))


@dataclass(frozen=True)
class WorkerBudget:
    max_steps: int = 12
    max_tool_calls: int = 8
    max_provider_calls: int = 6
    max_seconds: float = 120.0
    max_result_characters: int = 24_000

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_steps", max(1, min(128, int(self.max_steps))))
        object.__setattr__(self, "max_tool_calls", max(0, min(64, int(self.max_tool_calls))))
        object.__setattr__(self, "max_provider_calls", max(0, min(64, int(self.max_provider_calls))))
        object.__setattr__(self, "max_seconds", max(0.5, min(3600.0, float(self.max_seconds))))
        object.__setattr__(
            self,
            "max_result_characters",
            max(256, min(250_000, int(self.max_result_characters))),
        )


@dataclass(frozen=True)
class SpecialistWorkerSpec:
    task_id: str
    role: str
    capabilities: frozenset[str]
    mutating_capabilities: frozenset[str] = field(default_factory=frozenset)
    budget: WorkerBudget = field(default_factory=WorkerBudget)
    privacy: str = "inherit"
    cost_class: str = "inherit"
    worker_id: str = field(default_factory=lambda: f"worker_{uuid.uuid4().hex[:12]}")

    def __post_init__(self) -> None:
        task_id = str(self.task_id or "").strip()
        role = str(self.role or "").strip().lower()
        if not task_id:
            raise ValueError("worker task_id is required")
        if not role:
            raise ValueError("worker role is required")
        capabilities = _normalized_capabilities(self.capabilities)
        mutating = _normalized_capabilities(self.mutating_capabilities)
        if not mutating.issubset(capabilities):
            raise ValueError("mutating capabilities must be a subset of worker capabilities")
        object.__setattr__(self, "task_id", task_id[:120])
        object.__setattr__(self, "role", role[:80])
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "mutating_capabilities", mutating)
        object.__setattr__(self, "privacy", str(self.privacy or "inherit").strip().lower()[:40])
        object.__setattr__(self, "cost_class", str(self.cost_class or "inherit").strip().lower()[:40])

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = sorted(self.capabilities)
        payload["mutating_capabilities"] = sorted(self.mutating_capabilities)
        return payload


class SpecialistWorkerSession:
    """Process-local lifecycle/accounting for one disposable specialist."""

    def __init__(self, spec: SpecialistWorkerSpec) -> None:
        self.spec = spec
        self._started = monotonic()
        self._status = "active"
        self._cancel_reason = ""
        self._steps = 0
        self._tool_calls = 0
        self._provider_calls = 0
        self._last_activity = "spawned"

    @property
    def active(self) -> bool:
        return self._status == "active"

    def _elapsed(self) -> float:
        return max(0.0, monotonic() - self._started)

    def _expire_time_budget(self) -> bool:
        if self.active and self._elapsed() > self.spec.budget.max_seconds:
            self._status = "budget_exhausted"
            self._last_activity = "time_budget_exhausted"
            return True
        return False

    def _require_active(self) -> None:
        if not self.active:
            raise RuntimeError(f"specialist worker is {self._status}")
        if self._expire_time_budget():
            raise RuntimeError("specialist worker time budget exhausted")

    def authorize_capability(self, capability: str, *, mutating: bool = False) -> bool:
        """Check the delegated envelope; this is not host execution approval."""
        self._require_active()
        name = str(capability or "").strip().lower()
        if not name or name not in self.spec.capabilities:
            return False
        if mutating and name not in self.spec.mutating_capabilities:
            return False
        return True

    def record_step(self, label: str = "") -> None:
        self._require_active()
        if self._steps >= self.spec.budget.max_steps:
            self._status = "budget_exhausted"
            self._last_activity = "step_budget_exhausted"
            raise RuntimeError("specialist worker step budget exhausted")
        self._steps += 1
        self._last_activity = str(label or "step").strip()[:120]

    def record_tool_call(self, capability: str, *, mutating: bool = False) -> None:
        self._require_active()
        if not self.authorize_capability(capability, mutating=mutating):
            raise PermissionError("specialist worker capability was not delegated")
        if self._tool_calls >= self.spec.budget.max_tool_calls:
            self._status = "budget_exhausted"
            self._last_activity = "tool_budget_exhausted"
            raise RuntimeError("specialist worker tool-call budget exhausted")
        self._tool_calls += 1
        self._last_activity = f"tool:{str(capability)[:96]}"

    def record_provider_call(self) -> None:
        self._require_active()
        if self._provider_calls >= self.spec.budget.max_provider_calls:
            self._status = "budget_exhausted"
            self._last_activity = "provider_budget_exhausted"
            raise RuntimeError("specialist worker provider-call budget exhausted")
        self._provider_calls += 1
        self._last_activity = "provider_call"

    def cancel(self, reason: str = "") -> None:
        if self._status in _TERMINAL:
            return
        self._status = "cancelled"
        self._cancel_reason = str(reason or "cancelled by parent").strip()[:240]
        self._last_activity = "cancelled"

    def complete(self) -> None:
        self._require_active()
        self._status = "completed"
        self._last_activity = "completed"

    def fail(self, reason: str = "") -> None:
        if self._status in _TERMINAL:
            return
        self._status = "failed"
        self._cancel_reason = str(reason or "worker failed").strip()[:240]
        self._last_activity = "failed"

    def clip_result(self, value: Any) -> str:
        text = str(value or "")
        limit = self.spec.budget.max_result_characters
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 1)].rstrip() + "…"

    def status(self) -> dict[str, Any]:
        self._expire_time_budget()
        return {
            "version": VERSION,
            "worker_id": self.spec.worker_id,
            "task_id": self.spec.task_id,
            "role": self.spec.role,
            "status": self._status,
            "elapsed_seconds": round(self._elapsed(), 3),
            "steps": self._steps,
            "tool_calls": self._tool_calls,
            "provider_calls": self._provider_calls,
            "capabilities": sorted(self.spec.capabilities),
            "mutating_capabilities": sorted(self.spec.mutating_capabilities),
            "cancel_reason": self._cancel_reason,
            "last_activity": self._last_activity,
            "ownership": {
                "mary_identity": False,
                "durable_memory": False,
                "creator_profile": False,
                "canonical_state": False,
            },
            "authority": (
                "delegated task-local envelope only; existing host/tool/device "
                "approval boundaries still decide actual execution"
            ),
        }


class SpecialistWorkerPool:
    """Bounded process-local registry for disposable specialist sessions."""

    def __init__(self, *, capacity: int = 8) -> None:
        self.capacity = max(1, min(64, int(capacity)))
        self._sessions: dict[str, SpecialistWorkerSession] = {}

    def spawn(
        self,
        *,
        task_id: str,
        role: str,
        parent_capabilities: Iterable[str],
        requested_capabilities: Iterable[str] = (),
        parent_mutating_capabilities: Iterable[str] = (),
        requested_mutating_capabilities: Iterable[str] = (),
        budget: WorkerBudget | None = None,
        privacy: str = "inherit",
        cost_class: str = "inherit",
    ) -> SpecialistWorkerSession:
        parent = _normalized_capabilities(parent_capabilities)
        requested = _normalized_capabilities(requested_capabilities)
        parent_mutating = _normalized_capabilities(parent_mutating_capabilities)
        requested_mutating = _normalized_capabilities(requested_mutating_capabilities)

        if not requested.issubset(parent):
            raise PermissionError("specialist worker cannot widen parent capabilities")
        if not parent_mutating.issubset(parent):
            raise ValueError("parent mutating capabilities must be within parent capabilities")
        if not requested_mutating.issubset(requested):
            raise PermissionError("mutating delegation must be within requested capabilities")
        if not requested_mutating.issubset(parent_mutating):
            raise PermissionError("specialist worker cannot widen parent mutation authority")

        active = [session for session in self._sessions.values() if session.active]
        if len(active) >= self.capacity:
            raise RuntimeError("active specialist worker capacity reached")

        if len(self._sessions) >= self.capacity * 2:
            terminal_ids = [
                worker_id
                for worker_id, session in self._sessions.items()
                if not session.active
            ]
            for worker_id in terminal_ids[: max(0, len(self._sessions) - self.capacity)]:
                self._sessions.pop(worker_id, None)

        spec = SpecialistWorkerSpec(
            task_id=task_id,
            role=role,
            capabilities=requested,
            mutating_capabilities=requested_mutating,
            budget=budget or WorkerBudget(),
            privacy=privacy,
            cost_class=cost_class,
        )
        session = SpecialistWorkerSession(spec)
        self._sessions[spec.worker_id] = session
        return session

    def get(self, worker_id: str) -> SpecialistWorkerSession | None:
        return self._sessions.get(str(worker_id or "").strip())

    def cancel_all(self, *, task_id: str | None = None, reason: str = "") -> int:
        count = 0
        for session in self._sessions.values():
            if not session.active:
                continue
            if task_id is not None and session.spec.task_id != str(task_id):
                continue
            session.cancel(reason)
            count += 1
        return count

    def status(self) -> dict[str, Any]:
        rows = [session.status() for session in self._sessions.values()]
        return {
            "version": VERSION,
            "capacity": self.capacity,
            "active": sum(1 for row in rows if row["status"] == "active"),
            "sessions": rows[-self.capacity :],
            "policy": (
                "disposable specialists inherit/narrow parent authority; "
                "workers never own Mary identity or durable memory"
            ),
        }
