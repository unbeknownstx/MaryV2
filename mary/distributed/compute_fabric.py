"""Adaptive, benchmark-aware scheduling for Mary's replaceable compute nodes.

This module does not own identity, memory, permissions, or durable truth.  It
ranks already-advertised capabilities using bounded runtime evidence so the same
Mary Core can make useful use of heterogeneous Mac/Windows/cloud resources.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from statistics import median
from threading import RLock
from typing import Any, Iterable

from .nodes import NodeDescriptor, NodeRegistry


@dataclass(frozen=True)
class BenchmarkSample:
    node_id: str
    capability: str
    operation: str
    latency_ms: float
    success: bool = True
    throughput: float | None = None
    measured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BenchmarkBook:
    """Small process-local benchmark evidence store.

    Benchmarks are operational hints only. They are intentionally not Mary
    memory and may be discarded on restart or rebuilt after hardware changes.
    """

    VERSION = "13.11"

    def __init__(self, *, max_samples_per_key: int = 12) -> None:
        self.max_samples_per_key = max(3, min(50, int(max_samples_per_key)))
        self._lock = RLock()
        self._samples: dict[tuple[str, str, str], list[BenchmarkSample]] = {}

    def record(self, sample: BenchmarkSample) -> None:
        key = (
            str(sample.node_id).strip(),
            str(sample.capability).strip().lower(),
            str(sample.operation).strip().lower(),
        )
        if not all(key):
            raise ValueError("benchmark sample requires node, capability, and operation")
        with self._lock:
            items = self._samples.setdefault(key, [])
            items.append(sample)
            del items[:-self.max_samples_per_key]

    def ingest(self, payload: Iterable[dict[str, Any]]) -> None:
        for item in payload:
            try:
                self.record(BenchmarkSample(
                    node_id=str(item.get("node_id") or ""),
                    capability=str(item.get("capability") or ""),
                    operation=str(item.get("operation") or "general"),
                    latency_ms=max(0.0, float(item.get("latency_ms") or 0.0)),
                    success=bool(item.get("success", True)),
                    throughput=(None if item.get("throughput") is None else max(0.0, float(item.get("throughput")))),
                    measured_at=str(item.get("measured_at") or datetime.now(timezone.utc).isoformat())[:80],
                ))
            except (TypeError, ValueError):
                continue

    def summary(self, node_id: str, capability: str, operation: str = "general") -> dict[str, Any]:
        key = (str(node_id).strip(), str(capability).strip().lower(), str(operation).strip().lower())
        with self._lock:
            samples = list(self._samples.get(key, []))
            if not samples and key[2] != "general":
                samples = list(self._samples.get((key[0], key[1], "general"), []))
        successes = [item for item in samples if item.success]
        latencies = [item.latency_ms for item in successes]
        throughputs = [item.throughput for item in successes if item.throughput is not None]
        return {
            "samples": len(samples),
            "success_rate": round(len(successes) / len(samples), 3) if samples else None,
            "median_latency_ms": round(median(latencies), 2) if latencies else None,
            "median_throughput": round(median(throughputs), 3) if throughputs else None,
            "authority": "operational_hint_only",
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            items = [sample.to_dict() for values in self._samples.values() for sample in values]
        return {"version": self.VERSION, "samples": items, "authority": "operational_hint_only"}


@dataclass(frozen=True)
class WorkloadRequest:
    capability: str
    operation: str = "general"
    realtime: bool = False
    privacy_required: bool = False
    local_preferred: bool = True
    cost_sensitive: bool = True
    estimated_seconds: float = 0.0


@dataclass(frozen=True)
class NodeLoad:
    node_id: str
    active_realtime: int = 0
    active_background: int = 0
    cpu_fraction: float | None = None
    memory_fraction: float | None = None
    stream_critical: bool = False

    @property
    def pressure(self) -> float:
        pressure = min(1.0, 0.28 * self.active_realtime + 0.12 * self.active_background)
        for value in (self.cpu_fraction, self.memory_fraction):
            if value is not None:
                pressure = max(pressure, max(0.0, min(1.0, float(value))))
        return pressure


class HomeComputeScheduler:
    """Rank node candidates without granting execution permission.

    The task broker remains the execution boundary. This class only provides a
    better selection decision using readiness, privacy, cost, measured latency,
    and live load.
    """

    VERSION = "13.11"

    def __init__(self, registry: NodeRegistry, *, benchmarks: BenchmarkBook | None = None) -> None:
        self.registry = registry
        self.benchmarks = benchmarks or BenchmarkBook()
        self._loads: dict[str, NodeLoad] = {}
        self._lock = RLock()

    def update_load(self, load: NodeLoad) -> None:
        with self._lock:
            self._loads[str(load.node_id)] = load

    def load_for(self, node_id: str) -> NodeLoad:
        with self._lock:
            return self._loads.get(str(node_id), NodeLoad(node_id=str(node_id)))

    def _score(self, node: NodeDescriptor, request: WorkloadRequest) -> tuple[float, str]:
        cap = node.capabilities[request.capability]
        score = 0.0
        reasons: list[str] = []

        readiness = str(cap.readiness).strip().lower()
        if readiness == "ready":
            score += 40.0
            reasons.append("ready")
        elif readiness == "degraded":
            score += 12.0
            reasons.append("degraded")
        else:
            return (-10_000.0, readiness or "unavailable")

        if request.privacy_required:
            if not cap.private:
                return (-10_000.0, "privacy_mismatch")
            score += 30.0
            reasons.append("private")
        elif cap.private:
            score += 5.0

        if request.local_preferred and cap.local:
            score += 14.0
            reasons.append("local")
        if request.cost_sensitive and cap.cost in {"free", "local"}:
            score += 10.0
            reasons.append("zero_cost")

        bench = self.benchmarks.summary(node.node_id, request.capability, request.operation)
        latency = bench.get("median_latency_ms")
        success_rate = bench.get("success_rate")
        if success_rate is not None:
            score += 18.0 * float(success_rate)
            reasons.append(f"success={success_rate:.2f}")
        if latency is not None:
            # Realtime work strongly favors lower measured latency; background
            # work still benefits but does not starve slower useful machines.
            budget = 2500.0 if request.realtime else 15_000.0
            latency_factor = max(0.0, 1.0 - min(float(latency), budget) / budget)
            score += (28.0 if request.realtime else 12.0) * latency_factor
            reasons.append(f"median={latency:.0f}ms")

        load = self.load_for(node.node_id)
        penalty = 36.0 * load.pressure
        if load.stream_critical and not request.realtime:
            penalty += 30.0
            reasons.append("protect_stream")
        if request.realtime and load.active_realtime:
            penalty += min(24.0, 8.0 * load.active_realtime)
        score -= penalty
        if penalty:
            reasons.append(f"load_penalty={penalty:.1f}")

        return (score, ",".join(reasons))

    def rank(self, request: WorkloadRequest) -> list[dict[str, Any]]:
        capability = str(request.capability).strip().lower()
        normalized = WorkloadRequest(
            capability=capability,
            operation=str(request.operation or "general").strip().lower(),
            realtime=bool(request.realtime),
            privacy_required=bool(request.privacy_required),
            local_preferred=bool(request.local_preferred),
            cost_sensitive=bool(request.cost_sensitive),
            estimated_seconds=max(0.0, float(request.estimated_seconds)),
        )
        ranked = []
        for node in self.registry.candidates(capability):
            score, reason = self._score(node, normalized)
            if score <= -9000:
                continue
            ranked.append({
                "node_id": node.node_id,
                "score": round(score, 3),
                "reason": reason,
                "load_pressure": round(self.load_for(node.node_id).pressure, 3),
                "benchmark": self.benchmarks.summary(node.node_id, capability, normalized.operation),
            })
        ranked.sort(key=lambda item: (-float(item["score"]), str(item["node_id"])))
        return ranked

    def choose(self, request: WorkloadRequest) -> NodeDescriptor | None:
        ranked = self.rank(request)
        if not ranked:
            return None
        return self.registry.get(str(ranked[0]["node_id"]))

    def route_preview(self, request: WorkloadRequest) -> dict[str, Any]:
        ranked = self.rank(request)
        return {
            "version": self.VERSION,
            "capability": str(request.capability).strip().lower(),
            "operation": str(request.operation or "general").strip().lower(),
            "selected_node_id": ranked[0]["node_id"] if ranked else None,
            "candidates": ranked,
            "execution": "not_authorized",
            "authority": "scheduling_hint_only",
            "policy": "selection never grants permission; execution still uses the bounded device-task channel",
        }


WORKLOAD_PROFILES: dict[str, dict[str, Any]] = {
    "conversation_fast": {"operation": "conversation", "realtime": True, "estimated_seconds": 2.0},
    "speech_to_text": {"operation": "stt", "realtime": True, "privacy_required": True, "estimated_seconds": 2.0},
    "screen_perception": {"operation": "vision", "realtime": True, "estimated_seconds": 4.0},
    "memory_index": {"operation": "embedding", "realtime": False, "estimated_seconds": 30.0},
    "background_summary": {"operation": "summary", "realtime": False, "estimated_seconds": 30.0},
    "creative_generation": {"operation": "generation", "realtime": False, "estimated_seconds": 120.0},
}


def workload(capability: str, profile: str, **overrides: Any) -> WorkloadRequest:
    values = dict(WORKLOAD_PROFILES.get(str(profile).strip().lower(), {}))
    values.update(overrides)
    return WorkloadRequest(capability=capability, **values)
