"""MaryV2 runtime gateway shared by presentation clients.

The gateway is a thin authority boundary, not another Mary abstraction layer.
It lets a surface use the same small set of canonical operations whether it is
running in-process for explicit standalone development or connected to the
remote Mary Core.

Crucially, this module never constructs Mary or MaryApplication. A caller must
supply an existing application for standalone mode, while remote mode uses
MaryClient only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
from typing import Any, Protocol

from mary.distributed import CapabilityDescriptor, NodeDescriptor, preview_capability_task
from mary.protocol.client import MaryClient
from mary.runtime.application import MaryApplication


@dataclass(frozen=True)
class GatewayTurnResult:
    text: str
    conversation_id: str
    turn_id: str
    effective_mode: str = "adaptive"
    provenance: dict[str, Any] = field(default_factory=dict)
    state_changes: dict[str, Any] = field(default_factory=dict)
    conversation_state: dict[str, Any] = field(default_factory=dict)
    display_hints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MaryRuntimeGateway(Protocol):
    authority: str
    device_id: str
    surface: str

    def turn(
        self,
        text: str,
        *,
        conversation_id: str,
        requested_mode: str | None = None,
        voice_input: bool = False,
    ) -> GatewayTurnResult: ...

    def state(self) -> dict[str, Any]: ...
    def conversation(self) -> dict[str, Any]: ...
    def workspace(self) -> dict[str, Any]: ...
    def dashboard(self) -> dict[str, Any]: ...
    def workspace_action(
        self,
        action: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...
    def runtime_action(
        self,
        action: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...
    def nodes(self) -> dict[str, Any]: ...
    def register_node(
        self,
        *,
        display_name: str,
        host_type: str,
        platform: str,
        surface: str,
        capabilities: list[dict[str, Any]],
        local: bool = True,
    ) -> dict[str, Any]: ...
    def heartbeat_node(self) -> dict[str, Any]: ...
    def disconnect_node(self) -> dict[str, Any]: ...
    def route_capability(
        self,
        capability: str,
        *,
        prefer_private: bool = True,
        prefer_local: bool = True,
    ) -> dict[str, Any]: ...
    def preview_capability_task(self, capability: str, intent: str) -> dict[str, Any]: ...
    def dispatch_capability_task(self, capability: str, intent: str, args: dict[str, Any] | None = None) -> dict[str, Any]: ...
    def poll_capability_task(self, *, wait_seconds: float = 0.0) -> dict[str, Any]: ...
    def complete_capability_task(self, task_id: str, *, status: str, result: dict[str, Any] | None = None, error: str = "") -> dict[str, Any]: ...
    def capability_task_status(self, task_id: str) -> dict[str, Any]: ...


class LocalMaryGateway:
    """Gateway over an explicitly supplied in-process MaryApplication."""

    authority = "standalone_application"

    def __init__(
        self,
        application: MaryApplication,
        *,
        device_id: str = "local-device",
        surface: str = "standalone",
    ) -> None:
        if application is None:
            raise ValueError("LocalMaryGateway requires an existing MaryApplication.")
        self.application = application
        self.device_id = str(device_id or "local-device")
        self.surface = str(surface or "standalone")

    @property
    def mary(self):
        return self.application.mary

    def turn(
        self,
        text: str,
        *,
        conversation_id: str,
        requested_mode: str | None = None,
        voice_input: bool = False,
    ) -> GatewayTurnResult:
        if requested_mode:
            self.mary.engagement.set_mode(requested_mode)

        result = self.application.run(
            text,
            metadata={
                "surface": self.surface,
                "transport": "in_process",
                "conversation_id": conversation_id,
                "device_id": self.device_id,
                "requested_mode": requested_mode,
                "voice_input": bool(voice_input),
            },
        )

        if not result.success:
            raise RuntimeError(result.error or "Mary's standalone turn pipeline failed.")

        conversation = self.conversation()
        engagement = dict(conversation.get("engagement", {}) or {})
        plan = dict(engagement.get("last_plan", {}) or {})
        values = dict(getattr(result, "metadata", {}).get("pipeline_values", {}) or {})
        cycle = values.get("cognitive_cycle")
        cycle_metadata = dict(getattr(cycle, "metadata", {}) or {})
        reasoning = getattr(cycle, "reasoning", None)
        reasoning_metadata = dict(getattr(reasoning, "metadata", {}) or {})

        return GatewayTurnResult(
            text=str(result.output or ""),
            conversation_id=str(conversation_id),
            turn_id=str(result.turn_id or ""),
            effective_mode=str(
                plan.get("effective_mode")
                or engagement.get("mode")
                or "adaptive"
            ),
            provenance={
                "provider": reasoning_metadata.get("provider") or "local/system",
                "model": reasoning_metadata.get("model"),
                "route": reasoning_metadata.get("route") or reasoning_metadata.get("generation_purpose"),
                "provider_attempts": reasoning_metadata.get("provider_attempts", []),
            },
            conversation_state=conversation,
            display_hints={
                "delivery_plan": cycle_metadata.get("delivery_plan", {}),
                "realtime": getattr(result, "metadata", {}).get("realtime", {}),
            },
        )

    def state(self) -> dict[str, Any]:
        return {
            "authority": {
                "mode": self.authority,
                "surface": self.surface,
                "device_id": self.device_id,
            },
            "mary": self.mary.live_state(runtime_status="idle"),
            "runtime": self.application.state.to_dict(),
            "environment": self.mary.runtime_environment.snapshot(),
            "nodes": self.mary.node_registry.snapshot(),
        }

    def conversation(self) -> dict[str, Any]:
        dialogue = getattr(self.mary, "dialogue", None)
        session_status = getattr(dialogue, "session_status", None)
        return {
            "engagement": self.mary.engagement.status(),
            "dialogue": session_status() if callable(session_status) else {},
            "realtime": self.mary.realtime.status(),
        }

    def workspace(self) -> dict[str, Any]:
        return self.application.ecosystem.workspace_snapshot()

    def dashboard(self) -> dict[str, Any]:
        from mary.desktop.dashboard import build_desktop_dashboard_state

        payload = build_desktop_dashboard_state(
            self.mary,
            runtime_status="idle",
        )
        payload["ecosystem"] = self.application.ecosystem.snapshot()
        try:
            payload["mind"] = self.mary.mind.status()
        except Exception:
            payload["mind"] = {"enabled": False}
        payload["realtime"] = self.mary.realtime.status()
        payload["nodes"] = self.mary.node_registry.snapshot()
        payload["retrieval"] = self.mary.mind.retrieval.status()
        payload["perception"] = self.mary.perception_director.snapshot()
        return payload

    def workspace_action(
        self,
        action: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.application.ecosystem.apply_workspace_action(
            action,
            args,
            source=f"{self.surface}:{self.device_id}",
        )
        return {
            **dict(result or {}),
            "workspace": self.workspace(),
        }

    def runtime_action(
        self,
        action: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        values = dict(args or {})
        name = str(action or "").strip().lower()

        if name == "conversation.set_mode":
            return self.mary.engagement.set_mode(
                str(values.get("mode") or "adaptive")
            )
        if name == "conversation.begin_session":
            self.mary.engagement.begin_session(
                str(values.get("mode") or "engaged"),
                turns=max(1, min(100, int(values.get("turns", 8)))),
                reason=f"gateway:{self.device_id}",
            )
            return self.mary.engagement.status()
        if name == "conversation.end_session":
            self.mary.engagement.end_session()
            return self.mary.engagement.status()
        if name == "realtime.speech_started":
            self.mary.realtime.speech_started(
                turn_id=str(values.get("turn_id") or "") or None,
                source=f"gateway:{self.device_id}",
            )
            return self.mary.realtime.status()
        if name == "realtime.speech_ended":
            self.mary.realtime.speech_ended(
                reason=str(values.get("reason") or "speech_finished")
            )
            return self.mary.realtime.status()
        if name == "realtime.interrupt":
            self.mary.realtime.interrupt(
                reason=str(values.get("reason") or "client_barge_in"),
                by_source=f"gateway:{self.device_id}",
            )
            self.mary.realtime.speech_ended(reason="interrupted")
            return self.mary.realtime.status()
        raise ValueError(f"Unsupported runtime action: {name}")

    def nodes(self) -> dict[str, Any]:
        return self.mary.node_registry.snapshot()

    def register_node(
        self,
        *,
        display_name: str,
        host_type: str,
        platform: str,
        surface: str,
        capabilities: list[dict[str, Any]],
        local: bool = True,
    ) -> dict[str, Any]:
        parsed = [CapabilityDescriptor.from_dict(item) for item in list(capabilities or [])]
        descriptor = NodeDescriptor(
            node_id=self.device_id,
            display_name=str(display_name or self.device_id)[:120],
            role="capability_node",
            host_type=str(host_type or "device")[:48],
            platform=str(platform or "unknown")[:48],
            surface=str(surface or self.surface)[:64],
            transport="in_process",
            capabilities={item.name: item for item in parsed},
            local=bool(local),
            trusted=True,
            execution_policy="authorization_required",
        )
        node = self.mary.node_registry.register(descriptor)
        return {
            "ok": True,
            "node": node.to_dict(stale_after=self.mary.node_registry.stale_after),
            "registry": self.mary.node_registry.snapshot(),
        }

    def heartbeat_node(self) -> dict[str, Any]:
        if not self.mary.node_registry.heartbeat(self.device_id):
            raise KeyError(f"Unknown capability node: {self.device_id}")
        node = self.mary.node_registry.get(self.device_id)
        return {
            "ok": True,
            "node": node.to_dict(stale_after=self.mary.node_registry.stale_after) if node else {},
        }

    def disconnect_node(self) -> dict[str, Any]:
        changed = self.mary.node_registry.disconnect(self.device_id)
        return {"ok": changed, "node_id": self.device_id, "connected": False}

    def route_capability(
        self,
        capability: str,
        *,
        prefer_private: bool = True,
        prefer_local: bool = True,
    ) -> dict[str, Any]:
        return self.mary.node_registry.route_preview(
            capability,
            prefer_private=prefer_private,
            prefer_local=prefer_local,
        )

    def preview_capability_task(self, capability: str, intent: str) -> dict[str, Any]:
        plan = preview_capability_task(
            self.mary.node_registry,
            capability=capability,
            intent=intent,
            requester_device_id=self.device_id,
        )
        return {
            "ok": True,
            "plan": plan.to_dict(),
            "execution": {
                "authorized": False,
                "endpoint": None,
                "policy": "preview only; no device task was executed",
            },
        }

    def dispatch_capability_task(self, capability: str, intent: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        raise RuntimeError("Device task dispatch is a remote-Core capability; standalone mode has no device broker.")

    def poll_capability_task(self, *, wait_seconds: float = 0.0) -> dict[str, Any]:
        del wait_seconds
        raise RuntimeError("Device task polling is a remote-Core capability; standalone mode has no device broker.")

    def complete_capability_task(self, task_id: str, *, status: str, result: dict[str, Any] | None = None, error: str = "") -> dict[str, Any]:
        raise RuntimeError("Device task completion is a remote-Core capability; standalone mode has no device broker.")

    def capability_task_status(self, task_id: str) -> dict[str, Any]:
        raise RuntimeError("Device task status is a remote-Core capability; standalone mode has no device broker.")


class RemoteMaryGateway:
    """Gateway backed only by Mary Protocol; it owns no MaryApplication."""

    authority = "remote_mary_core"

    def __init__(
        self,
        client: MaryClient,
        *,
        surface: str = "client",
    ) -> None:
        self.client = client
        self.device_id = client.device_id
        self.surface = str(surface or "client")

    def turn(
        self,
        text: str,
        *,
        conversation_id: str,
        requested_mode: str | None = None,
        voice_input: bool = False,
    ) -> GatewayTurnResult:
        # Mary Protocol currently derives voice/device context at the transport
        # surface. Keep the argument in the common interface for Desktop/native
        # parity without inventing a second state owner here.
        response = self.client.turn(
            text,
            conversation_id=conversation_id,
            requested_mode=requested_mode,
            voice_input=bool(voice_input),
        )
        return GatewayTurnResult(
            text=response.response,
            conversation_id=response.conversation_id,
            turn_id=response.turn_id,
            effective_mode=response.effective_mode,
            provenance=dict(response.provenance or {}),
            state_changes=dict(response.state_changes or {}),
            conversation_state=dict(response.conversation_state or {}),
            display_hints=dict(response.display_hints or {}),
        )

    def state(self) -> dict[str, Any]:
        return self.client.state()

    def conversation(self) -> dict[str, Any]:
        return self.client.conversation_status()

    def workspace(self) -> dict[str, Any]:
        return self.client.workspace()

    def dashboard(self) -> dict[str, Any]:
        return self.client.dashboard()

    def workspace_action(
        self,
        action: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.client.workspace_action(action, args)

    def runtime_action(
        self,
        action: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.client.runtime_action(action, args)

    def nodes(self) -> dict[str, Any]:
        return self.client.nodes()

    def register_node(
        self,
        *,
        display_name: str,
        host_type: str,
        platform: str,
        surface: str,
        capabilities: list[dict[str, Any]],
        local: bool = True,
    ) -> dict[str, Any]:
        return self.client.register_node(
            display_name=display_name,
            host_type=host_type,
            platform=platform,
            surface=surface,
            capabilities=capabilities,
            local=local,
        )

    def heartbeat_node(self) -> dict[str, Any]:
        return self.client.heartbeat_node()

    def disconnect_node(self) -> dict[str, Any]:
        return self.client.disconnect_node()

    def route_capability(
        self,
        capability: str,
        *,
        prefer_private: bool = True,
        prefer_local: bool = True,
    ) -> dict[str, Any]:
        return self.client.route_capability(
            capability,
            prefer_private=prefer_private,
            prefer_local=prefer_local,
        )

    def preview_capability_task(self, capability: str, intent: str) -> dict[str, Any]:
        return self.client.preview_capability_task(capability, intent)

    def dispatch_capability_task(self, capability: str, intent: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.client.dispatch_capability_task(capability, intent, args)

    def poll_capability_task(self, *, wait_seconds: float = 0.0) -> dict[str, Any]:
        return self.client.poll_capability_task(wait_seconds=wait_seconds)

    def complete_capability_task(self, task_id: str, *, status: str, result: dict[str, Any] | None = None, error: str = "") -> dict[str, Any]:
        return self.client.complete_capability_task(task_id, status=status, result=result, error=error)

    def capability_task_status(self, task_id: str) -> dict[str, Any]:
        return self.client.capability_task_status(task_id)


def gateway_from_environment(
    *,
    application: MaryApplication | None = None,
    device_id: str = "python-client",
    surface: str = "client",
) -> MaryRuntimeGateway:
    """Resolve remote vs explicit standalone authority without constructing Mary."""

    core_url = os.getenv("MARY_CORE_URL", "").strip()
    core_token = os.getenv("MARY_CORE_TOKEN", "").strip()

    if core_url:
        if application is not None:
            raise RuntimeError(
                "MARY_CORE_URL selects remote client mode; do not supply a local "
                "MaryApplication because that would create ambiguous authority."
            )
        if not core_token:
            raise RuntimeError("MARY_CORE_TOKEN is required when MARY_CORE_URL is configured.")
        return RemoteMaryGateway(
            MaryClient(
                core_url,
                token=core_token,
                device_id=device_id,
                surface=surface,
            ),
            surface=surface,
        )

    if application is None:
        raise RuntimeError(
            "Standalone gateway mode requires an explicitly constructed "
            "MaryApplication. The gateway will not create Mary implicitly."
        )

    return LocalMaryGateway(
        application,
        device_id=device_id,
        surface=surface,
    )
