"""Operational resource and affordance scoring for MaryV2."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import AtomicJsonStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ResourceSnapshot:
    node_id: str
    readiness: str
    captured_at: str
    vram_total_mb: int = 0
    vram_used_mb: int = 0
    ram_total_mb: int = 0
    ram_used_mb: int = 0
    cpu_load: float = 0.0
    gpu_load: float = 0.0

    @property
    def vram_free_mb(self) -> int:
        return max(0, self.vram_total_mb - self.vram_used_mb)


@dataclass(frozen=True)
class ActionAffordance:
    action: str
    available: bool
    permission_granted: bool
    readiness: str
    confidence: float
    risk: str
    estimated_latency_ms: float
    estimated_cost: float
    required_vram_mb: int = 0


class ComputeResourceGovernor:
    """Track latest resource snapshots and make non-authoritative placement recommendations."""

    VERSION = 1
    ROUTABLE = {"ready", "degraded"}

    def __init__(self, path: Path) -> None:
        self._store = AtomicJsonStore(path, default={"version": self.VERSION, "nodes": {}})

    def update(self, snapshot: ResourceSnapshot) -> ResourceSnapshot:
        clean = ResourceSnapshot(
            node_id=str(snapshot.node_id).strip()[:160],
            readiness=str(snapshot.readiness).strip().lower()[:40] or "unavailable",
            captured_at=snapshot.captured_at or _now(),
            vram_total_mb=max(0, int(snapshot.vram_total_mb)),
            vram_used_mb=max(0, int(snapshot.vram_used_mb)),
            ram_total_mb=max(0, int(snapshot.ram_total_mb)),
            ram_used_mb=max(0, int(snapshot.ram_used_mb)),
            cpu_load=max(0.0, min(float(snapshot.cpu_load), 1.0)),
            gpu_load=max(0.0, min(float(snapshot.gpu_load), 1.0)),
        )
        if not clean.node_id:
            raise ValueError("node_id is required")

        def mutate(data: dict[str, Any]) -> None:
            nodes = dict(data.get("nodes") or {})
            nodes[clean.node_id] = asdict(clean)
            data["nodes"] = nodes
            data["version"] = self.VERSION

        self._store.mutate(mutate)
        return clean

    def recommend_node(self, *, required_vram_mb: int = 0) -> str | None:
        required = max(0, int(required_vram_mb))
        candidates: list[tuple[float, str]] = []
        for node_id, raw in dict(self._store.snapshot().get("nodes") or {}).items():
            snap = ResourceSnapshot(**raw)
            if snap.readiness not in self.ROUTABLE:
                continue
            if required and snap.vram_free_mb < required:
                continue
            readiness_bonus = 1.0 if snap.readiness == "ready" else 0.5
            headroom = (snap.vram_free_mb / max(snap.vram_total_mb, 1)) if snap.vram_total_mb else 0.0
            pressure = max(snap.cpu_load, snap.gpu_load)
            score = readiness_bonus + headroom - pressure
            candidates.append((score, node_id))
        if not candidates:
            return None
        return max(candidates)[1]

    def snapshots(self) -> list[ResourceSnapshot]:
        return [ResourceSnapshot(**raw) for raw in dict(self._store.snapshot().get("nodes") or {}).values()]

    def status(self) -> dict[str, Any]:
        snaps = self.snapshots()
        return {
            "version": self.VERSION,
            "nodes": len(snaps),
            "ready": sum(1 for s in snaps if s.readiness == "ready"),
            "policy": "placement advisory only; NodeRegistry and permissions remain authoritative",
        }


class AffordanceScorer:
    """Rank what is useful/feasible without granting authority to execute it."""

    RISK_PENALTY = {"low": 0.0, "medium": 0.15, "high": 0.45, "critical": 1.0}

    def score(self, item: ActionAffordance) -> dict[str, Any]:
        if not item.available:
            return {"action": item.action, "eligible": False, "score": 0.0, "reason": "unavailable"}
        if not item.permission_granted:
            return {"action": item.action, "eligible": False, "score": 0.0, "reason": "permission_required"}
        if item.readiness not in ComputeResourceGovernor.ROUTABLE:
            return {"action": item.action, "eligible": False, "score": 0.0, "reason": "resource_not_ready"}
        latency_penalty = min(max(float(item.estimated_latency_ms), 0.0) / 30_000.0, 0.30)
        cost_penalty = min(max(float(item.estimated_cost), 0.0), 1.0) * 0.20
        risk_penalty = self.RISK_PENALTY.get(str(item.risk).lower(), 0.25)
        score = max(0.0, min(1.0, float(item.confidence) - latency_penalty - cost_penalty - risk_penalty))
        return {"action": item.action, "eligible": True, "score": round(score, 4), "reason": "eligible"}
