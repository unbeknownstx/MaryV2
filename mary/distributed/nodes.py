"""Transport-agnostic Mary node registry and capability routing foundation.

The authoritative Core owns state. Device nodes only advertise replaceable
capabilities. Registration, heartbeat, and routing never grant permission to
execute work on a device.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import os
from threading import RLock
from time import monotonic
from typing import Any

from .capabilities import CapabilityDescriptor, capabilities_from_environment


@dataclass
class NodeDescriptor:
    node_id: str
    role: str
    host_type: str
    platform: str
    capabilities: dict[str, CapabilityDescriptor] = field(default_factory=dict)
    local: bool = True
    trusted: bool = True
    connected: bool = True
    display_name: str = ""
    surface: str = "client"
    transport: str = "in_process"
    execution_policy: str = "authorization_required"
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_heartbeat_monotonic: float = field(default_factory=monotonic, repr=False)

    def heartbeat(self) -> None:
        self.connected = True
        self.last_heartbeat_monotonic = monotonic()

    def disconnect(self) -> None:
        self.connected = False

    def supports(self, capability: str) -> bool:
        item = self.capabilities.get(str(capability).strip().lower())
        return bool(item and item.routable)

    def to_dict(self, *, stale_after: float = 90.0) -> dict[str, Any]:
        age = max(0.0, monotonic() - self.last_heartbeat_monotonic)
        connected = bool(self.connected and age <= stale_after)
        return {
            "node_id": self.node_id,
            "display_name": self.display_name or self.node_id,
            "role": self.role,
            "host_type": self.host_type,
            "platform": self.platform,
            "surface": self.surface,
            "transport": self.transport,
            "local": self.local,
            "trusted": self.trusted,
            "connected": connected,
            "heartbeat_age_seconds": round(age, 2),
            "registered_at": self.registered_at,
            "capabilities": {name: item.to_dict() for name, item in self.capabilities.items()},
            "ownership": {
                "character_identity": False,
                "memory": False,
                "canonical_state": False,
            },
            "execution": {
                "policy": self.execution_policy,
                "authorized": False,
            },
        }


class NodeRegistry:
    VERSION = "13.11"

    def __init__(self, *, stale_after: float = 90.0) -> None:
        self.stale_after = max(10.0, float(stale_after))
        self._lock = RLock()
        self._nodes: dict[str, NodeDescriptor] = {}

    @property
    def lifecycle_lock(self) -> RLock:
        """Shared lock for registry lifecycle and its paired task broker."""
        return self._lock

    def register(self, node: NodeDescriptor) -> NodeDescriptor:
        with self._lock:
            existing = self._nodes.get(node.node_id)
            if existing is not None:
                node.registered_at = existing.registered_at
            node.heartbeat()
            self._nodes[node.node_id] = node
            return node

    def get(self, node_id: str) -> NodeDescriptor | None:
        with self._lock:
            return self._nodes.get(str(node_id))

    def heartbeat(self, node_id: str) -> bool:
        with self._lock:
            node = self._nodes.get(str(node_id))
            if node is None:
                return False
            node.heartbeat()
            return True

    def update_capability_readiness(
        self,
        node_id: str,
        capability: str,
        readiness: str,
        *,
        available: bool | None = None,
    ) -> bool:
        """Update one advertised capability health without changing ownership."""
        normalized = str(capability or "").strip().lower()
        state = str(readiness or "").strip().lower()
        if state not in {"ready", "degraded", "starting", "unavailable"}:
            raise ValueError("capability readiness must be ready, degraded, starting, or unavailable")
        with self._lock:
            node = self._nodes.get(str(node_id))
            if node is None or normalized not in node.capabilities:
                return False
            current = node.capabilities[normalized]
            effective_available = bool(current.available if available is None else available)
            if state == "unavailable":
                effective_available = False
            node.capabilities[normalized] = replace(
                current,
                available=effective_available,
                readiness=state,
            )
            return True

    def disconnect(self, node_id: str) -> bool:
        with self._lock:
            node = self._nodes.get(str(node_id))
            if node is None:
                return False
            node.disconnect()
            return True

    def is_live(self, node_id: str) -> bool:
        with self._lock:
            node = self._nodes.get(str(node_id))
            return bool(
                node is not None
                and node.connected
                and (monotonic() - node.last_heartbeat_monotonic) <= self.stale_after
            )

    def remove(self, node_id: str) -> bool:
        with self._lock:
            return self._nodes.pop(str(node_id), None) is not None

    def available(self) -> list[NodeDescriptor]:
        with self._lock:
            now = monotonic()
            return [
                node for node in self._nodes.values()
                if node.connected and (now - node.last_heartbeat_monotonic) <= self.stale_after
            ]

    def candidates(self, capability: str) -> list[NodeDescriptor]:
        normalized = str(capability).strip().lower()
        return [node for node in self.available() if node.supports(normalized)]

    @staticmethod
    def _benchmark_score(cap: CapabilityDescriptor) -> tuple[int, int, float]:
        """Return a stable preference tuple from sanitized operational hints.

        Missing benchmark data remains neutral so old/unbenchmarked nodes still
        work. A benchmark can only influence routing among already-routable
        candidates; it never grants capability or execution authority.
        """
        metadata = dict(cap.metadata or {})
        try:
            success = float(metadata.get("benchmark_success_rate"))
        except (TypeError, ValueError):
            success = -1.0
        try:
            latency = float(metadata.get("benchmark_latency_ms"))
        except (TypeError, ValueError):
            latency = -1.0
        has_measurement = 0 if (success >= 0.0 or latency >= 0.0) else 1
        failure_penalty = 0 if success < 0.0 or success >= 0.75 else 1
        latency_value = latency if latency >= 0.0 else float("inf")
        return (failure_penalty, has_measurement, latency_value)

    def choose(self, capability: str, *, prefer_private: bool = True, prefer_local: bool = True) -> NodeDescriptor | None:
        normalized = str(capability).strip().lower()
        candidates = self.candidates(normalized)
        if not candidates:
            return None

        def score(node: NodeDescriptor) -> tuple[int, int, int, int, int, int, float, str]:
            cap = node.capabilities[normalized]
            benchmark = self._benchmark_score(cap)
            return (
                0 if str(cap.readiness).strip().lower() == "ready" else 1,
                0 if (prefer_private and cap.private) else 1,
                0 if (prefer_local and cap.local) else 1,
                0 if cap.cost in {"free", "local"} else 1,
                benchmark[0],
                benchmark[1],
                benchmark[2],
                node.node_id,
            )

        return sorted(candidates, key=score)[0]

    def route_preview(
        self,
        capability: str,
        *,
        prefer_private: bool = True,
        prefer_local: bool = True,
    ) -> dict[str, Any]:
        normalized = str(capability).strip().lower()
        candidates = self.candidates(normalized)
        selected = self.choose(
            normalized,
            prefer_private=prefer_private,
            prefer_local=prefer_local,
        )
        return {
            "capability": normalized,
            "available": selected is not None,
            "selected_node_id": selected.node_id if selected is not None else None,
            "candidate_node_ids": [node.node_id for node in candidates],
            "candidate_readiness": {
                node.node_id: str(node.capabilities[normalized].readiness)
                for node in candidates
            },
            "candidate_benchmarks": {
                node.node_id: {
                    key: value
                    for key, value in dict(node.capabilities[normalized].metadata or {}).items()
                    if key in {"benchmark_latency_ms", "benchmark_success_rate", "benchmark_throughput", "benchmark_profile_version"}
                }
                for node in candidates
            },
            "candidate_count": len(candidates),
            "execution": "not_authorized",
            "policy": "routing selects a capable node only; execution requires a separate authorized device task channel",
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            nodes = [node.to_dict(stale_after=self.stale_after) for node in self._nodes.values()]
        nodes.sort(key=lambda item: (not bool(item.get("connected")), str(item.get("node_id"))))
        return {
            "version": self.VERSION,
            "nodes": nodes,
            "connected": sum(1 for item in nodes if item.get("connected")),
            "registered": len(nodes),
            "policy": "Core owns Mary state; nodes advertise replaceable capabilities and cannot execute without authorization",
        }

    @classmethod
    def with_local_runtime(cls, environment: Any) -> "NodeRegistry":
        registry = cls()
        snapshot = dict(environment.snapshot() or {})
        if str(snapshot.get("runtime_role") or "").strip().lower() == "core":
            return registry

        explicit = os.getenv("MARY_NODE_ID", "").strip()
        node_id = explicit or f"local-{snapshot.get('host_type', 'runtime')}-{snapshot.get('platform', 'unknown')}"
        capabilities = capabilities_from_environment(environment)
        registry.register(
            NodeDescriptor(
                node_id=node_id[:96],
                display_name=node_id[:96],
                role="local_runtime",
                host_type=str(snapshot.get("host_type") or "unknown"),
                platform=str(snapshot.get("platform") or "unknown"),
                capabilities={item.name: item for item in capabilities},
                local=True,
                trusted=True,
                surface="in_process",
                transport="in_process",
            )
        )
        return registry
