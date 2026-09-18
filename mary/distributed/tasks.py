"""Bounded capability task planning and broker for MaryV2 device nodes.

Core may select a replaceable device node and queue a narrowly typed task, but
execution always occurs on the device under that device's local permission
policy. There is intentionally no shell-command task type here.

13.50 adds bounded claim leases. If a replay-safe claim stalls, the old attempt
is terminally expired and a new task ID is queued as its replacement. Late
completion of the old ID cannot mutate the replacement. MCP work is never
blindly replayed.

13.51 wires the benchmark-aware HomeComputeScheduler into the real broker.
13.52 feeds currently claimed broker work back as process-local NodeLoad.
13.53 accepts a tiny allowlisted resource report on task completion, expires it
quickly, and folds measured RAM/accelerator pressure into the same scheduler.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import Condition, RLock
from time import monotonic
from typing import Any, Callable
from uuid import uuid4

from .compute_fabric import BenchmarkBook, BenchmarkSample, HomeComputeScheduler, NodeLoad, WorkloadRequest
from .nodes import NodeRegistry
from .mcp_fabric import MCP_CAPABILITIES, sanitize_mcp_result, sanitize_mcp_task_args
from .engineering import (
    ENGINEERING_CAPABILITIES,
    READ_ONLY_ENGINEERING_CAPABILITIES,
    sanitize_engineering_result,
    sanitize_engineering_task_args,
)
from .resource_telemetry import ResourceTelemetry, merge_resource_load, sanitize_resource_telemetry
from .sensors import SENSOR_CAPABILITIES, sanitize_sensor_result, sanitize_sensor_task_args


_ALLOWED_EXECUTION_CAPABILITIES = {
    "personal_search", "llm.local", "llm.ollama", "llm.llama_cpp",
    *MCP_CAPABILITIES, *SENSOR_CAPABILITIES, *ENGINEERING_CAPABILITIES,
}
_TERMINAL_STATUSES = {"completed", "rejected", "failed", "expired"}
_REPLAY_SAFE_CAPABILITIES = {
    "personal_search", "llm.local", "llm.ollama", "llm.llama_cpp",
    *SENSOR_CAPABILITIES, *READ_ONLY_ENGINEERING_CAPABILITIES,
}
_REALTIME_OPERATIONS = {"conversation", "quick_answer", "stt", "vision"}
ExecutionPolicy = Callable[[str], None]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _operation_for(capability: str, args: dict[str, Any] | None) -> str:
    name = str(capability or "").strip().lower()
    values = dict(args or {})
    if name in {"llm.local", "llm.ollama", "llm.llama_cpp"}:
        role = str(values.get("role") or "general").strip().lower()
        return {
            "conversation": "conversation",
            "fast": "quick_answer",
            "utility": "utility",
            "general": "general",
        }.get(role, "general")
    if name == "personal_search":
        return "search"
    if "audio" in name and "transcrib" in name:
        return "stt"
    if name.startswith("sensor.screen"):
        return "vision"
    if name.startswith("mcp."):
        return "tool"
    if name.startswith("engineering.tests.") or name == "engineering.structure.verify":
        return "test"
    if name == "engineering.repair.plan":
        return "engineering_plan"
    if name.startswith("engineering."):
        return "engineering"
    return "general"


def _workload_for(capability: str, args: dict[str, Any] | None) -> WorkloadRequest:
    operation = _operation_for(capability, args)
    return WorkloadRequest(
        capability=str(capability).strip().lower(),
        operation=operation,
        realtime=operation in _REALTIME_OPERATIONS,
        privacy_required=(
            str(capability).strip().lower().startswith("sensor.")
            or str(capability).strip().lower().startswith("engineering.")
        ),
        local_preferred=True,
        cost_sensitive=True,
    )


def _sanitize_task_args(capability: str, args: dict[str, Any] | None) -> dict[str, Any]:
    values = dict(args or {})
    if capability == "personal_search":
        query = _clean_text(values.get("query"), 500)
        if not query:
            raise ValueError("personal_search requires a non-empty query.")
        limit = int(values.get("limit", 8) or 8)
        return {"query": query, "limit": max(1, min(12, limit))}
    if capability in {"llm.local", "llm.ollama", "llm.llama_cpp"}:
        provider_label = capability
        raw_messages = values.get("messages")
        if not isinstance(raw_messages, list) or not raw_messages:
            raise ValueError(f"{provider_label} requires a non-empty messages array.")
        if len(raw_messages) > 12:
            raise ValueError(f"{provider_label} supports at most 12 messages per task.")
        messages: list[dict[str, str]] = []
        total_characters = 0
        for raw_message in raw_messages:
            if not isinstance(raw_message, dict):
                raise ValueError(f"Each {provider_label} message must be a JSON object.")
            role = str(raw_message.get("role") or "").strip().lower()
            if role not in {"system", "user", "assistant"}:
                raise ValueError(f"{provider_label} message role must be system, user, or assistant.")
            content = str(raw_message.get("content") or "").strip()
            if not content:
                raise ValueError(f"{provider_label} messages cannot be empty.")
            if len(content) > 48_000:
                raise ValueError(f"A single {provider_label} message exceeds the 48000 character task limit.")
            total_characters += len(content)
            if total_characters > 48_000:
                raise ValueError(f"{provider_label} message content exceeds the 48000 character task limit.")
            messages.append({"role": role, "content": content})
        role = str(values.get("role") or "general").strip().lower()
        if role not in {"general", "conversation", "fast", "utility"}:
            raise ValueError(f"{provider_label} role must be general, conversation, fast, or utility.")
        try:
            temperature = float(values.get("temperature", 0.7))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{provider_label} temperature must be numeric.") from exc
        temperature = max(0.0, min(1.5, temperature))
        try:
            max_tokens = int(values.get("max_tokens", 1024) or 1024)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{provider_label} max_tokens must be an integer.") from exc
        return {"messages": messages, "role": role, "temperature": temperature, "max_tokens": max(1, min(2048, max_tokens))}
    if capability in MCP_CAPABILITIES:
        return sanitize_mcp_task_args(capability, values)
    if capability in SENSOR_CAPABILITIES:
        return sanitize_sensor_task_args(capability, values)
    if capability in ENGINEERING_CAPABILITIES:
        return sanitize_engineering_task_args(capability, values)
    raise ValueError(f"Capability execution is not supported: {capability}")


def _sanitize_task_result(capability: str, result: dict[str, Any] | None) -> dict[str, Any]:
    values = dict(result or {})
    if capability in MCP_CAPABILITIES:
        return sanitize_mcp_result(capability, values)
    if capability in SENSOR_CAPABILITIES:
        return sanitize_sensor_result(capability, values)
    if capability in ENGINEERING_CAPABILITIES:
        return sanitize_engineering_result(capability, values)
    if capability not in {"llm.local", "llm.ollama", "llm.llama_cpp"}:
        return values
    content = str(values.get("content") or "").strip()
    if not content:
        return {}
    if len(content) > 32_000:
        content = content[:31_999].rstrip() + "…"
    usage = values.get("usage")
    usage_values = dict(usage or {}) if isinstance(usage, dict) else {}
    safe_usage = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        try:
            safe_usage[key] = max(0, int(usage_values.get(key, 0) or 0))
        except (TypeError, ValueError):
            safe_usage[key] = 0
    runtime = str(values.get("runtime") or "").strip().lower()
    if runtime not in {"lm_studio", "ollama", "llama_cpp"}:
        runtime = (
            "llama_cpp"
            if capability == "llm.llama_cpp"
            else "ollama"
            if capability == "llm.ollama"
            else "local"
        )
    provider = (
        "local_device"
        if capability == "llm.local"
        else "llama_cpp"
        if capability == "llm.llama_cpp"
        else "ollama"
    )
    payload = {
        "content": content,
        "provider": provider,
        "model": str(values.get("model") or "unknown")[:160],
        "finish_reason": str(values.get("finish_reason") or "")[:80],
        "usage": safe_usage,
        "privacy": "generated on selected device; raw provider payload not retained by Core",
    }
    # Preserve the long-standing llm.ollama/llm.llama_cpp wire contract.
    # Runtime identity is new metadata only for the generic llm.local capability.
    if capability == "llm.local":
        payload["runtime"] = runtime
    return payload


@dataclass(frozen=True)
class CapabilityTaskPlan:
    task_id: str
    capability: str
    intent: str
    requester_device_id: str
    selected_node_id: str | None
    status: str
    execution_authorized: bool = False
    execution_endpoint: None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeviceCapabilityTask:
    task_id: str
    capability: str
    intent: str
    args: dict[str, Any]
    requester_device_id: str
    selected_node_id: str
    status: str = "queued"
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    claimed: bool = False
    attempt: int = 1
    root_task_id: str = ""
    replacement_task_id: str = ""
    operation: str = "general"
    claimed_monotonic: float | None = field(default=None, repr=False)
    created_monotonic: float = field(default_factory=monotonic, repr=False)

    def __post_init__(self) -> None:
        if not self.root_task_id:
            self.root_task_id = self.task_id
        self.operation = str(self.operation or "general").strip().lower()[:80] or "general"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "capability": self.capability,
            "intent": self.intent,
            "args": dict(self.args),
            "requester_device_id": self.requester_device_id,
            "selected_node_id": self.selected_node_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result": dict(self.result),
            "error": self.error,
            "attempt": self.attempt,
            "root_task_id": self.root_task_id,
            "replacement_task_id": self.replacement_task_id,
            "operation": self.operation,
        }


class DeviceTaskBroker:
    """Small in-memory Core broker for bounded device tasks.

    Device tasks, scheduler evidence, and resource telemetry are intentionally
    ephemeral. They are not Mary memories or canonical character state.
    """

    VERSION = "13.53"

    def __init__(
        self,
        *,
        max_tasks: int = 200,
        ttl_seconds: float = 900.0,
        claim_lease_seconds: float = 660.0,
        max_claim_attempts: int = 2,
        resource_ttl_seconds: float = 90.0,
        lifecycle_lock: RLock | None = None,
        live_node: Callable[[str], bool] | None = None,
        execution_policy: ExecutionPolicy | None = None,
    ) -> None:
        self.max_tasks = max(20, int(max_tasks))
        self.ttl_seconds = max(30.0, float(ttl_seconds))
        self.claim_lease_seconds = max(30.0, min(float(claim_lease_seconds), self.ttl_seconds))
        self.max_claim_attempts = max(1, min(5, int(max_claim_attempts)))
        self.resource_ttl_seconds = max(10.0, min(600.0, float(resource_ttl_seconds)))
        self._lock = lifecycle_lock or RLock()
        self._condition = Condition(self._lock)
        self._live_node = live_node
        self._execution_policy = execution_policy
        self._tasks: dict[str, DeviceCapabilityTask] = {}
        self._order: list[str] = []
        self._benchmark_book = BenchmarkBook()
        self._compute_scheduler: HomeComputeScheduler | None = None
        self._scheduler_registry: NodeRegistry | None = None
        self._resources: dict[str, tuple[float, ResourceTelemetry]] = {}
        self._resource_rejections = 0

    def set_execution_policy(self, policy: ExecutionPolicy | None) -> None:
        with self._condition:
            self._execution_policy = policy
            self._condition.notify_all()

    def _enforce_execution_policy(self, kind: str) -> None:
        if self._execution_policy is not None:
            self._execution_policy(kind)

    def update_resource_telemetry(self, node_id: str, payload: dict[str, Any] | None) -> ResourceTelemetry:
        node_key = str(node_id or "").strip()[:160]
        if not node_key:
            raise ValueError("resource telemetry requires node_id")
        report = sanitize_resource_telemetry(payload)
        with self._lock:
            self._resources[node_key] = (monotonic(), report)
        return report

    def _resource_for(self, node_id: str) -> ResourceTelemetry | None:
        entry = self._resources.get(str(node_id))
        if entry is None:
            return None
        measured_at, report = entry
        if monotonic() - measured_at > self.resource_ttl_seconds:
            self._resources.pop(str(node_id), None)
            return None
        return report

    def _scheduler_for(self, registry: NodeRegistry) -> HomeComputeScheduler:
        if self._compute_scheduler is None or self._scheduler_registry is not registry:
            self._scheduler_registry = registry
            self._compute_scheduler = HomeComputeScheduler(registry, benchmarks=self._benchmark_book)
        return self._compute_scheduler

    def _active_loads(self, node_ids: set[str]) -> dict[str, NodeLoad]:
        counts = {node_id: {"realtime": 0, "background": 0} for node_id in node_ids}
        for task in self._tasks.values():
            if task.status != "claimed" or task.selected_node_id not in counts:
                continue
            lane = "realtime" if task.operation in _REALTIME_OPERATIONS else "background"
            counts[task.selected_node_id][lane] += 1
        output: dict[str, NodeLoad] = {}
        for node_id, values in counts.items():
            base = NodeLoad(
                node_id=node_id,
                active_realtime=values["realtime"],
                active_background=values["background"],
                stream_critical=values["realtime"] > 0,
            )
            report = self._resource_for(node_id)
            output[node_id] = merge_resource_load(base, report) if report is not None else base
        return output

    def _select_node(self, registry: NodeRegistry, capability: str, args: dict[str, Any]) -> Any:
        fallback = registry.choose(capability, require_execution_ready=True)
        if fallback is None:
            return None
        candidates_fn = getattr(registry, "executable_candidates", None)
        if not callable(candidates_fn):
            return fallback
        candidates = list(candidates_fn(capability))
        if not candidates:
            return fallback
        operation = _operation_for(capability, args)
        node_ids = {str(node.node_id) for node in candidates}
        loads = self._active_loads(node_ids)
        has_live_pressure = any(
            load.active_realtime > 0
            or load.active_background > 0
            or load.memory_fraction is not None
            or load.accelerator_fraction is not None
            for load in loads.values()
        )
        has_runtime_evidence = any(
            self._benchmark_book.summary(node.node_id, capability, operation).get("samples", 0) > 0
            for node in candidates
        )
        if not has_runtime_evidence and not has_live_pressure:
            return fallback
        scheduler = self._scheduler_for(registry)
        for load in loads.values():
            scheduler.update_load(load)
        selected = scheduler.choose(_workload_for(capability, args))
        if selected is None:
            return fallback
        return selected if selected.node_id in node_ids else fallback

    def enqueue(
        self,
        registry: NodeRegistry,
        *,
        capability: str,
        intent: str,
        args: dict[str, Any] | None,
        requester_device_id: str,
        preferred_node_id: str | None = None,
    ) -> DeviceCapabilityTask:
        normalized = str(capability or "").strip().lower()
        if normalized not in _ALLOWED_EXECUTION_CAPABILITIES:
            raise ValueError(f"Capability execution is not supported: {normalized}")
        sanitized_args = _sanitize_task_args(normalized, args)
        with self._condition:
            self._enforce_execution_policy("device_task.enqueue")
            self._expire_locked()
            selected = None
            clean_preferred = str(preferred_node_id or "").strip()
            if clean_preferred:
                candidates_fn = getattr(registry, "executable_candidates", None)
                candidates = (
                    list(candidates_fn(normalized))
                    if callable(candidates_fn)
                    else []
                )
                selected = next(
                    (
                        node for node in candidates
                        if str(getattr(node, "node_id", "")) == clean_preferred
                    ),
                    None,
                )
                if selected is None:
                    raise LookupError(
                        f"Preferred node {clean_preferred} is not live/authorized for capability: {normalized}"
                    )
            else:
                selected = self._select_node(registry, normalized, sanitized_args)
            if selected is None:
                raise LookupError(f"No connected node supports capability: {normalized}")
            task = DeviceCapabilityTask(
                task_id=f"capability_task_{uuid4().hex}",
                capability=normalized,
                intent=_clean_text(intent, 500),
                args=sanitized_args,
                requester_device_id=_clean_text(requester_device_id or "unknown-device", 160),
                selected_node_id=selected.node_id,
                operation=_operation_for(normalized, sanitized_args),
            )
            self._tasks[task.task_id] = task
            self._order.append(task.task_id)
            self._trim_locked()
            self._condition.notify_all()
        return task

    def poll(self, node_id: str, *, wait_seconds: float = 0.0, live_node: Callable[[str], bool] | None = None) -> DeviceCapabilityTask | None:
        node_id = str(node_id or "").strip()
        try:
            timeout = max(0.0, min(25.0, float(wait_seconds)))
        except (TypeError, ValueError):
            timeout = 0.0
        deadline = monotonic() + timeout
        with self._condition:
            while True:
                self._enforce_execution_policy("device_task.claim")
                self._expire_locked()
                validator = live_node or self._live_node
                if validator is not None and not validator(node_id):
                    if self._live_node is None or not self._live_node(node_id):
                        self._expire_pending_for_node_locked(node_id, reason="Capability node became unavailable before task delivery.")
                    raise PermissionError(f"Capability node is not live: {node_id}")
                for task_id in self._order:
                    task = self._tasks.get(task_id)
                    if task is None or task.selected_node_id != node_id or task.status != "queued" or task.claimed:
                        continue
                    task.claimed = True
                    task.status = "claimed"
                    task.claimed_monotonic = monotonic()
                    task.updated_at = _utc_now()
                    return task
                remaining = deadline - monotonic()
                if remaining <= 0.0:
                    return None
                self._condition.wait(timeout=remaining)

    def complete(self, *, node_id: str, task_id: str, status: str, result: dict[str, Any] | None = None, error: str = "", live_node: Callable[[str], bool] | None = None) -> DeviceCapabilityTask:
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in {"completed", "rejected", "failed"}:
            raise ValueError("Task completion status must be completed, rejected, or failed.")
        with self._lock:
            self._expire_locked()
            task = self._tasks.get(str(task_id))
            if task is None:
                raise KeyError(f"Unknown capability task: {task_id}")
            if task.selected_node_id != str(node_id):
                raise PermissionError("A capability task may only be completed by its selected node.")
            validator = live_node or self._live_node
            if validator is not None and not validator(str(node_id)):
                if self._live_node is None or not self._live_node(str(node_id)):
                    self._expire_pending_for_node_locked(str(node_id), reason="Capability node became unavailable before task completion.")
                raise PermissionError(f"Capability node is not live: {node_id}")
            if task.status in _TERMINAL_STATUSES:
                return task

            raw_result = dict(result or {})
            resource_payload = raw_result.pop("_resource", None)
            if resource_payload is not None:
                try:
                    if not isinstance(resource_payload, dict) or len(resource_payload) > 8:
                        raise ValueError("resource telemetry must be a small JSON object")
                    self.update_resource_telemetry(task.selected_node_id, resource_payload)
                except (TypeError, ValueError):
                    self._resource_rejections += 1

            claimed_at = task.claimed_monotonic
            task.status = normalized_status
            task.claimed = True
            task.result = _sanitize_task_result(task.capability, raw_result) if normalized_status == "completed" else {}
            task.error = _clean_text(error, 500)
            task.claimed_monotonic = None
            task.updated_at = _utc_now()

            if claimed_at is not None and normalized_status in {"completed", "failed"}:
                self._benchmark_book.record(BenchmarkSample(
                    node_id=task.selected_node_id,
                    capability=task.capability,
                    operation=task.operation,
                    latency_ms=max(0.0, (monotonic() - claimed_at) * 1000.0),
                    success=normalized_status == "completed",
                ))
            self._condition.notify_all()
            return task

    def expire_pending_for_node(self, node_id: str, *, reason: str = "Capability node is unavailable.") -> int:
        clean_node_id = str(node_id or "").strip()
        with self._condition:
            return self._expire_pending_for_node_locked(clean_node_id, reason=reason)

    def _expire_pending_for_node_locked(self, node_id: str, *, reason: str) -> int:
        expired = 0
        for task in self._tasks.values():
            if task.selected_node_id != node_id or task.status in _TERMINAL_STATUSES:
                continue
            task.status = "expired"
            task.claimed = True
            task.claimed_monotonic = None
            task.error = _clean_text(reason, 500)
            task.updated_at = _utc_now()
            expired += 1
        if expired:
            self._condition.notify_all()
        return expired

    def _follow_replacement_locked(self, task: DeviceCapabilityTask | None) -> DeviceCapabilityTask | None:
        seen: set[str] = set()
        current = task
        while current is not None and current.replacement_task_id:
            if current.task_id in seen:
                break
            seen.add(current.task_id)
            replacement = self._tasks.get(current.replacement_task_id)
            if replacement is None:
                break
            current = replacement
        return current

    def wait_for_terminal(self, task_id: str, *, timeout_seconds: float) -> DeviceCapabilityTask | None:
        try:
            timeout = max(0.0, min(240.0, float(timeout_seconds)))
        except (TypeError, ValueError):
            timeout = 0.0
        deadline = monotonic() + timeout
        task_key = str(task_id)
        with self._condition:
            while True:
                self._expire_locked()
                task = self._follow_replacement_locked(self._tasks.get(task_key))
                if task is None or task.status in _TERMINAL_STATUSES:
                    return task
                remaining = deadline - monotonic()
                if remaining <= 0.0:
                    return task
                self._condition.wait(timeout=remaining)

    def get(self, task_id: str) -> DeviceCapabilityTask | None:
        with self._lock:
            self._expire_locked()
            return self._tasks.get(str(task_id))

    def compute_status(self) -> dict[str, Any]:
        with self._lock:
            self._expire_locked()
            benchmark_snapshot = self._benchmark_book.snapshot()
            resource_nodes = {
                node_id for node_id in self._resources
                if self._resource_for(node_id) is not None
            }
            active_node_ids = resource_nodes | {
                task.selected_node_id
                for task in self._tasks.values()
                if task.status == "claimed"
            }
            live_loads = self._active_loads(active_node_ids)
            return {
                "version": self.VERSION,
                "scheduler": "home_compute_scheduler",
                "sample_count": len(benchmark_snapshot.get("samples", [])),
                "benchmarks": benchmark_snapshot,
                "live_load": {
                    node_id: {
                        "active_realtime": load.active_realtime,
                        "active_background": load.active_background,
                        "memory_fraction": load.memory_fraction,
                        "accelerator_fraction": load.accelerator_fraction,
                        "stream_critical": load.stream_critical,
                    }
                    for node_id, load in sorted(live_loads.items())
                },
                "resource_reports": len(resource_nodes),
                "resource_rejections": self._resource_rejections,
                "resource_ttl_seconds": self.resource_ttl_seconds,
                "authority": "operational_hint_only",
                "content_retained": False,
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._expire_locked()
            tasks = [self._tasks[task_id].to_dict() for task_id in self._order if task_id in self._tasks]
        return {
            "version": self.VERSION,
            "tasks": tasks[-50:],
            "queued": sum(1 for item in tasks if item["status"] == "queued"),
            "claimed": sum(1 for item in tasks if item["status"] == "claimed"),
            "claim_lease_seconds": self.claim_lease_seconds,
            "max_claim_attempts": self.max_claim_attempts,
            "replay_safe_capabilities": sorted(_REPLAY_SAFE_CAPABILITIES),
            "scheduler_samples": self.compute_status()["sample_count"],
            "policy": "typed device tasks; measured execution, claimed work, and fresh bounded resource pressure may improve node selection; permissions remain device-local",
        }

    def _rollover_claim_locked(self, task: DeviceCapabilityTask) -> DeviceCapabilityTask | None:
        if task.capability not in _REPLAY_SAFE_CAPABILITIES or task.attempt >= self.max_claim_attempts:
            return None
        replacement = DeviceCapabilityTask(
            task_id=f"capability_task_{uuid4().hex}",
            capability=task.capability,
            intent=task.intent,
            args=dict(task.args),
            requester_device_id=task.requester_device_id,
            selected_node_id=task.selected_node_id,
            attempt=task.attempt + 1,
            root_task_id=task.root_task_id,
            operation=task.operation,
        )
        self._tasks[replacement.task_id] = replacement
        self._order.append(replacement.task_id)
        task.replacement_task_id = replacement.task_id
        return replacement

    def _expire_locked(self) -> None:
        now = monotonic()
        changed = False
        for node_id, (measured_at, _report) in list(self._resources.items()):
            if now - measured_at > self.resource_ttl_seconds:
                self._resources.pop(node_id, None)
        for task in list(self._tasks.values()):
            if task.status in _TERMINAL_STATUSES:
                continue
            unavailable = self._live_node is not None and not self._live_node(task.selected_node_id)
            if unavailable or now - task.created_monotonic > self.ttl_seconds:
                task.status = "expired"
                task.claimed = True
                task.claimed_monotonic = None
                task.error = "Capability node became unavailable before task completion." if unavailable else "Capability task expired before completion."
                task.updated_at = _utc_now()
                changed = True
                continue

            lease_expired = (
                task.status == "claimed"
                and task.claimed_monotonic is not None
                and now - task.claimed_monotonic > self.claim_lease_seconds
            )
            if not lease_expired:
                continue

            replacement = self._rollover_claim_locked(task)
            task.status = "expired"
            task.claimed = True
            task.claimed_monotonic = None
            task.error = (
                "Capability task claim lease expired; replay-safe work was rolled over."
                if replacement is not None
                else "Capability task claim lease expired; unsafe or exhausted work was not replayed."
            )
            task.updated_at = _utc_now()
            changed = True
        if changed:
            self._trim_locked()
            self._condition.notify_all()

    def _trim_locked(self) -> None:
        while len(self._order) > self.max_tasks:
            task_id = self._order.pop(0)
            self._tasks.pop(task_id, None)


def preview_capability_task(registry: NodeRegistry, *, capability: str, intent: str, requester_device_id: str) -> CapabilityTaskPlan:
    """Create a route plan only. This function can never execute a task."""
    route = registry.route_preview(capability)
    selected = route.get("selected_node_id")
    clean_intent = _clean_text(intent, 500)
    return CapabilityTaskPlan(
        task_id=f"capability_task_{uuid4().hex}",
        capability=str(capability).strip().lower()[:80],
        intent=clean_intent,
        requester_device_id=str(requester_device_id or "unknown-device")[:160],
        selected_node_id=str(selected) if selected else None,
        status="route_candidate" if selected else "no_capable_node",
        execution_authorized=False,
        execution_endpoint=None,
        created_at=_utc_now(),
    )