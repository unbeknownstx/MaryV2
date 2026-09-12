"""Bounded capability task planning and broker for MaryV2 device nodes.

Core may select a replaceable device node and queue a narrowly typed task, but
execution always occurs on the device under that device's local permission
policy.  There is intentionally no shell-command task type here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import Condition, RLock
from time import monotonic
from typing import Any, Callable
from uuid import uuid4

from .nodes import NodeRegistry
from .mcp_fabric import MCP_CAPABILITIES, sanitize_mcp_result, sanitize_mcp_task_args
from .sensors import SENSOR_CAPABILITIES, sanitize_sensor_result, sanitize_sensor_task_args


_ALLOWED_EXECUTION_CAPABILITIES = {"personal_search", "llm.ollama", "llm.llama_cpp", *MCP_CAPABILITIES, *SENSOR_CAPABILITIES}
_TERMINAL_STATUSES = {"completed", "rejected", "failed", "expired"}
ExecutionPolicy = Callable[[str], None]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _sanitize_task_args(capability: str, args: dict[str, Any] | None) -> dict[str, Any]:
    values = dict(args or {})
    if capability == "personal_search":
        query = _clean_text(values.get("query"), 500)
        if not query:
            raise ValueError("personal_search requires a non-empty query.")
        limit = int(values.get("limit", 8) or 8)
        return {"query": query, "limit": max(1, min(12, limit))}
    if capability in {"llm.ollama", "llm.llama_cpp"}:
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
            if len(content) > 12_000:
                raise ValueError(f"A single {provider_label} message exceeds the 12000 character limit.")
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
    raise ValueError(f"Capability execution is not supported: {capability}")


def _sanitize_task_result(capability: str, result: dict[str, Any] | None) -> dict[str, Any]:
    values = dict(result or {})
    if capability in MCP_CAPABILITIES:
        return sanitize_mcp_result(capability, values)
    if capability in SENSOR_CAPABILITIES:
        return sanitize_sensor_result(capability, values)
    if capability not in {"llm.ollama", "llm.llama_cpp"}:
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
    return {
        "content": content,
        "provider": "llama_cpp" if capability == "llm.llama_cpp" else "ollama",
        "model": str(values.get("model") or "unknown")[:160],
        "finish_reason": str(values.get("finish_reason") or "")[:80],
        "usage": safe_usage,
        "privacy": "generated on selected device; raw provider payload not retained by Core",
    }


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
    created_monotonic: float = field(default_factory=monotonic, repr=False)

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
        }


class DeviceTaskBroker:
    """Small in-memory Core broker for bounded device tasks.

    Device tasks are intentionally ephemeral. They are not Mary memories or
    canonical character state, and a Core restart may discard them.
    """

    VERSION = "13.12"

    def __init__(self, *, max_tasks: int = 200, ttl_seconds: float = 300.0, lifecycle_lock: RLock | None = None, live_node: Callable[[str], bool] | None = None, execution_policy: ExecutionPolicy | None = None) -> None:
        self.max_tasks = max(20, int(max_tasks))
        self.ttl_seconds = max(30.0, float(ttl_seconds))
        self._lock = lifecycle_lock or RLock()
        self._condition = Condition(self._lock)
        self._live_node = live_node
        self._execution_policy = execution_policy
        self._tasks: dict[str, DeviceCapabilityTask] = {}
        self._order: list[str] = []

    def set_execution_policy(self, policy: ExecutionPolicy | None) -> None:
        with self._condition:
            self._execution_policy = policy
            self._condition.notify_all()

    def _enforce_execution_policy(self, kind: str) -> None:
        if self._execution_policy is not None:
            self._execution_policy(kind)

    def enqueue(self, registry: NodeRegistry, *, capability: str, intent: str, args: dict[str, Any] | None, requester_device_id: str) -> DeviceCapabilityTask:
        normalized = str(capability or "").strip().lower()
        if normalized not in _ALLOWED_EXECUTION_CAPABILITIES:
            raise ValueError(f"Capability execution is not supported: {normalized}")
        with self._condition:
            self._enforce_execution_policy("device_task.enqueue")
            self._expire_locked()
            selected = registry.choose(normalized)
            if selected is None:
                raise LookupError(f"No connected node supports capability: {normalized}")
            task = DeviceCapabilityTask(
                task_id=f"capability_task_{uuid4().hex}",
                capability=normalized,
                intent=_clean_text(intent, 500),
                args=_sanitize_task_args(normalized, args),
                requester_device_id=_clean_text(requester_device_id or "unknown-device", 160),
                selected_node_id=selected.node_id,
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
            task.status = normalized_status
            task.claimed = True
            task.result = _sanitize_task_result(task.capability, result) if normalized_status == "completed" else {}
            task.error = _clean_text(error, 500)
            task.updated_at = _utc_now()
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
            task.error = _clean_text(reason, 500)
            task.updated_at = _utc_now()
            expired += 1
        if expired:
            self._condition.notify_all()
        return expired

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
                task = self._tasks.get(task_key)
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

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._expire_locked()
            tasks = [self._tasks[task_id].to_dict() for task_id in self._order if task_id in self._tasks]
        return {
            "version": self.VERSION,
            "tasks": tasks[-50:],
            "queued": sum(1 for item in tasks if item["status"] == "queued"),
            "claimed": sum(1 for item in tasks if item["status"] == "claimed"),
            "policy": "Core queues typed capability tasks; device-local permission controls execution",
        }

    def _expire_locked(self) -> None:
        now = monotonic()
        for task in self._tasks.values():
            if task.status in _TERMINAL_STATUSES:
                continue
            unavailable = self._live_node is not None and not self._live_node(task.selected_node_id)
            if unavailable or now - task.created_monotonic > self.ttl_seconds:
                task.status = "expired"
                task.claimed = True
                task.error = "Capability node became unavailable before task completion." if unavailable else "Capability task expired before completion."
                task.updated_at = _utc_now()
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
