"""Observation -> typed action -> verification planning for computer use.

The cycle is a plan, not an executor. Every leg travels through Mary's existing
DeviceTaskBroker and device-local permission system. Mutation grants are
request-scoped and cannot be reused for the verification observation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .computer_use_bridge import ComputerUseDispatch, bridge_computer_use
from .computer_use_contract import ComputerUseGrant, ComputerUseRequest, make_computer_use_request


@dataclass(frozen=True)
class ComputerUseCycle:
    observe: ComputerUseDispatch
    action: ComputerUseDispatch | None
    verify: ComputerUseDispatch | None
    request_id: str
    turn_id: str
    authority: str = "plan_only_existing_task_broker_executes"

    def to_dict(self) -> dict[str, Any]:
        return {
            "observe": asdict(self.observe),
            "action": asdict(self.action) if self.action else None,
            "verify": asdict(self.verify) if self.verify else None,
            "request_id": self.request_id,
            "turn_id": self.turn_id,
            "authority": self.authority,
        }


def plan_computer_use_cycle(
    request: ComputerUseRequest,
    *,
    grant: ComputerUseGrant | None = None,
    action_capability: str = "",
    action_args: dict[str, Any] | None = None,
) -> ComputerUseCycle:
    observe_request = make_computer_use_request(
        node_id=request.node_id,
        action="observe_screen",
        turn_id=request.turn_id,
        request_id=f"{request.request_id}:observe",
    )
    observe = bridge_computer_use(observe_request)
    if not request.requires_grant:
        return ComputerUseCycle(observe, None, None, request.request_id, request.turn_id)

    action = bridge_computer_use(
        request, grant=grant, action_capability=action_capability, action_args=action_args
    )
    verify = None
    if request.verify_after:
        verify_request = make_computer_use_request(
            node_id=request.node_id,
            action="observe_screen",
            turn_id=request.turn_id,
            request_id=f"{request.request_id}:verify",
        )
        verify = bridge_computer_use(verify_request)
    return ComputerUseCycle(observe, action, verify, request.request_id, request.turn_id)
