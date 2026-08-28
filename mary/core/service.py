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
import os
from typing import Any
from uuid import uuid4

from mary.distributed import CapabilityDescriptor, DeviceTaskBroker, NodeDescriptor, preview_capability_task
from mary.llm.interface import LLMMessage
from mary.llm.output_quality import inspect_output_quality
from mary.llm.providers.device_ollama import DeviceOllamaProvider
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
        self._device_ollama_provider: DeviceOllamaProvider | None = None
        self._attach_device_ollama_provider()
        self._closed = False

    def _attach_device_ollama_provider(self) -> None:
        """Let remote Core treat a connected Ollama node as provider ``ollama``.

        The router remains the single LLM policy owner. This adapter only makes
        the already-existing Ollama route executable on a replaceable device
        node when the cloud host itself has no Ollama server.
        """

        router = getattr(self.mary, "llm", None)
        registry = getattr(self.mary, "node_registry", None)
        register = getattr(router, "register_provider", None)
        if registry is None or not callable(register):
            return
        self._device_ollama_provider = DeviceOllamaProvider(registry, self.device_tasks)
        register("ollama", self._device_ollama_provider)

    def process_turn(self, request: TurnRequest | dict[str, Any]) -> TurnResponse:
        if self._closed:
            raise RuntimeError("Mary Core is closed.")
        turn = request if isinstance(request, TurnRequest) else TurnRequest.from_dict(request)

        with self._turn_lock:
            before = self._state_fingerprint()
            if turn.requested_mode:
                self.mary.engagement.set_mode(turn.requested_mode)

            pipeline_started = monotonic()
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
            pipeline_ms = (monotonic() - pipeline_started) * 1000.0
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
                display_hints=self._display_hints(
                    result,
                    pipeline_ms=pipeline_ms,
                ),
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

        compute_fabric = self.compute_fabric_status()
        return _json_safe({
            "core": self.health(),
            "mary": self.mary.live_state(runtime_status="idle"),
            "runtime": self.application.state.to_dict(),
            "environment": self.mary.runtime_environment.snapshot(),
            "nodes": compute_fabric.get("nodes", {}),
            "compute_fabric": compute_fabric,
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
            "performance_context": (
                self.mary.performance_context.status()
                if callable(getattr(getattr(self.mary, "performance_context", None), "status", None))
                else {"mode": "private", "enabled": False}
            ),
        })

    def compute_fabric_status(self) -> dict[str, Any]:
        """Return one display-safe view of engines, routes, nodes, and task flow.

        The view deliberately combines observability without combining
        authority: Core still owns Mary state, the LLM router owns model policy,
        and device nodes remain permission-bounded executors.
        """

        router = getattr(self.mary, "llm", None)
        routing_status = getattr(router, "routing_status", None)
        routing = routing_status() if callable(routing_status) else {}
        registry = getattr(self.mary, "node_registry", None)
        nodes = registry.snapshot() if callable(getattr(registry, "snapshot", None)) else {}
        tasks = self.device_tasks.snapshot()
        ollama_route = {}
        if registry is not None:
            preview = getattr(registry, "route_preview", None)
            if callable(preview):
                ollama_route = preview("llm.ollama")
        return _json_safe({
            "routing": routing,
            "nodes": nodes,
            "tasks": tasks,
            "capability_routes": {"llm.ollama": ollama_route},
            "private_route_ready": bool(ollama_route.get("available")),
            "authority": "mary_core",
            "policy": (
                "Capability availability is not execution authorization and never "
                "transfers Mary identity, relationship, memory, or agency ownership."
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
        payload["compute_fabric"] = state.get("compute_fabric", {})
        payload["retrieval"] = state.get("retrieval", {})
        payload["perception"] = state.get("perception", {})
        payload["performance_context"] = state.get("performance_context", {})
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
        node = self.mary.node_registry.get(model.node_id)
        if node is None:
            raise KeyError(f"Unknown capability node: {model.node_id}")
        task = self.device_tasks.poll(
            model.node_id,
            wait_seconds=model.wait_seconds,
        )
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
        task = self.device_tasks.complete(
            node_id=model.node_id,
            task_id=model.task_id,
            status=model.status,
            result=model.result,
            error=model.error,
        )
        return _json_safe({"ok": True, "task": task.to_dict()})

    def capability_task_status(self, task_id: str) -> dict[str, Any]:
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

            if action.action == "llm.probe":
                return _json_safe(self._probe_llm_provider(values))

            if action.action == "presence.idle_tick":
                return _json_safe(
                    self.application.ecosystem.presence.idle_tick(
                        focus_active=bool(values.get("focus_active", False))
                    )
                )

            if action.action == "performance.context.status":
                return _json_safe(self.mary.performance_context.status())

            if action.action == "performance.context.set":
                return _json_safe(
                    self.mary.performance_context.set_mode(
                        str(values.get("mode") or "private")
                    )
                )

            if action.action == "presence.pulse":
                return _json_safe(self._presence_pulse(values, device_id=action.device_id))

            if action.action == "training.feedback.status":
                return _json_safe(self.mary.training_feedback.status())

            if action.action == "training.feedback.record":
                tags = values.get("tags") or []
                if not isinstance(tags, (list, tuple)):
                    raise ValueError("training feedback tags must be a list")
                patterns = values.get("character_patterns") or []
                if not isinstance(patterns, (list, tuple)):
                    raise ValueError("training feedback character_patterns must be a list")
                record = self.mary.training_feedback.record(
                    rating=str(values.get("rating") or "neutral"),
                    user_text=str(values.get("user_text") or ""),
                    context_text=str(values.get("context_text") or ""),
                    assistant_text=str(values.get("assistant_text") or ""),
                    chosen_text=str(values.get("chosen_text") or values.get("correction_text") or ""),
                    source_kind=str(values.get("source_kind") or "creator_turn"),
                    input_authority=str(values.get("input_authority") or "creator"),
                    provider=str(values.get("provider") or "unknown"),
                    model=str(values.get("model") or "unknown"),
                    conversation_mode=str(values.get("conversation_mode") or "adaptive"),
                    performance_context=str(values.get("performance_context") or "private"),
                    character_patterns=list(patterns),
                    tags=list(tags),
                    note=str(values.get("note") or ""),
                    turn_id=str(values.get("turn_id") or ""),
                )
                return _json_safe({
                    "ok": True,
                    "id": record.id,
                    "status": self.mary.training_feedback.status(),
                })

        raise ValueError(f"Unsupported runtime action: {action.action}")

    def _presence_pulse(self, values: dict[str, Any], *, device_id: str) -> dict[str, Any]:
        """Expose MaryApplication's canonical Presence cycle over Core protocol.

        Presence policy lives in one place now.  Core only adds transport-safe
        display/provenance/state-change projections for remote clients.
        """

        before = self._state_fingerprint()
        pulse = dict(
            self.application.presence_pulse(
                surface=str(values.get("surface") or "presence")[:64],
                conversation_id=str(
                    values.get("conversation_id")
                    or self.mary.dialogue.DEFAULT_SESSION_ID
                )[:160],
                device_id=str(device_id or "unknown-device")[:160],
                surface_visible=bool(values.get("surface_visible", True)),
                focus_active=(
                    bool(values.get("focus_active"))
                    if "focus_active" in values
                    else None
                ),
            )
            or {}
        )

        if not bool(pulse.get("speak") or pulse.get("spoke")):
            # PipelineResult is an in-process object and must never leak through
            # the transport serialization boundary.
            pulse.pop("pipeline_result", None)
            pulse.setdefault("llm_calls", 0)
            return _json_safe(pulse)

        result = pulse.pop("pipeline_result", None)
        if result is None:
            return _json_safe({**pulse, "ok": False, "speak": False, "spoke": False, "reason": "presence_result_missing"})

        display = self._display_hints(result)
        cycle = None
        try:
            cycle = dict(getattr(result, "metadata", {}) or {}).get("pipeline_values", {}).get("cognitive_cycle")
        except Exception:
            cycle = None
        cycle_meta = dict(getattr(cycle, "metadata", {}) or {}) if cycle is not None else {}
        result_metadata = dict(getattr(result, "metadata", {}) or {})
        after = self._state_fingerprint()
        response_text = str(getattr(result, "output", "") or pulse.get("text") or "")

        return _json_safe({
            **pulse,
            "ok": True,
            "speak": True,
            "spoke": True,
            "text": response_text,
            "response": response_text,
            "turn_id": str(getattr(result, "turn_id", "") or pulse.get("turn_id") or ""),
            "display_hints": display,
            "performance_packet": display.get("performance_packet", {}),
            "provenance": self._provenance(result),
            "state_changes": self._state_changes(before, after),
            "conversation_state": self.conversation_status(),
            "handled_by": cycle_meta.get("handled_by") or result_metadata.get("handled_by"),
        })

    def _probe_llm_provider(self, values: dict[str, Any]) -> dict[str, Any]:
        """Run one bounded, non-state-mutating provider diagnostic.

        This intentionally bypasses Mary's turn pipeline so benchmarking an
        engine never creates relationship history, memories, growth evidence,
        or conversation state. It uses the exact provider objects owned by the
        canonical Core, including the connected-device Ollama adapter. Paid
        OpenAI is deliberately excluded.
        """

        provider_name = str(values.get("provider") or "").strip().lower()
        if provider_name not in {"groq", "gemini", "openrouter", "ollama"}:
            raise ValueError("llm.probe provider must be groq, gemini, openrouter, or ollama")

        purpose = str(values.get("purpose") or "conversation").strip().lower()
        if purpose not in {"social_instant", "conversation", "general"}:
            raise ValueError("llm.probe purpose must be social_instant, conversation, or general")

        profile = str(values.get("profile") or "latency").strip().lower()
        if profile not in {"latency", "conversation"}:
            raise ValueError("llm.probe profile must be latency or conversation")

        if profile == "conversation":
            prompt = (
                "A close collaborator says, 'I finally solved the bug that kept me up late.' "
                "Reply in exactly two natural sentences: acknowledge the moment and ask one "
                "grounded follow-up question. Do not mention being an AI or this benchmark."
            )
            temperature = 0.45
            max_tokens = 96
        else:
            prompt = "Reply with exactly: MARY ENGINE OK"
            temperature = 0.0
            max_tokens = 32

        router = getattr(self.mary, "llm", None)
        selector = getattr(router, "_get_provider_for_purpose", None)
        if router is None or not callable(selector):
            raise RuntimeError("Mary's LLM router is unavailable")

        selected = selector(provider_name, purpose)
        availability_started = monotonic()
        try:
            available = bool(selected.is_available())
        except Exception as exc:
            return {
                "ok": False,
                "status": "availability_error",
                "provider": provider_name,
                "purpose": purpose,
                "profile": profile,
                "error_type": type(exc).__name__,
                "availability_ms": round((monotonic() - availability_started) * 1000.0, 2),
            }

        availability_ms = (monotonic() - availability_started) * 1000.0
        if not available:
            return {
                "ok": False,
                "status": "unavailable",
                "provider": provider_name,
                "purpose": purpose,
                "profile": profile,
                "model": str(selected.model_name() or ""),
                "availability_ms": round(availability_ms, 2),
            }

        messages = [LLMMessage(role="user", content=prompt)]
        generation_started = monotonic()
        try:
            response = selected.generate(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            return {
                "ok": False,
                "status": "generation_error",
                "provider": provider_name,
                "purpose": purpose,
                "profile": profile,
                "model": str(selected.model_name() or ""),
                "error_type": type(exc).__name__,
                "availability_ms": round(availability_ms, 2),
                "generation_ms": round((monotonic() - generation_started) * 1000.0, 2),
            }

        generation_ms = (monotonic() - generation_started) * 1000.0
        content = str(response.content or "").strip()
        issue = inspect_output_quality(content, messages)
        return {
            "ok": issue is None,
            "status": "ok" if issue is None else "invalid_output",
            "provider": str(response.provider or provider_name),
            "model": str(response.model or selected.model_name() or ""),
            "purpose": purpose,
            "profile": profile,
            "availability_ms": round(availability_ms, 2),
            "generation_ms": round(generation_ms, 2),
            "usage": dict(response.usage or {}),
            "finish_reason": str(response.finish_reason or ""),
            "output_quality": None if issue is None else {
                "code": issue.code,
                "description": issue.description,
            },
            "content": content[:1200],
            "canonical_state_changed": False,
        }

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
            "conversation_lane": {
                "lane": str(
                    dict(metadata.get("conversation_lane", {}) or {}).get("lane")
                    or ""
                ),
            },
            "self_grounded": bool(metadata.get("self_grounded", False)),
            "usage": metadata.get("usage", {}),
        })

    def _display_hints(
        self,
        result: Any,
        *,
        pipeline_ms: float | None = None,
    ) -> dict[str, Any]:
        values = dict(getattr(result, "metadata", {}).get("pipeline_values", {}) or {})
        cycle = values.get("cognitive_cycle")
        cycle_metadata = dict(getattr(cycle, "metadata", {}) or {})
        raw_timings = dict(cycle_metadata.get("timings", {}) or {})
        timings: dict[str, float] = {}
        for name in (
            "context_ms",
            "intent_ms",
            "reasoning_ms",
            "reflection_ms",
            "response_select_ms",
            "cognition_total_ms",
        ):
            try:
                value = float(raw_timings.get(name))
            except (TypeError, ValueError):
                continue
            if value >= 0.0:
                timings[name] = round(value, 2)

        measured_pipeline_ms = pipeline_ms
        if measured_pipeline_ms is None:
            try:
                elapsed = getattr(result, "elapsed", None)
                measured_pipeline_ms = None if elapsed is None else float(elapsed) * 1000.0
            except (TypeError, ValueError):
                measured_pipeline_ms = None
        if measured_pipeline_ms is not None and measured_pipeline_ms >= 0.0:
            timings["pipeline_ms"] = round(float(measured_pipeline_ms), 2)
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
            "performance_packet": cycle_metadata.get("performance_packet", {}) or result_metadata.get("performance_packet", {}),
            "performance_context": cycle_metadata.get("performance_context", {}) or result_metadata.get("performance_context", {}),
            "dialogue_plan": safe_dialogue_plan,
            "timings": timings,
            "realtime": result_metadata.get("realtime", {}),
            "emotion": emotion,
            "avatar": avatar,
        })
