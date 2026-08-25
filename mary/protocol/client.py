"""Dependency-light Python client for Mary Protocol v1."""
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .models import TurnRequest, TurnResponse


class MaryProtocolError(RuntimeError):
    pass


class MaryClient:
    def __init__(self, base_url: str, *, token: str, device_id: str = "python-client", timeout: float = 120.0) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.token = str(token or "")
        self.device_id = str(device_id or "python-client")
        self.timeout = float(timeout)

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

    def turn(self, text: str, *, conversation_id: str | None = None, requested_mode: str | None = None) -> TurnResponse:
        payload = TurnRequest.from_dict({
            "text": text,
            "conversation_id": conversation_id,
            "device_id": self.device_id,
            "requested_mode": requested_mode,
        })
        raw = self._request("POST", "/v1/turn", payload.to_dict())
        return TurnResponse(**raw)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None, *, authenticated: bool = True) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if authenticated and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
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
