"""MaryV2 13.2 unified authoritative core service.

This is the host-independent ownership boundary for one live Mary runtime.
Clients and transports talk to this service; they do not construct their own
Mary coordinator.  The underlying MaryApplication remains the persistence-aware
composition root, so 13.2 consolidates ownership without rewriting Mary's
existing cognition, memory, relationship, growth, routing, or realtime systems.
"""
from __future__ import annotations

from copy import deepcopy
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
from threading import RLock
from time import monotonic, time
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
from mary.runtime.persistence import atomic_write_json, load_json_recovering
from mary.runtime.turn_observability import (
    current_turn_trace,
    emit_core_started,
    observe_turn_stage,
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


@dataclass(frozen=True)
class CoreIdentity:
    service: str = "mary-core"
    protocol_version: str = "1"
    mary_architecture: str = "13.2"


@dataclass
class _EnrollmentGrant:
    node_id: str
    digest: str
    expires_monotonic: float
    expires_at_epoch: float
    expires_at: str
    remaining_uses: int
    issued_at: str
    grant_id: str


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
        enrollment_state_path: str | Path | None = None,
    ) -> None:
        self.application = application or create_application(name="mary_core")
        self.mary = self.application.mary
        self.identity = CoreIdentity()
        self.instance_id = str(instance_id or uuid4())
        self.started_monotonic = monotonic()
        self._turn_lock = RLock()
        self._recent_turn_traces: deque[dict[str, Any]] = deque(maxlen=40)
        emit_core_started(self.instance_id)
        registry = getattr(self.mary, "node_registry", None)
        if registry is None:
            raise RuntimeError("Mary Core requires a canonical node registry.")
        # Compatibility for narrow non-node test doubles; production registry
        # always provides this canonical shared lifecycle lock.
        self._node_lifecycle_lock = getattr(registry, "lifecycle_lock", RLock())
        self._node_live_validator = getattr(registry, "is_live", lambda _node_id: False)
        # Digests share the registry/broker lifecycle lock. Raw credentials
        # never enter registry descriptors, serialized state, or task payloads.
        self._node_token_digests: dict[str, str] = {}
        self._node_session_generations: dict[str, int] = {}
        self._enrollment_grants: dict[str, _EnrollmentGrant] = {}
        self._enrollment_audit: list[dict[str, Any]] = []
        configured_path = enrollment_state_path
        if configured_path is None:
            paths = getattr(getattr(self.mary, "config", None), "paths", None)
            runtime_path = getattr(paths, "runtime", None)
            if runtime_path is not None:
                configured_path = Path(runtime_path) / "node_enrollment.json"
        self._enrollment_state_path = (
            Path(configured_path) if configured_path is not None else None
        )
        self._load_enrollment_state()
        self.device_tasks = DeviceTaskBroker(
            lifecycle_lock=self._node_lifecycle_lock,
            live_node=self._node_live_validator,
        )
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

        with observe_turn_stage(
            "turn_lock_acquisition",
            failure_kind="lock_failure",
        ):
            self._turn_lock.acquire()
        try:
            before = self._state_fingerprint()
            if turn.requested_mode:
                self.mary.engagement.set_mode(turn.requested_mode)

            pipeline_started = monotonic()
            with observe_turn_stage("application_turn"):
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
            trace = current_turn_trace()
            if trace is not None:
                trace.set_turn_id(result.turn_id)
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
                request_id=trace.request_id if trace is not None else "",
                effective_mode=str(last_plan.get("effective_mode") or engagement.get("mode") or "adaptive"),
                provenance=self._provenance(result),
                state_changes=self._state_changes(before, after),
                conversation_state=conversation,
                display_hints=self._display_hints(
                    result,
                    pipeline_ms=pipeline_ms,
                ),
            )
        finally:
            self._turn_lock.release()

    def record_turn_trace(self, trace: dict[str, Any]) -> None:
        """Retain a small content-free diagnostic window for this Core process."""

        self._recent_turn_traces.append(_json_safe(trace))

    def recent_turn_traces(self) -> list[dict[str, Any]]:
        return [deepcopy(item) for item in self._recent_turn_traces]

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
            "character": {
                "sourcebook": (
                    self.mary.character_sourcebook.snapshot()
                    if callable(getattr(getattr(self.mary, "character_sourcebook", None), "snapshot", None))
                    else {"enabled": False}
                ),
                "evaluation": (
                    self.mary.character_evaluation.snapshot()
                    if callable(getattr(getattr(self.mary, "character_evaluation", None), "snapshot", None))
                    else {"enabled": False}
                ),
            },
            "root_authority": (
                self.mary.root_authority.snapshot(self.mary)
                if callable(getattr(getattr(self.mary, "root_authority", None), "snapshot", None))
                else {}
            ),
            "training": self.mary.training_feedback.status() if hasattr(self.mary, "training_feedback") else {},
            "creative_services": (
                self.mary.creative_services.snapshot()
                if callable(getattr(getattr(self.mary, "creative_services", None), "snapshot", None))
                else {}
            ),
            "production": (
                self.application.ecosystem.production.snapshot()
                if hasattr(getattr(self.application, "ecosystem", None), "production")
                else {}
            ),
            "integration": self.integration_status(),
        })

    def integration_status(self) -> dict[str, Any]:
        """Return executable top-to-bottom Mary architecture connection health."""
        from mary.runtime.integration_graph import build_integration_graph
        return _json_safe(build_integration_graph(application=self.application, service=self))

    def production_jobs(self, production_id: str) -> dict[str, Any]:
        """Compile a canonical production project into non-executing capability jobs."""
        return _json_safe(self.application.ecosystem.production.jobs(
            str(production_id or ""),
            node_registry=getattr(self.mary, "node_registry", None),
            service_registry=getattr(self.mary, "creative_services", None),
        ))

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
        payload["training"] = state.get("training", {})
        payload["production"] = state.get("production", {})
        payload["integration"] = state.get("integration", {})
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
        *,
        node_token: str | None = None,
        enrollment_grant: str | None = None,
        creator_authorized: bool = True,
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
        registry = self.mary.node_registry
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
        with self._node_lifecycle_lock:
            digest = self._node_token_digests.get(model.node_id)
            valid_existing_token = digest is not None and self._valid_node_token(
                model.node_id, node_token
            )
            node_is_live = registry.is_live(model.node_id)
            continuing_live_session = bool(
                digest is not None and valid_existing_token and node_is_live
            )
            if digest is not None and node_is_live and not valid_existing_token:
                self._audit_rejected_live_grant(
                    model.node_id,
                    enrollment_grant,
                )
                raise PermissionError(
                    "Existing live capability node registration requires its current node token."
                )
            if not continuing_live_session and not creator_authorized:
                if enrollment_grant is None:
                    raise PermissionError("Valid scoped enrollment grant required.")
                self._consume_enrollment_grant(model.node_id, enrollment_grant)
            # A disconnected/stale descriptor is not an active identity:
            # expire all prior-session work before atomically revoking its old
            # digest and issuing recovery credentials.
            if digest is not None and not continuing_live_session:
                self.device_tasks.expire_pending_for_node(
                    model.node_id,
                    reason=(
                        "Capability task expired because node enrollment/session "
                        "was replaced."
                    ),
                )
            raw_token = (
                None if continuing_live_session
                else secrets.token_urlsafe(32)
            )
            if raw_token is not None:
                self._node_token_digests[model.node_id] = self._node_token_digest(raw_token)
                self._node_session_generations[model.node_id] = (
                    self._node_session_generations.get(model.node_id, 0) + 1
                )
            registered = registry.register(descriptor)
            if raw_token is not None:
                self._save_enrollment_state()
        response = {
            "ok": True,
            "node": registered.to_dict(stale_after=self.mary.node_registry.stale_after),
            "registry": self.mary.node_registry.snapshot(),
            "session_generation": self._node_session_generations.get(model.node_id, 0),
        }
        # This is the sole disclosure point. It is deliberately not embedded in
        # node/registry objects, diagnostics, tasks, or persisted application state.
        if raw_token is not None:
            response["node_token"] = raw_token
        return _json_safe(response)

    def issue_enrollment_grant(
        self,
        node_id: str,
        *,
        expires_in_seconds: float = 900.0,
        max_uses: int = 10,
    ) -> dict[str, Any]:
        """Mint a narrow bearer usable only to enroll one named capability node."""
        clean_node_id = NodeRegistrationRequest.from_dict({
            "node_id": node_id,
            "capabilities": [],
        }).node_id
        ttl = max(30.0, min(86400.0, float(expires_in_seconds)))
        uses = max(1, min(20, int(max_uses)))
        raw = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        grant = _EnrollmentGrant(
            node_id=clean_node_id,
            digest=self._node_token_digest(raw),
            expires_monotonic=monotonic() + ttl,
            expires_at_epoch=time() + ttl,
            expires_at=datetime.fromtimestamp(now.timestamp() + ttl, timezone.utc).isoformat(),
            remaining_uses=uses,
            issued_at=now.isoformat(),
            grant_id=f"enroll_{uuid4().hex[:16]}",
        )
        with self._node_lifecycle_lock:
            self._enrollment_grants[grant.grant_id] = grant
            self._record_enrollment_audit("issued", grant)
            self._save_enrollment_state()
        return _json_safe({
            "ok": True,
            "enrollment_grant": raw,
            "grant": self._grant_public(grant),
        })

    def enrollment_grant_status(self) -> dict[str, Any]:
        with self._node_lifecycle_lock:
            self._prune_enrollment_grants()
            grants = [self._grant_public(item) for item in self._enrollment_grants.values()]
            audit = list(self._enrollment_audit)
        return _json_safe({"grants": grants, "audit": audit})

    def _consume_enrollment_grant(self, node_id: str, raw: str | None) -> None:
        self._prune_enrollment_grants()
        matched = self._matching_enrollment_grant(node_id, raw)
        if matched is None:
            raise PermissionError("Valid scoped enrollment grant required.")
        # Preserve active-ID takeover protection without burning the grant.
        if self.mary.node_registry.is_live(node_id):
            self._record_enrollment_audit("rejected_live_node", matched)
            self._save_enrollment_state()
            raise PermissionError("Existing live capability node registration requires its current node token.")
        matched.remaining_uses -= 1
        self._record_enrollment_audit("consumed", matched)
        if matched.remaining_uses <= 0:
            self._enrollment_grants.pop(matched.grant_id, None)
        self._save_enrollment_state()

    def _audit_rejected_live_grant(
        self,
        node_id: str,
        raw: str | None,
    ) -> None:
        if raw is None:
            return
        self._prune_enrollment_grants()
        matched = self._matching_enrollment_grant(node_id, raw)
        if matched is None:
            return
        self._record_enrollment_audit("rejected_live_node", matched)
        self._save_enrollment_state()

    def _matching_enrollment_grant(
        self,
        node_id: str,
        raw: str | None,
    ) -> _EnrollmentGrant | None:
        supplied_digest = self._node_token_digest(str(raw or ""))
        return next((
            item for item in self._enrollment_grants.values()
            if item.node_id == str(node_id)
            and secrets.compare_digest(item.digest, supplied_digest)
        ), None)

    def _prune_enrollment_grants(self) -> None:
        now = monotonic()
        changed = False
        for grant_id, grant in list(self._enrollment_grants.items()):
            if grant.expires_monotonic <= now or grant.expires_at_epoch <= time():
                self._record_enrollment_audit("expired", grant)
                self._enrollment_grants.pop(grant_id, None)
                changed = True
        if changed:
            self._save_enrollment_state()

    def _record_enrollment_audit(self, event: str, grant: _EnrollmentGrant) -> None:
        self._enrollment_audit.append({
            "event": event,
            "grant_id": grant.grant_id,
            "node_id": grant.node_id,
            "at": datetime.now(timezone.utc).isoformat(),
            "remaining_uses": grant.remaining_uses,
        })
        del self._enrollment_audit[:-200]

    def _load_enrollment_state(self) -> None:
        path = self._enrollment_state_path
        if path is None:
            return
        payload, _ = load_json_recovering(path, backup_generations=3)
        if not isinstance(payload, dict):
            return
        now_epoch = time()
        now_monotonic = monotonic()
        for item in list(payload.get("grants") or []):
            if not isinstance(item, dict):
                continue
            try:
                expires_epoch = float(item["expires_at_epoch"])
                if expires_epoch <= now_epoch:
                    continue
                grant = _EnrollmentGrant(
                    node_id=str(item["node_id"]),
                    digest=str(item["digest"]),
                    expires_monotonic=now_monotonic + (expires_epoch - now_epoch),
                    expires_at_epoch=expires_epoch,
                    expires_at=str(item["expires_at"]),
                    remaining_uses=max(1, int(item["remaining_uses"])),
                    issued_at=str(item["issued_at"]),
                    grant_id=str(item["grant_id"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._enrollment_grants[grant.grant_id] = grant
        self._enrollment_audit = [
            dict(item) for item in list(payload.get("audit") or [])[-200:]
            if isinstance(item, dict)
        ]
        self._node_session_generations = {
            str(node_id): max(0, int(generation))
            for node_id, generation in dict(
                payload.get("session_generations") or {}
            ).items()
        }

    def _save_enrollment_state(self) -> None:
        path = self._enrollment_state_path
        if path is None:
            return
        payload = {
            "version": 1,
            "grants": [
                {
                    "grant_id": item.grant_id,
                    "node_id": item.node_id,
                    "digest": item.digest,
                    "issued_at": item.issued_at,
                    "expires_at": item.expires_at,
                    "expires_at_epoch": item.expires_at_epoch,
                    "remaining_uses": item.remaining_uses,
                    "scope": ["node.enroll"],
                }
                for item in self._enrollment_grants.values()
            ],
            "audit": list(self._enrollment_audit),
            "session_generations": dict(self._node_session_generations),
        }
        if not atomic_write_json(path, payload, backup_generations=3, indent=2):
            raise RuntimeError("Could not persist node enrollment grant state.")

    @staticmethod
    def _grant_public(grant: _EnrollmentGrant) -> dict[str, Any]:
        return {
            "grant_id": grant.grant_id,
            "node_id": grant.node_id,
            "issued_at": grant.issued_at,
            "expires_at": grant.expires_at,
            "remaining_uses": grant.remaining_uses,
            "scope": ["node.enroll"],
        }

    def heartbeat_node(
        self,
        request: NodeHeartbeatRequest | dict[str, Any],
        *,
        node_token: str | None = None,
    ) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("Mary Core is closed.")
        model = (
            request
            if isinstance(request, NodeHeartbeatRequest)
            else NodeHeartbeatRequest.from_dict(request)
        )
        with self._node_lifecycle_lock:
            self.require_node_token(model.node_id, node_token)
            if not self.mary.node_registry.is_live(model.node_id):
                raise RuntimeError(
                    "Capability node lease is stale or disconnected; re-enrollment is required."
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
        *,
        node_token: str | None = None,
    ) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("Mary Core is closed.")
        model = (
            request
            if isinstance(request, NodeHeartbeatRequest)
            else NodeHeartbeatRequest.from_dict(request)
        )
        with self._node_lifecycle_lock:
            self.require_node_token(model.node_id, node_token)
            changed = self.mary.node_registry.disconnect(model.node_id)
            self.device_tasks.expire_pending_for_node(
                model.node_id, reason="Capability node disconnected before task completion."
            )
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
        *,
        node_token: str | None = None,
    ) -> dict[str, Any]:
        model = (
            request
            if isinstance(request, NodeTaskPollRequest)
            else NodeTaskPollRequest.from_dict(request)
        )
        captured_token = str(node_token or "")

        def authorized_live_node(node_id: str) -> bool:
            # DeviceTaskBroker invokes this only while holding the shared
            # lifecycle lock, including after every long-poll wake.
            return (
                self._valid_node_token(node_id, captured_token)
                and self.mary.node_registry.is_live(node_id)
            )

        task = self.device_tasks.poll(
            model.node_id,
            wait_seconds=model.wait_seconds,
            live_node=authorized_live_node,
        )
        return _json_safe({
            "ok": True,
            "task": task.to_dict() if task is not None else None,
        })

    def complete_capability_task(
        self,
        request: NodeTaskCompletionRequest | dict[str, Any],
        *,
        node_token: str | None = None,
    ) -> dict[str, Any]:
        model = (
            request
            if isinstance(request, NodeTaskCompletionRequest)
            else NodeTaskCompletionRequest.from_dict(request)
        )
        with self._node_lifecycle_lock:
            self.require_node_token(model.node_id, node_token)
            task = self.device_tasks.complete(
                node_id=model.node_id,
                task_id=model.task_id,
                status=model.status,
                result=model.result,
                error=model.error,
            )
        return _json_safe({"ok": True, "task": task.to_dict()})

    @staticmethod
    def _node_token_digest(token: str) -> str:
        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()

    def validate_node_token(self, node_id: str, token: str | None) -> bool:
        """Validate a scoped node credential for protocol transports."""
        with self._node_lifecycle_lock:
            return self._valid_node_token(node_id, token)

    def _valid_node_token(self, node_id: str, token: str | None) -> bool:
        supplied = str(token or "")
        expected = self._node_token_digests.get(str(node_id))
        return bool(supplied and expected) and secrets.compare_digest(
            self._node_token_digest(supplied), expected
        )

    def require_node_token(self, node_id: str, token: str | None) -> None:
        """Require the current credential for an explicitly named node."""
        with self._node_lifecycle_lock:
            if not self._valid_node_token(node_id, token):
                raise PermissionError("Valid scoped node token required.")

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

            if action.action == "training.dataset.preview":
                from mary.training import MaryTrainingDatasetExporter
                return _json_safe(MaryTrainingDatasetExporter().preview(self.mary.training_feedback))

            if action.action == "production.jobs.preview":
                return self.production_jobs(str(values.get("production_id") or ""))

            if action.action == "integration.status":
                return self.integration_status()

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
