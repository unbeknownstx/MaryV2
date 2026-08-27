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

from mary.protocol.models import RuntimeActionRequest, TurnRequest, TurnResponse, WorkspaceActionRequest
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
        return _json_safe({
            "core": self.health(),
            "mary": self.mary.live_state(runtime_status="idle"),
            "runtime": self.application.state.to_dict(),
            "environment": self.mary.runtime_environment.snapshot(),
            "nodes": self.mary.node_registry.snapshot(),
        })

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

    @staticmethod
    def _display_hints(result: Any) -> dict[str, Any]:
        values = dict(getattr(result, "metadata", {}).get("pipeline_values", {}) or {})
        cycle = values.get("cognitive_cycle")
        cycle_metadata = dict(getattr(cycle, "metadata", {}) or {})
        return _json_safe({
            "delivery_plan": cycle_metadata.get("delivery_plan", {}),
            "realtime": getattr(result, "metadata", {}).get("realtime", {}),
        })
