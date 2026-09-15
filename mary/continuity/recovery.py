"""Managed capability-node recovery state machine."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import AtomicJsonStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class NodeRecoveryState:
    node_id: str
    state: str
    updated_at: str
    failure_count: int = 0
    last_reason: str = ""


class NodeRecoveryManager:
    """Track deterministic recovery stages; never executes device actions itself."""

    VERSION = 1
    STATES = {
        "unconfigured",
        "configuring",
        "inactive",
        "active",
        "degraded",
        "recovering",
        "unavailable",
    }

    def __init__(self, path: Path) -> None:
        self._store = AtomicJsonStore(path, default={"version": self.VERSION, "nodes": {}})

    def observe(self, node_id: str, *, healthy: bool, configured: bool = True, reason: str = "") -> NodeRecoveryState:
        node_id = str(node_id).strip()[:160]
        if not node_id:
            raise ValueError("node_id is required")
        current = self.get(node_id)
        failures = current.failure_count
        if not configured:
            next_state = "unconfigured"
            failures = 0
        elif healthy:
            next_state = "active"
            failures = 0
        else:
            failures += 1
            if failures == 1:
                next_state = "degraded"
            elif failures <= 3:
                next_state = "recovering"
            else:
                next_state = "unavailable"
        state = NodeRecoveryState(
            node_id=node_id,
            state=next_state,
            updated_at=_now(),
            failure_count=failures,
            last_reason=str(reason).strip()[:600],
        )
        self._put(state)
        return state

    def get(self, node_id: str) -> NodeRecoveryState:
        raw = dict(self._store.snapshot().get("nodes") or {}).get(node_id)
        if raw is None:
            return NodeRecoveryState(node_id=node_id, state="inactive", updated_at=_now())
        return NodeRecoveryState(**raw)

    def recommended_steps(self, node_id: str) -> tuple[str, ...]:
        state = self.get(node_id)
        if state.state == "degraded":
            return ("retry_health_probe",)
        if state.state == "recovering":
            return ("restart_capability_service", "health_probe", "reload_required_model", "probe_inference")
        if state.state == "unavailable":
            return ("stop_routing_new_work", "surface_creator_diagnostic")
        if state.state == "unconfigured":
            return ("configure_or_enroll_node",)
        return ()

    def status(self) -> dict[str, Any]:
        nodes = dict(self._store.snapshot().get("nodes") or {})
        return {
            "version": self.VERSION,
            "nodes": len(nodes),
            "recovering": sum(1 for row in nodes.values() if row.get("state") == "recovering"),
            "unavailable": sum(1 for row in nodes.values() if row.get("state") == "unavailable"),
            "execution": "advisory state machine; capability node retains execution permission",
        }

    def _put(self, state: NodeRecoveryState) -> None:
        def mutate(data: dict[str, Any]) -> None:
            nodes = dict(data.get("nodes") or {})
            nodes[state.node_id] = asdict(state)
            data["nodes"] = nodes
            data["version"] = self.VERSION
        self._store.mutate(mutate)
