"""MaryV2 13.2 unified authoritative core service.

This is the host-independent ownership boundary for one live Mary runtime.
Clients and transports talk to this service; they do not construct their own
Mary coordinator.  The underlying MaryApplication remains the persistence-aware
composition root, so 13.2 consolidates ownership without rewriting Mary's
existing cognition, memory, relationship, growth, routing, or realtime systems.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from threading import RLock
from time import monotonic
from typing import Any
from uuid import uuid4

from mary.distributed import CapabilityDescriptor, DeviceTaskBroker, NodeDescriptor, preview_capability_task
from mary.protocol.models import (
    CapabilityRouteRequest,
    CapabilityTaskDispatchRequest,
    CapabilityTaskPreviewRequest,
    NodeHeartbeatRequest,
    NodeRegistrationRequest,
    NodeTaskCompletionRequest,
    NodeTaskPollRequest,
    RuntimeActionRequest,
    TurnRequest,
    TurnResponse,
    WorkspaceActionRequest,
)
from mary.runtime.application import MaryApplication, create_application


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


@dataclass(frozen=True)
class CoreIdentity:
    service: str = "mary-core"
    protocol_version: str = "1"
    mary_architecture: str = "13.2"


class MaryCoreService:
    """Own exactly one long-lived canonical ``MaryApplication``.

    The lock intentionally serializes creator turns. Mary is currently a
    single-user evolving character whose state-changing turn pipeline was not
    designed for concurrent writes. Serializing here makes that invariant
    explicit and keeps every transport on one turn pipeline.
    """

    def __init__(
        self,
        application: MaryApplication | None = None,
        *,
        instance_id: str | None = None,
    ) -> None:
        self.application = application or create_application(name="mary_core")
        self.mary = self.application.mary
        self.identity = CoreIdentity()
        self.instance_id = str(instance_id or uuid4())
        self.started_monotonic = monotonic()
        self._turn_lock = RLock()
        self.device_tasks = DeviceTaskBroker()
        self._closed = False

    def process_turn(self, request: TurnRequest | dict[str, Any]) -> TurnResponse:
        if self._closed:
            raise RuntimeError("Mary Core is closed.")
        turn = request if isinstance(request, TurnRequest) else TurnRequest.from_dict(request)

        with self._turn_lock:
            before = self._state_fingerprint()
            if turn.requested_mode:
                self.mary.engagement.set_mode(turn.requested_mode)

            result = self.application.run(
                turn.text,
                metadata={
                    "surface": turn.surface or "client",
                    "transport": "core",
                    "conversation_id": turn.conversation_id,
                    "device_id": turn.device_id,
                    "requested_mode": turn.requested_mode,
                    "voice_input": bool(turn.voice_input),
                },
            )
            if not result.success:
                raise RuntimeError(result.error or "Mary's canonical turn pipeline failed.")

            after = self._state_fingerprint()
            conversation = self.conversation_status()
            engagement = dict(conversation.get("engagement", {}) or {})
            last_plan = dict(engagement.get("last_plan", {}) or {})
            response_text = str(result.output or "")

            return TurnResponse(
                response=response_text,
                conversation_id=turn.conversation_id,
                turn_id=str(result.turn_id or ""),
                effective_mode=str(last_plan.get("effective_mode") or engagement.get("mode") or "adaptive"),
                provenance=self._provenance(result),
                state_changes=self._state_changes(before, after),
                conversation_state=conversation,
                display_hints=self._display_hints(result),
            )

    def health(self) -> dict[str, Any]:
        return {
            "ok": not self._closed,
            "service": self.identity.service,
            "protocol_version": self.identity.protocol_version,
            "architecture": self.identity.mary_architecture,
            "instance_id": self.instance_id,
            "uptime_seconds": round(max(0.0, monotonic() - self.started_monotonic), 2),
        }

    def state(self) -> dict[str, Any]:
        mind = getattr(self.mary, "mind", None)
        retrieval = getattr(mind, "retrieval", None)
        perception = getattr(self.mary, "perception_director", None)

        return _json_safe({
            "core": self.health(),
            "mary": self.mary.live_state(runtime_status="idle"),
            "runtime": self.application.state.to_dict(),
            "environment": self.mary.runtime_environment.snapshot(),
            "nodes": self.mary.node_registry.snapshot(),
            "mind": (
                mind.status()
                if callable(getattr(mind, "status", None))
                else {"enabled": False}
            ),
            "retrieval": (
                retrieval.status()
                if callable(getattr(retrieval, "status", None))
                else {"enabled": False}
            ),
            "perception": (
                perception.snapshot()
                if callable(getattr(perception, "snapshot", None))
                else {"enabled": False}
            ),
        })

    def dashboard_status(self) -> dict[str, Any]:
        """Return the existing display-safe dashboard from canonical Mary."""

        from mary.desktop.dashboard import build_desktop_dashboard_state

        try:
            payload = build_desktop_dashboard_state(
                self.mary,
                runtime_status="idle",
            )
        except Exception:
            payload = {"live": self.mary.live_state(runtime_status="idle")}

        ecosystem = getattr(self.application, "ecosystem", None)
        workspace_snapshot = getattr(ecosystem, "workspace_snapshot", None)
        payload["ecosystem"] = (
            workspace_snapshot()
            if callable(workspace_snapshot)
            else {}
        )
        state = self.state()
        payload["mind"] = state.get("mind", {})
        payload["realtime"] = self.conversation_status().get("realtime", {})
        payload["nodes"] = state.get("nodes", {})
        payload["retrieval"] = state.get("retrieval", {})
        payload["perception"] = state.get("perception", {})
        return _json_safe(payload)

    def memory_status(self) -> dict[str, Any]:
        lifecycle = getattr(self.mary, "memory_lifecycle_status", None)
        if callable(lifecycle):
            return _json_safe(lifecycle())
        return _json_safe(self.mary.memory.status())

    def conversation_status(self) -> dict[str, Any]:
        dialogue = getattr(
            self.mary,
            "dialogue",
            None,
        )
        session_status = getattr(
            dialogue,
            "session_status",
            None,
        )

        return _json_safe({
            "engagement": self.mary.engagement.status(),
            "dialogue": (
                session_status()
                if callable(session_status)
                else {}
            ),
            "realtime": self.mary.realtime.status(),
        })

    def growth_status(self) -> dict[str, Any]:
        return _json_safe(self.mary.growth.status())

    def node_status(self) -> dict[str, Any]:
        return _json_safe(self.mary.node_registry.snapshot())

    def register_node(
        self,
        request: NodeRegistrationRequest | dict[str, Any],
    ) -> dict[str, Any]:
        """Register or refresh one replaceable device capability node.

        Registration is an authenticated capability advertisement. It does not
        transfer Mary identity/state ownership and it does not authorize task
        execution on the device.
        """

        if self._closed:
            raise RuntimeError("Mary Core is closed.")
        model = (
            request
            if isinstance(request, NodeRegistrationRequest)
            else NodeRegistrationRequest.from_dict(request)
        )
        capabilities = [CapabilityDescriptor.from_dict(item) for item in model.capabilities]
        descriptor = NodeDescriptor(
            node_id=model.node_id,
            display_name=model.display_name,
            role="capability_node",
            host_type=model.host_type,
            platform=model.platform,
            surface=model.surface,
            transport="mary_protocol",
            capabilities={item.name: item for item in capabilities},
            local=bool(model.local),
            trusted=True,
            execution_policy="authorization_required",
        )
        with self._turn_lock:
            registered = self.mary.node_registry.register(descriptor)
            return _json_safe({
                "ok": True,
                "node": registered.to_dict(stale_after=self.mary.node_registry.stale_after),
                "registry": self.mary.node_registry.snapshot(),
            })

    def heartbeat_node(
        self,
        request: NodeHeartbeatRequest | dict[str, Any],
    ) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("Mary Core is closed.")
        model = (
            request
            if isinstance(request, NodeHeartbeatRequest)
            else NodeHeartbeatRequest.from_dict(request)
        )
        with self._turn_lock:
            if not self.mary.node_registry.heartbeat(model.node_id):
                raise KeyError(f"Unknown capability node: {model.node_id}")
            node = self.mary.node_registry.get(model.node_id)
            return _json_safe({
                "ok": True,
                "node": node.to_dict(stale_after=self.mary.node_registry.stale_after) if node else {},
            })

    def disconnect_node(
        self,
        request: NodeHeartbeatRequest | dict[str, Any],
    ) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("Mary Core is closed.")
        model = (
            request
            if isinstance(request, NodeHeartbeatRequest)
            else NodeHeartbeatRequest.from_dict(request)
        )
        with self._turn_lock:
            changed = self.mary.node_registry.disconnect(model.node_id)
            return _json_safe({
                "ok": changed,
                "node_id": model.node_id,
                "connected": False,
            })

    def route_capability(
        self,
        request: CapabilityRouteRequest | dict[str, Any],
    ) -> dict[str, Any]:
        model = (
            request
            if isinstance(request, CapabilityRouteRequest)
            else CapabilityRouteRequest.from_dict(request)
        )
        with self._turn_lock:
            return _json_safe(
                self.mary.node_registry.route_preview(
                    model.capability,
                    prefer_private=model.prefer_private,
                    prefer_local=model.prefer_local,
                )
            )

    def preview_capability_task(
        self,
        request: CapabilityTaskPreviewRequest | dict[str, Any],
    ) -> dict[str, Any]:
        """Return a non-executing dispatch plan for a capability request."""

        model = (
            request
            if isinstance(request, CapabilityTaskPreviewRequest)
            else CapabilityTaskPreviewRequest.from_dict(request)
        )
        with self._turn_lock:
            plan = preview_capability_task(
                self.mary.node_registry,
                capability=model.capability,
                intent=model.intent,
                requester_device_id=model.device_id,
            )
            return _json_safe({
                "ok": True,
                "plan": plan.to_dict(),
                "execution": {
                    "authorized": False,
                    "endpoint": None,
                    "policy": "preview only; no device task was executed",
                },
            })

    def dispatch_capability_task(
        self,
        request: CapabilityTaskDispatchRequest | dict[str, Any],
    ) -> dict[str, Any]:
        """Queue one narrowly typed task for a selected device node.

        Core chooses the node, but the device still decides whether local
        permission authorizes execution. No shell or arbitrary command payload
        exists in this contract.
        """

        if self._closed:
            raise RuntimeError("Mary Core is closed.")
        model = (
            request
            if isinstance(request, CapabilityTaskDispatchRequest)
            else CapabilityTaskDispatchRequest.from_dict(request)
        )
        with self._turn_lock:
            task = self.device_tasks.enqueue(
                self.mary.node_registry,
                capability=model.capability,
                intent=model.intent,
                args=model.args,
                requester_device_id=model.device_id,
            )
            return _json_safe({
                "ok": True,
                "task": task.to_dict(),
                "execution": {
                    "authorized_by_core": False,
                    "device_permission_required": True,
                    "policy": "typed task queued; selected device controls local execution permission",
                },
            })

    def poll_capability_task(
        self,
        request: NodeTaskPollRequest | dict[str, Any],
    ) -> dict[str, Any]:
        model = (
            request
            if isinstance(request, NodeTaskPollRequest)
            else NodeTaskPollRequest.from_dict(request)
        )
        with self._turn_lock:
            node = self.mary.node_registry.get(model.node_id)
            if node is None:
                raise KeyError(f"Unknown capability node: {model.node_id}")
            task = self.device_tasks.poll(model.node_id)
            return _json_safe({
                "ok": True,
                "task": task.to_dict() if task is not None else None,
            })

    def complete_capability_task(
        self,
        request: NodeTaskCompletionRequest | dict[str, Any],
    ) -> dict[str, Any]:
        model = (
            request
            if isinstance(request, NodeTaskCompletionRequest)
            else NodeTaskCompletionRequest.from_dict(request)
        )
        with self._turn_lock:
            task = self.device_tasks.complete(
                node_id=model.node_id,
                task_id=model.task_id,
                status=model.status,
                result=model.result,
                error=model.error,
            )
            return _json_safe({"ok": True, "task": task.to_dict()})

    def capability_task_status(self, task_id: str) -> dict[str, Any]:
        with self._turn_lock:
            task = self.device_tasks.get(task_id)
            if task is None:
                raise KeyError(f"Unknown capability task: {task_id}")
            return _json_safe({"ok": True, "task": task.to_dict()})

    def workspace_status(self) -> dict[str, Any]:
        """Return the canonical remote-safe Mary workspace snapshot."""

        with self._turn_lock:
            return _json_safe(
                self.application.ecosystem.workspace_snapshot()
            )

    def workspace_action(
        self,
        request: WorkspaceActionRequest | dict[str, Any],
    ) -> dict[str, Any]:
        """Apply one bounded canonical workspace mutation.

        Workspace writes share the same lock as conversation turns so the Core
        remains the single writer for canonical state. Device-local abilities
        are deliberately not exposed here.
        """

        if self._closed:
            raise RuntimeError("Mary Core is closed.")

        action = (
            request
            if isinstance(request, WorkspaceActionRequest)
            else WorkspaceActionRequest.from_dict(request)
        )

        with self._turn_lock:
            result = self.application.ecosystem.apply_workspace_action(
                action.action,
                action.args,
                source=f"mary_protocol:{action.device_id}",
            )
            return _json_safe({
                **dict(result or {}),
                "workspace": self.application.ecosystem.workspace_snapshot(),
            })

    def runtime_action(
        self,
        request: RuntimeActionRequest | dict[str, Any],
    ) -> dict[str, Any]:
        """Apply bounded conversation/realtime control on canonical Mary."""

        if self._closed:
            raise RuntimeError("Mary Core is closed.")
        action = (
            request
            if isinstance(request, RuntimeActionRequest)
            else RuntimeActionRequest.from_dict(request)
        )
        values = dict(action.args or {})

        with self._turn_lock:
            if action.action == "conversation.set_mode":
                mode = str(values.get("mode") or "adaptive")
                return _json_safe(self.mary.engagement.set_mode(mode))

            if action.action == "conversation.begin_session":
                mode = str(values.get("mode") or "engaged")
                turns = max(1, min(100, int(values.get("turns", 8))))
                self.mary.engagement.begin_session(
                    mode,
                    turns=turns,
                    reason=f"protocol:{action.device_id}",
                )
                return _json_safe(self.mary.engagement.status())

            if action.action == "conversation.end_session":
                self.mary.engagement.end_session()
                return _json_safe(self.mary.engagement.status())

            if action.action == "realtime.speech_started":
                self.mary.realtime.speech_started(
                    turn_id=str(values.get("turn_id") or "") or None,
                    source=f"protocol:{action.device_id}",
                )
                return _json_safe(self.mary.realtime.status())

            if action.action == "realtime.speech_ended":
                self.mary.realtime.speech_ended(
                    reason=str(values.get("reason") or "speech_finished")
                )
                return _json_safe(self.mary.realtime.status())

            if action.action == "realtime.interrupt":
                reason = str(values.get("reason") or "client_barge_in")
                self.mary.realtime.interrupt(
                    reason=reason,
                    by_source=f"protocol:{action.device_id}",
                )
                self.mary.realtime.speech_ended(reason="interrupted")
                return _json_safe(self.mary.realtime.status())

            if action.action == "realtime.listening":
                self.mary.realtime.mark_listening(
                    bool(values.get("active", False)),
                    source=f"protocol:{action.device_id}",
                )
                return _json_safe(self.mary.realtime.status())

            if action.action == "realtime.transcribing":
                self.mary.realtime.mark_transcribing(
                    bool(values.get("active", False)),
                    source=f"protocol:{action.device_id}",
                )
                return _json_safe(self.mary.realtime.status())

            if action.action == "mind.rebuild_reservoir":
                records = int(self.mary.mind.rebuild_reservoir())
                return _json_safe({
                    "ok": True,
                    "records": records,
                    "status": self.mary.mind.status(),
                })

            if action.action == "mind.maintenance":
                return _json_safe(self.mary.mind.maintenance())

            if action.action == "presence.idle_tick":
                return _json_safe(
                    self.application.ecosystem.presence.idle_tick(
                        focus_active=bool(values.get("focus_active", False))
                    )
                )

        raise ValueError(f"Unsupported runtime action: {action.action}")

    def save(self) -> bool:
        with self._turn_lock:
            return bool(self.application.save())

    def close(self) -> bool:
        with self._turn_lock:
            if self._closed:
                return True
            saved = bool(self.application.close())
            self._closed = True
            return saved

    def _state_fingerprint(self) -> dict[str, Any]:
        memory = _json_safe(self.mary.memory.status())
        relationship = _json_safe(self.mary.relationship.governance_status())
        growth = _json_safe(self.mary.growth.status())
        return {"memory": memory, "relationship": relationship, "growth": growth}

    @staticmethod
    def _state_changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        changes: dict[str, Any] = {}
        for key in ("memory", "relationship", "growth"):
            if before.get(key) != after.get(key):
                changes[key] = {"changed": True, "current": deepcopy(after.get(key))}
        return changes

    @staticmethod
    def _provenance(result: Any) -> dict[str, Any]:
        values = dict(getattr(result, "metadata", {}).get("pipeline_values", {}) or {})
        cycle = values.get("cognitive_cycle")
        reasoning = getattr(cycle, "reasoning", None)
        metadata = dict(getattr(reasoning, "metadata", {}) or {})
        return _json_safe({
            "provider": metadata.get("provider") or "local/system",
            "model": metadata.get("model"),
            "finish_reason": metadata.get("finish_reason"),
            "route": metadata.get("route") or metadata.get("generation_purpose"),
            "provider_attempts": metadata.get("provider_attempts", []),
            "self_grounded": bool(metadata.get("self_grounded", False)),
            "usage": metadata.get("usage", {}),
        })

    def _display_hints(self, result: Any) -> dict[str, Any]:
        values = dict(getattr(result, "metadata", {}).get("pipeline_values", {}) or {})
        cycle = values.get("cognitive_cycle")
        cycle_metadata = dict(getattr(cycle, "metadata", {}) or {})
        try:
            emotion = self.mary.emotion.snapshot()
        except Exception:
            emotion = {}
        try:
            avatar = self.mary.avatar.state.to_dict()
        except Exception:
            avatar = {}
        result_metadata = dict(getattr(result, "metadata", {}) or {})
        dialogue_plan = dict(result_metadata.get("dialogue_plan", {}) or {})
        safe_dialogue_plan = {
            key: dialogue_plan.get(key)
            for key in (
                "drive",
                "stance",
                "tone",
                "emotional_color",
                "opening_style",
                "ending_style",
                "allow_question",
                "initiative",
                "pacing",
                "energy",
                "warmth",
                "spontaneity",
                "intimacy",
                "expressiveness",
            )
            if dialogue_plan.get(key) not in (None, "", [], {})
        }
        return _json_safe({
            "delivery_plan": cycle_metadata.get("delivery_plan", {}) or result_metadata.get("delivery_plan", {}),
            "dialogue_plan": safe_dialogue_plan,
            "realtime": result_metadata.get("realtime", {}),
            "emotion": emotion,
            "avatar": avatar,
        })
