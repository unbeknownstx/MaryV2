"""Transport-agnostic Mary node registry and capability routing foundation.

13.1 registers the current host as a local node. A future cloud core/home-agent
transport can heartbeat remote nodes into the same registry without changing
callers. State remains canonical elsewhere; nodes are replaceable resources.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import os
from threading import RLock
from time import monotonic
from typing import Any, Iterable

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
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_heartbeat_monotonic: float = field(default_factory=monotonic, repr=False)

    def heartbeat(self) -> None:
        self.connected = True
        self.last_heartbeat_monotonic = monotonic()

    def supports(self, capability: str) -> bool:
        item = self.capabilities.get(str(capability))
        return bool(item and item.available)

    def to_dict(self, *, stale_after: float = 90.0) -> dict[str, Any]:
        age = max(0.0, monotonic() - self.last_heartbeat_monotonic)
        return {
            "node_id": self.node_id,
            "role": self.role,
            "host_type": self.host_type,
            "platform": self.platform,
            "local": self.local,
            "trusted": self.trusted,
            "connected": bool(self.connected and age <= stale_after),
            "heartbeat_age_seconds": round(age, 2),
            "registered_at": self.registered_at,
            "capabilities": {name: item.to_dict() for name, item in self.capabilities.items()},
        }


class NodeRegistry:
    VERSION = "13.1"

    def __init__(self, *, stale_after: float = 90.0) -> None:
        self.stale_after = max(10.0, float(stale_after))
        self._lock = RLock()
        self._nodes: dict[str, NodeDescriptor] = {}

    def register(self, node: NodeDescriptor) -> NodeDescriptor:
        with self._lock:
            node.heartbeat()
            self._nodes[node.node_id] = node
            return node

    def heartbeat(self, node_id: str) -> bool:
        with self._lock:
            node = self._nodes.get(str(node_id))
            if node is None:
                return False
            node.heartbeat()
            return True

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
        return [node for node in self.available() if node.supports(capability)]

    def choose(self, capability: str, *, prefer_private: bool = True, prefer_local: bool = True) -> NodeDescriptor | None:
        candidates = self.candidates(capability)
        if not candidates:
            return None

        def score(node: NodeDescriptor) -> tuple[int, int, int, str]:
            cap = node.capabilities[str(capability)]
            return (
                0 if (prefer_private and cap.private) else 1,
                0 if (prefer_local and node.local) else 1,
                0 if cap.cost in {"free", "local"} else 1,
                node.node_id,
            )

        return sorted(candidates, key=score)[0]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            nodes = [node.to_dict(stale_after=self.stale_after) for node in self._nodes.values()]
        nodes.sort(key=lambda item: (not bool(item.get("connected")), str(item.get("node_id"))))
        return {
            "version": self.VERSION,
            "nodes": nodes,
            "connected": sum(1 for item in nodes if item.get("connected")),
            "registered": len(nodes),
            "policy": "state is not owned by compute nodes; capability routing is replaceable and permission-aware",
        }

    @classmethod
    def with_local_runtime(cls, environment: Any) -> "NodeRegistry":
        registry = cls()
        snapshot = dict(environment.snapshot() or {})
        explicit = os.getenv("MARY_NODE_ID", "").strip()
        node_id = explicit or f"local-{snapshot.get('host_type', 'runtime')}-{snapshot.get('platform', 'unknown')}"
        capabilities = capabilities_from_environment(environment)
        registry.register(
            NodeDescriptor(
                node_id=node_id[:96],
                role="local_runtime",
                host_type=str(snapshot.get("host_type") or "unknown"),
                platform=str(snapshot.get("platform") or "unknown"),
                capabilities={item.name: item for item in capabilities},
                local=True,
                trusted=True,
            )
        )
        return registry
