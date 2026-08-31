"""Small transport-neutral Mary Protocol v1 data contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any
from uuid import uuid4

_ALLOWED_MODES = {"quick", "adaptive", "engaged", "deep"}
_NODE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")
_CAPABILITY_NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")


def _node_id(value: Any, *, field_name: str = "node_id") -> str:
    text = str(value or "").strip()
    if not _NODE_ID.fullmatch(text):
        raise ValueError(f"{field_name} contains unsupported characters or is too long.")
    return text


def _capability_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not _CAPABILITY_NAME.fullmatch(text):
        raise ValueError("capability must use lowercase letters, numbers, '.', '_' or '-'.")
    return text


@dataclass(frozen=True)
class TurnRequest:
    text: str
    conversation_id: str = field(default_factory=lambda: f"conversation_{uuid4().hex}")
    device_id: str = "unknown-device"
    surface: str = "client"
    voice_input: bool = False
    requested_mode: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TurnRequest":
        if not isinstance(payload, dict):
            raise ValueError("Turn request must be a JSON object.")
        text = str(payload.get("text") or "").strip()
        if not text:
            raise ValueError("text is required.")
        if len(text) > 32_000:
            raise ValueError("text exceeds the 32,000 character protocol limit.")
        conversation_id = str(payload.get("conversation_id") or f"conversation_{uuid4().hex}").strip()
        device_id = str(payload.get("device_id") or "unknown-device").strip()
        surface = str(payload.get("surface") or "client").strip().lower()[:64]
        voice_input = bool(payload.get("voice_input", False))
        mode_raw = payload.get("requested_mode")
        mode = str(mode_raw).strip().lower() if mode_raw is not None else None
        if mode and mode not in _ALLOWED_MODES:
            raise ValueError(f"requested_mode must be one of: {', '.join(sorted(_ALLOWED_MODES))}.")
        return cls(
            text=text,
            conversation_id=conversation_id[:160],
            device_id=device_id[:160],
            surface=surface or "client",
            voice_input=voice_input,
            requested_mode=mode,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TurnResponse:
    response: str
    conversation_id: str
    turn_id: str
    effective_mode: str
    provenance: dict[str, Any] = field(default_factory=dict)
    state_changes: dict[str, Any] = field(default_factory=dict)
    conversation_state: dict[str, Any] = field(default_factory=dict)
    display_hints: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ALLOWED_WORKSPACE_ACTIONS = {
    "command.add",
    "command.update",
    "focus.start",
    "focus.stop",
    "study.create_project",
    "study.add_card",
    "study.review_card",
    "research.create_thread",
    "research.add_note",
    "production.create",
    "production.set_stage",
    "production.add_asset",
    "production.review",
    "inbox.mark_read",
}


@dataclass(frozen=True)
class WorkspaceActionRequest:
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    device_id: str = "unknown-device"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkspaceActionRequest":
        if not isinstance(payload, dict):
            raise ValueError("Workspace action must be a JSON object.")

        action = str(payload.get("action") or "").strip().lower()
        if action not in _ALLOWED_WORKSPACE_ACTIONS:
            raise ValueError(
                "Unsupported workspace action. Allowed actions: "
                + ", ".join(sorted(_ALLOWED_WORKSPACE_ACTIONS))
            )

        args = payload.get("args") or {}
        if not isinstance(args, dict):
            raise ValueError("Workspace action args must be a JSON object.")

        if len(args) > 32:
            raise ValueError("Workspace action args exceed the protocol field limit.")

        device_id = str(payload.get("device_id") or "unknown-device").strip()[:160]

        return cls(
            action=action,
            args=dict(args),
            device_id=device_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ALLOWED_RUNTIME_ACTIONS = {
    "conversation.set_mode",
    "conversation.begin_session",
    "conversation.end_session",
    "realtime.speech_started",
    "realtime.speech_ended",
    "realtime.interrupt",
    "realtime.listening",
    "realtime.transcribing",
    "mind.rebuild_reservoir",
    "mind.maintenance",
    "llm.probe",
    "presence.idle_tick",
    "presence.pulse",
    "performance.context.status",
    "performance.context.set",
    "training.feedback.status",
    "training.dataset.preview",
    "production.jobs.preview",
    "integration.status",
    "training.feedback.record",
}


@dataclass(frozen=True)
class RuntimeActionRequest:
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    device_id: str = "unknown-device"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuntimeActionRequest":
        if not isinstance(payload, dict):
            raise ValueError("Runtime action must be a JSON object.")
        action = str(payload.get("action") or "").strip().lower()
        if action not in _ALLOWED_RUNTIME_ACTIONS:
            raise ValueError(
                "Unsupported runtime action. Allowed actions: "
                + ", ".join(sorted(_ALLOWED_RUNTIME_ACTIONS))
            )
        args = payload.get("args") or {}
        if not isinstance(args, dict):
            raise ValueError("Runtime action args must be a JSON object.")
        if len(args) > 24:
            raise ValueError("Runtime action args exceed the protocol field limit.")
        device_id = str(payload.get("device_id") or "unknown-device").strip()[:160]
        return cls(action=action, args=dict(args), device_id=device_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NodeRegistrationRequest:
    node_id: str
    display_name: str
    host_type: str
    platform: str
    surface: str
    capabilities: list[dict[str, Any]] = field(default_factory=list)
    local: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NodeRegistrationRequest":
        if not isinstance(payload, dict):
            raise ValueError("Node registration must be a JSON object.")
        node_id = _node_id(payload.get("node_id"))
        raw_capabilities = payload.get("capabilities") or []
        if not isinstance(raw_capabilities, list):
            raise ValueError("capabilities must be a JSON array.")
        if len(raw_capabilities) > 64:
            raise ValueError("capabilities exceeds the 64-item protocol limit.")

        capabilities: list[dict[str, Any]] = []
        for raw in raw_capabilities:
            if not isinstance(raw, dict):
                raise ValueError("Each capability must be a JSON object.")
            item = dict(raw)
            item["name"] = _capability_name(item.get("name"))
            metadata = item.get("metadata") or {}
            if not isinstance(metadata, dict):
                raise ValueError("Capability metadata must be a JSON object.")
            if len(metadata) > 16:
                raise ValueError("Capability metadata exceeds the 16-field limit.")
            item["metadata"] = dict(metadata)
            capabilities.append(item)

        return cls(
            node_id=node_id,
            display_name=str(payload.get("display_name") or node_id).strip()[:120] or node_id,
            host_type=str(payload.get("host_type") or "device").strip().lower()[:48] or "device",
            platform=str(payload.get("platform") or "unknown").strip().lower()[:48] or "unknown",
            surface=str(payload.get("surface") or "client").strip().lower()[:64] or "client",
            capabilities=capabilities,
            local=bool(payload.get("local", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NodeHeartbeatRequest:
    node_id: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NodeHeartbeatRequest":
        if not isinstance(payload, dict):
            raise ValueError("Node heartbeat must be a JSON object.")
        return cls(node_id=_node_id(payload.get("node_id")))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityRouteRequest:
    capability: str
    prefer_private: bool = True
    prefer_local: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CapabilityRouteRequest":
        if not isinstance(payload, dict):
            raise ValueError("Capability route request must be a JSON object.")
        return cls(
            capability=_capability_name(payload.get("capability")),
            prefer_private=bool(payload.get("prefer_private", True)),
            prefer_local=bool(payload.get("prefer_local", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityTaskPreviewRequest:
    capability: str
    intent: str
    device_id: str = "unknown-device"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CapabilityTaskPreviewRequest":
        if not isinstance(payload, dict):
            raise ValueError("Capability task preview must be a JSON object.")
        intent = " ".join(str(payload.get("intent") or "").split())
        if not intent:
            raise ValueError("intent is required.")
        if len(intent) > 500:
            raise ValueError("intent exceeds the 500 character preview limit.")
        return cls(
            capability=_capability_name(payload.get("capability")),
            intent=intent,
            device_id=str(payload.get("device_id") or "unknown-device").strip()[:160],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityTaskDispatchRequest:
    capability: str
    intent: str
    args: dict[str, Any] = field(default_factory=dict)
    device_id: str = "unknown-device"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CapabilityTaskDispatchRequest":
        if not isinstance(payload, dict):
            raise ValueError("Capability task dispatch must be a JSON object.")
        intent = " ".join(str(payload.get("intent") or "").split())
        if not intent:
            raise ValueError("intent is required.")
        if len(intent) > 500:
            raise ValueError("intent exceeds the 500 character dispatch limit.")
        args = payload.get("args") or {}
        if not isinstance(args, dict):
            raise ValueError("Capability task args must be a JSON object.")
        if len(args) > 8:
            raise ValueError("Capability task args exceed the 8-field limit.")
        return cls(
            capability=_capability_name(payload.get("capability")),
            intent=intent,
            args=dict(args),
            device_id=str(payload.get("device_id") or "unknown-device").strip()[:160],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NodeTaskPollRequest:
    node_id: str
    wait_seconds: float = 0.0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NodeTaskPollRequest":
        if not isinstance(payload, dict):
            raise ValueError("Node task poll must be a JSON object.")
        try:
            wait_seconds = float(payload.get("wait_seconds", 0.0) or 0.0)
        except (TypeError, ValueError) as exc:
            raise ValueError("wait_seconds must be numeric.") from exc
        return cls(
            node_id=_node_id(payload.get("node_id")),
            wait_seconds=max(0.0, min(25.0, wait_seconds)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NodeTaskCompletionRequest:
    node_id: str
    task_id: str
    status: str
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NodeTaskCompletionRequest":
        if not isinstance(payload, dict):
            raise ValueError("Node task completion must be a JSON object.")
        task_id = str(payload.get("task_id") or "").strip()
        if not task_id.startswith("capability_task_") or len(task_id) > 96:
            raise ValueError("task_id is invalid.")
        status = str(payload.get("status") or "").strip().lower()
        if status not in {"completed", "rejected", "failed"}:
            raise ValueError("status must be completed, rejected, or failed.")
        result = payload.get("result") or {}
        if not isinstance(result, dict):
            raise ValueError("result must be a JSON object.")
        if len(result) > 8:
            raise ValueError("result exceeds the 8-field limit.")
        items = result.get("items")
        if items is not None:
            if not isinstance(items, list) or len(items) > 12:
                raise ValueError("result items must be an array with at most 12 entries.")
            for item in items:
                if not isinstance(item, dict) or len(item) > 8:
                    raise ValueError("Each result item must be a small JSON object.")
        error = " ".join(str(payload.get("error") or "").split())[:500]
        return cls(
            node_id=_node_id(payload.get("node_id")),
            task_id=task_id,
            status=status,
            result=dict(result),
            error=error,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
