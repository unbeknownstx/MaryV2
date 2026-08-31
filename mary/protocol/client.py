"""Dependency-light Python client for Mary Protocol v1."""
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .models import (
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


class MaryProtocolError(RuntimeError):
    pass


class MaryClient:
    def __init__(self, base_url: str, *, token: str, device_id: str = "python-client", surface: str = "client", timeout: float = 120.0) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.token = str(token or "")
        self.device_id = str(device_id or "python-client")
        self.surface = str(surface or "client")
        self.timeout = float(timeout)
        # Ephemeral process-local device credential. It is never included in
        # request JSON or a client state/snapshot object.
        self._node_token = ""

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/v1/health", authenticated=False)

    def state(self) -> dict[str, Any]:
        return self._request("GET", "/v1/state")

    def memory_status(self) -> dict[str, Any]:
        return self._request("GET", "/v1/memory/status")

    def conversation_status(self) -> dict[str, Any]:
        return self._request("GET", "/v1/conversation")

    def growth_status(self) -> dict[str, Any]:
        return self._request("GET", "/v1/growth")

    def nodes(self) -> dict[str, Any]:
        return self._request("GET", "/v1/nodes")

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
        response = self._request(
            "POST", "/v1/nodes/register", model.to_dict(),
            timeout=min(self.timeout, 3.0), node_authenticated=bool(self._node_token),
        )
        issued = response.get("node_token")
        if issued is not None:
            if not isinstance(issued, str) or not issued:
                raise MaryProtocolError("Mary Core returned an invalid node token.")
            self._node_token = issued
        return response

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
        conversation_id: str | None = None,
        requested_mode: str | None = None,
        voice_input: bool = False,
    ) -> TurnResponse:
        payload = TurnRequest.from_dict({
            "text": text,
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
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout if timeout is None else float(timeout)) as response:
                data = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MaryProtocolError(f"Mary Core returned HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise MaryProtocolError(f"Could not reach Mary Core: {exc}") from exc
        try:
            parsed = json.loads(data.decode("utf-8"))
        except Exception as exc:
            raise MaryProtocolError("Mary Core returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise MaryProtocolError("Mary Core returned an invalid response object.")
        return parsed
