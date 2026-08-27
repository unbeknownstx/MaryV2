"""Non-executing capability task planning for MaryV2 distributed nodes."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .nodes import NodeRegistry


@dataclass(frozen=True)
class CapabilityTaskPlan:
    task_id: str
    capability: str
    intent: str
    requester_device_id: str
    selected_node_id: str | None
    status: str
    execution_authorized: bool = False
    execution_endpoint: None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def preview_capability_task(
    registry: NodeRegistry,
    *,
    capability: str,
    intent: str,
    requester_device_id: str,
) -> CapabilityTaskPlan:
    """Create a route plan only. This function can never execute a task."""

    route = registry.route_preview(capability)
    selected = route.get("selected_node_id")
    clean_intent = " ".join(str(intent or "").split())[:500]
    return CapabilityTaskPlan(
        task_id=f"capability_task_{uuid4().hex}",
        capability=str(capability).strip().lower()[:80],
        intent=clean_intent,
        requester_device_id=str(requester_device_id or "unknown-device")[:160],
        selected_node_id=str(selected) if selected else None,
        status="route_candidate" if selected else "no_capable_node",
        execution_authorized=False,
        execution_endpoint=None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
