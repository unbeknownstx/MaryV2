"""Bridge computer-use intent into Mary's existing typed node task fabric.

This deliberately stops short of execution. It maps a request-scoped
ComputerUseRequest onto existing sensor/MCP capability names so NodeRegistry,
DeviceTaskBroker and device-local permissions remain the only execution path.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .computer_use_contract import ComputerUseGrant, ComputerUseRequest, authorize_computer_use


@dataclass(frozen=True)
class ComputerUseDispatch:
    capability: str
    args: dict[str, Any]
    mutating: bool
    verification_required: bool
    authority: str = "typed_capability_dispatch_only"


_READ_ONLY_MAP = {
    "observe_screen": "sensor.screen_describe",
    "observe_window": "sensor.screen_describe",
    "probe_permissions": "sensor.screen_capture",
}


def bridge_computer_use(
    request: ComputerUseRequest,
    *,
    grant: ComputerUseGrant | None = None,
    action_capability: str = "",
    action_args: dict[str, Any] | None = None,
) -> ComputerUseDispatch:
    allowed, reason = authorize_computer_use(request, grant)
    if not allowed:
        raise PermissionError(reason)

    if not request.requires_grant:
        capability = _READ_ONLY_MAP[request.action]
        args = {
            "computer_use_request_id": request.request_id,
            "turn_id": request.turn_id,
            "observation_purpose": request.action,
        }
        if capability == "sensor.screen_describe":
            args["mode"] = "ui"
        else:
            args.update({"max_width": 1280, "quality": 70, "all_screens": False})
        return ComputerUseDispatch(capability, args, False, request.verify_after)

    # Mutating GUI automation is intentionally adapter-defined. Core may only
    # route it through an already typed capability; this bridge never invents
    # shell commands or a generic arbitrary-action endpoint.
    capability = str(action_capability or "").strip().lower()[:160]
    if not capability:
        raise ValueError("mutating computer use requires an explicit typed action_capability")
    if capability.startswith("sensor.") or capability.startswith("llm."):
        raise ValueError("mutating computer use cannot masquerade as a sensor or model capability")
    args = dict(action_args or {})
    args.update({
        "computer_use_request_id": request.request_id,
        "turn_id": request.turn_id,
        "computer_use_action": request.action,
        "verify_after": bool(request.verify_after),
    })
    return ComputerUseDispatch(capability, args, True, request.verify_after)
