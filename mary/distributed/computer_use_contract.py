"""Bounded computer-use request contract for Mary capability nodes.

Inspired by AUV/AIRI's useful separation between agent intent and host-owned
execution. Mary Core may request an operation, but a node remains the executor
and a request-scoped grant is required for mutating actions. This module does
not execute shell commands, clicks, typing, screenshots, or app automation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

VERSION = "13.70"

_READ_ONLY_ACTIONS = {"observe_screen", "observe_window", "probe_permissions"}
_MUTATING_ACTIONS = {"open_app", "focus_app", "click", "type_text", "key_press", "scroll"}


@dataclass(frozen=True)
class ComputerUseRequest:
    node_id: str
    action: str
    request_id: str
    turn_id: str
    requires_grant: bool
    verify_after: bool = True
    authority: str = "mary_core_request_node_execution"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComputerUseGrant:
    request_id: str
    turn_id: str
    node_id: str
    granted: bool
    scope: str = "current_request_only"
    persistence: str = "none"

    def matches(self, request: ComputerUseRequest) -> bool:
        return bool(
            self.granted
            and self.request_id == request.request_id
            and self.turn_id == request.turn_id
            and self.node_id == request.node_id
            and self.scope == "current_request_only"
        )


def make_computer_use_request(
    *,
    node_id: str,
    action: str,
    turn_id: str,
    request_id: str | None = None,
) -> ComputerUseRequest:
    clean_node = str(node_id or "").strip()[:240]
    clean_action = str(action or "").strip().lower()[:80]
    clean_turn = str(turn_id or "").strip()[:240]
    if not clean_node or not clean_action or not clean_turn:
        raise ValueError("node_id, action and turn_id are required")
    if clean_action not in _READ_ONLY_ACTIONS | _MUTATING_ACTIONS:
        raise ValueError(f"unsupported computer-use action: {clean_action}")
    return ComputerUseRequest(
        node_id=clean_node,
        action=clean_action,
        request_id=str(request_id or uuid4().hex)[:240],
        turn_id=clean_turn,
        requires_grant=clean_action in _MUTATING_ACTIONS,
    )


def authorize_computer_use(
    request: ComputerUseRequest,
    grant: ComputerUseGrant | None,
) -> tuple[bool, str]:
    if not request.requires_grant:
        return True, "read_only_observation"
    if grant is None:
        return False, "request_scoped_grant_required"
    if not grant.matches(request):
        return False, "grant_scope_mismatch"
    return True, "request_scoped_grant_verified"
