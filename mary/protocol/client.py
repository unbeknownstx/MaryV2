"""Dependency-light Python client for Mary Protocol v1."""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .credential_store import NodeCredentialStore
from .models import (
    CapabilityRouteRequest,
    CapabilityTaskDispatchRequest,
    CapabilityTaskPreviewRequest,
    CreatorOfflineRequest,
    CreatorSurfaceRequest,
    NodeHeartbeatRequest,
    NodeRegistrationRequest,
    NodeTaskCompletionRequest,
    NodeTaskPollRequest,
    RuntimeActionRequest,
    TurnRequest,
    TurnResponse,
    WorkspaceActionRequest,
)


_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class MaryProtocolError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        request_id: str = "",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        candidate = str(request_id or "").strip()
        self.request_id = (
            candidate
            if _SAFE_REQUEST_ID.fullmatch(candidate)
            else ""
        )
        self.status_code = status_code


class MaryClient:
    def __init__(self, base_url: str, *, token: str = "", enrollment_grant: str = "", device_credential: str = "", credential_store: Any | None = None, device_id: str = "python-client", surface: str = "client", timeout: float = 120.0) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.token = str(token or "")
        self.enrollment_grant = str(enrollment_grant or "")
        self.device_id = str(device_id or "python-client")
        self.surface = str(surface or "client")
        self.timeout = float(timeout)
        self._credential_store = (
            credential_store if credential_store is not None else NodeCredentialStore()
        )
        self._device_credential = str(device_credential or "")
        self._credential_loaded = bool(self._device_credential)
        # The session node token remains ephemeral and is never included in
        # request JSON or a client state/snapshot object.
        self._node_token = ""

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/v1/health", authenticated=False)

    def state(self) -> dict[str, Any]:
        return self._request("GET", "/v1/state")

    def lifecycle_status(self) -> dict[str, Any]:
        return self._request("GET", "/v1/creator-surfaces/status")

    def surface_register(self, surface_id: str | None = None, *, visible: bool = True, foreground: bool = True, lease_seconds: float | None = None) -> dict[str, Any]:
        model = CreatorSurfaceRequest.from_dict({
            "surface_id": surface_id or self.device_id,
            "visible": visible,
            "foreground": foreground,
            "lease_seconds": lease_seconds,
        })
        return self._request("POST", "/v1/creator-surfaces/register", model.to_dict())

    def surface_renew(self, surface_id: str | None = None, *, visible: bool | None = None, foreground: bool | None = None, activity: bool = False, lease_seconds: float | None = None) -> dict[str, Any]:
        model = CreatorSurfaceRequest.from_dict({
            "surface_id": surface_id or self.device_id,
            "visible": visible,
            "foreground": foreground,
            "activity": activity,
            "lease_seconds": lease_seconds,
        })
        return self._request("POST", "/v1/creator-surfaces/renew", model.to_dict())

    def surface_disconnect(self, surface_id: str | None = None) -> dict[str, Any]:
        model = CreatorSurfaceRequest.from_dict({"surface_id": surface_id or self.device_id})
        return self._request("POST", "/v1/creator-surfaces/disconnect", model.to_dict())

    def surface_wake(self, surface_id: str | None = None) -> dict[str, Any]:
        model = CreatorSurfaceRequest.from_dict({"surface_id": surface_id or self.device_id})
        return self._request("POST", "/v1/creator-surfaces/wake", model.to_dict())

    # Explicit aliases keep the creator-oriented protocol vocabulary available.
    creator_lifecycle_status = lifecycle_status
    register_creator_surface = surface_register
    renew_creator_surface = surface_renew
    disconnect_creator_surface = surface_disconnect
    wake_creator_surfaces = surface_wake

    def set_creator_offline(self, offline: bool = True) -> dict[str, Any]:
        model = CreatorOfflineRequest(offline=bool(offline))
        return self._request("POST", "/v1/creator-surfaces/offline", model.to_dict())

    def memory_status(self) -> dict[str, Any]:
        return self._request("GET", "/v1/memory/status")

    def conversation_status(self) -> dict[str, Any]:
        return self._request("GET", "/v1/conversation")

    def growth_status(self) -> dict[str, Any]:
        return self._request("GET", "/v1/growth")

    def nodes(self) -> dict[str, Any]:
        return self._request("GET", "/v1/nodes")

    def revoke_node(self, node_id: str) -> dict[str, Any]:
        clean = str(node_id or "").strip()
        if not clean:
            raise ValueError("node_id is required.")
        return self._request(
            "POST",
            "/v1/nodes/revoke",
            {"node_id": clean},
            timeout=min(self.timeout, 3.0),
        )

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
        model = NodeRegistrationRequest.from_dict({
            "node_id": self.device_id,
            "display_name": display_name,
            "host_type": host_type,
            "platform": platform,
            "surface": surface,
            "capabilities": list(capabilities or []),
            "local": bool(local),
        })
        if not self._device_credential_transport_is_safe():
            raise MaryProtocolError(
                "Node registration credentials require HTTPS or a loopback Core endpoint."
            )
        device_credential = self._load_device_credential()
        response = self._request(
            "POST", "/v1/nodes/register", model.to_dict(),
            timeout=min(self.timeout, 3.0),
            authenticated=bool(self.token),
            node_authenticated=bool(self._node_token),
            enrollment_authenticated=bool(self.enrollment_grant),
            device_credential_authenticated=bool(device_credential),
        )
        issued = response.get("node_token")
        if issued is not None:
            if not isinstance(issued, str) or not issued:
                raise MaryProtocolError("Mary Core returned an invalid node token.")
            self._node_token = issued
        # This bootstrap value is deliberately consumed here rather than passed
        # onward to UI/status callers with the registration response.
        issued_credential = response.pop("device_credential", None)
        if issued_credential is not None:
            if not isinstance(issued_credential, str) or not issued_credential:
                raise MaryProtocolError("Mary Core returned an invalid device credential.")
            try:
                self._credential_store.save(self.device_id, issued_credential)
            except Exception as exc:
                raise MaryProtocolError("Could not securely store the device credential.") from exc
            self._device_credential = issued_credential
            self._credential_loaded = True
        return response

    def _load_device_credential(self) -> str:
        if not self._credential_loaded:
            self._credential_loaded = True
            try:
                self._device_credential = str(
                    self._credential_store.load(self.device_id) or ""
                )
            except Exception as exc:
                raise MaryProtocolError("Could not read the local device credential.") from exc
        return self._device_credential

    def _device_credential_transport_is_safe(self) -> bool:
        parsed = urlsplit(self.base_url)
        return parsed.scheme.lower() == "https"

    def heartbeat_node(self) -> dict[str, Any]:
        model = NodeHeartbeatRequest.from_dict({"node_id": self.device_id})
        return self._request("POST", "/v1/nodes/heartbeat", model.to_dict(), timeout=min(self.timeout, 3.0), node_authenticated=True)

    def disconnect_node(self) -> dict[str, Any]:
        model = NodeHeartbeatRequest.from_dict({"node_id": self.device_id})
        return self._request("POST", "/v1/nodes/disconnect", model.to_dict(), timeout=min(self.timeout, 3.0), node_authenticated=True)

    def route_capability(
        self,
        capability: str,
        *,
        prefer_private: bool = True,
        prefer_local: bool = True,
    ) -> dict[str, Any]:
        model = CapabilityRouteRequest.from_dict({
            "capability": capability,
            "prefer_private": bool(prefer_private),
            "prefer_local": bool(prefer_local),
        })
        return self._request("POST", "/v1/nodes/route", model.to_dict(), timeout=min(self.timeout, 3.0))

    def preview_capability_task(
        self,
        capability: str,
        intent: str,
    ) -> dict[str, Any]:
        model = CapabilityTaskPreviewRequest.from_dict({
            "capability": capability,
            "intent": intent,
            "device_id": self.device_id,
        })
        return self._request("POST", "/v1/nodes/task/preview", model.to_dict(), timeout=min(self.timeout, 3.0))

    def dispatch_capability_task(
        self,
        capability: str,
        intent: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model = CapabilityTaskDispatchRequest.from_dict({
            "capability": capability,
            "intent": intent,
            "args": dict(args or {}),
            "device_id": self.device_id,
        })
        return self._request("POST", "/v1/nodes/task/dispatch", model.to_dict(), timeout=min(self.timeout, 5.0))

    def poll_capability_task(self, *, wait_seconds: float = 0.0) -> dict[str, Any]:
        model = NodeTaskPollRequest.from_dict({
            "node_id": self.device_id,
            "wait_seconds": wait_seconds,
        })
        request_timeout = max(3.0, float(model.wait_seconds) + 5.0)
        return self._request(
            "POST",
            "/v1/nodes/task/poll",
            model.to_dict(),
            timeout=min(max(self.timeout, request_timeout), 35.0),
            node_authenticated=True,
        )

    def complete_capability_task(
        self,
        task_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> dict[str, Any]:
        model = NodeTaskCompletionRequest.from_dict({
            "node_id": self.device_id,
            "task_id": task_id,
            "status": status,
            "result": dict(result or {}),
            "error": error,
        })
        return self._request("POST", "/v1/nodes/task/complete", model.to_dict(), timeout=min(self.timeout, 5.0), node_authenticated=True)

    def capability_task_status(self, task_id: str) -> dict[str, Any]:
        clean = str(task_id or "").strip()
        if not clean.startswith("capability_task_") or len(clean) > 96:
            raise ValueError("task_id is invalid.")
        return self._request("GET", f"/v1/nodes/task/{clean}", timeout=min(self.timeout, 3.0))

    def workspace(self) -> dict[str, Any]:
        return self._request("GET", "/v1/workspace")

    def dashboard(self) -> dict[str, Any]:
        return self._request("GET", "/v1/dashboard")

    def workspace_action(
        self,
        action: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = WorkspaceActionRequest.from_dict({
            "action": action,
            "args": dict(args or {}),
            "device_id": self.device_id,
        })
        return self._request(
            "POST",
            "/v1/workspace/action",
            payload.to_dict(),
        )

    def runtime_action(
        self,
        action: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = RuntimeActionRequest.from_dict({
            "action": action,
            "args": dict(args or {}),
            "device_id": self.device_id,
        })
        return self._request(
            "POST",
            "/v1/runtime/action",
            payload.to_dict(),
        )

    def turn(
        self,
        text: str,
        *,
        turn_id: str | None = None,
        conversation_id: str | None = None,
        requested_mode: str | None = None,
        voice_input: bool = False,
    ) -> TurnResponse:
        payload = TurnRequest.from_dict({
            "text": text,
            "turn_id": turn_id,
            "conversation_id": conversation_id,
            "device_id": self.device_id,
            "surface": self.surface,
            "voice_input": bool(voice_input),
            "requested_mode": requested_mode,
        })
        raw = self._request("POST", "/v1/turn", payload.to_dict())
        return TurnResponse(**raw)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        authenticated: bool = True,
        node_authenticated: bool = False,
        enrollment_authenticated: bool = False,
        device_credential_authenticated: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if authenticated and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if node_authenticated:
            if not self._node_token:
                raise MaryProtocolError("Node registration is required before device-channel calls.")
            headers["X-Mary-Node-Token"] = self._node_token
        if enrollment_authenticated:
            headers["X-Mary-Enrollment-Grant"] = self.enrollment_grant
        if device_credential_authenticated:
            headers["X-Mary-Device-Credential"] = self._device_credential
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout if timeout is None else float(timeout)) as response:
                data = response.read()
        except HTTPError as exc:
            request_id = str(
                (exc.headers or {}).get("X-Mary-Request-ID")
                or ""
            )
            safe_request_id = (
                request_id
                if _SAFE_REQUEST_ID.fullmatch(request_id)
                else ""
            )
            suffix = (
                f" (request_id={safe_request_id})"
                if safe_request_id
                else ""
            )
            raise MaryProtocolError(
                f"Mary Core returned HTTP {exc.code}{suffix}.",
                request_id=safe_request_id,
                status_code=int(exc.code),
            ) from exc
        except OSError as exc:
            raise MaryProtocolError(
                "Could not reach Mary Core.",
            ) from exc
        try:
            parsed = json.loads(data.decode("utf-8"))
        except Exception as exc:
            raise MaryProtocolError("Mary Core returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise MaryProtocolError("Mary Core returned an invalid response object.")
        return parsed
