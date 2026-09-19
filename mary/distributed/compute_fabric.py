"""Adaptive, benchmark-aware scheduling for Mary's replaceable compute nodes.

This module does not own identity, memory, permissions, or durable truth. It
ranks already-advertised capabilities using bounded runtime evidence so the same
Mary Core can make useful use of heterogeneous Mac/Windows/cloud resources.

13.54 adds explicit-hint-only accelerator fit planning. A node may advertise a
measured/configured per-role accelerator-memory footprint; absent that hint,
fit remains unknown and existing selection behavior is preserved.
13.55 records one bounded content-free adaptive routing explanation for
observability; prompts, task args, results, and credentials are never retained.
13.56 binds live benchmark and durable competence hints to a capability's
execution-relevant implementation fingerprint when one is advertised.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from statistics import median
from threading import RLock
from typing import Any, Iterable

from .capabilities import capability_implementation_fingerprint
from .nodes import NodeDescriptor, NodeRegistry
from .resource_broker import ResourceSnapshot, WorkloadFootprint, plan_resource_handoff


@dataclass(frozen=True)
class BenchmarkSample:
    node_id: str
    capability: str
    operation: str
    latency_ms: float
    success: bool = True
    throughput: float | None = None
    implementation_fingerprint: str = ""
    measured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BenchmarkBook:
    """Small process-local benchmark and routing-evidence store.

    Evidence is operational only. It is intentionally not Mary memory and may
    be discarded on restart or rebuilt after hardware changes.
    """

    VERSION = "13.11"
    ROUTING_REVISION = "13.55"

    def __init__(self, *, max_samples_per_key: int = 12) -> None:
        self.max_samples_per_key = max(3, min(50, int(max_samples_per_key)))
        self._lock = RLock()
        self._samples: dict[tuple[str, str, str, str], list[BenchmarkSample]] = {}
        self._last_adaptive_decision: dict[str, Any] = {}

    def record(self, sample: BenchmarkSample) -> None:
        key = (
            str(sample.node_id).strip(),
            str(sample.capability).strip().lower(),
            str(sample.operation).strip().lower(),
            str(sample.implementation_fingerprint or "").strip().lower()[:64],
        )
        if not all(key[:3]):
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
                    implementation_fingerprint=str(
                        item.get("implementation_fingerprint") or ""
                    ).strip().lower()[:64],
                    measured_at=str(item.get("measured_at") or datetime.now(timezone.utc).isoformat())[:80],
                ))
            except (TypeError, ValueError):
                continue

    def summary(
        self,
        node_id: str,
        capability: str,
        operation: str = "general",
        implementation_fingerprint: str = "",
    ) -> dict[str, Any]:
        key = (
            str(node_id).strip(),
            str(capability).strip().lower(),
            str(operation).strip().lower(),
            str(implementation_fingerprint or "").strip().lower()[:64],
        )
        with self._lock:
            samples = list(self._samples.get(key, []))
            if not samples and key[2] != "general":
                samples = list(
                    self._samples.get((key[0], key[1], "general", key[3]), [])
                )
        successes = [item for item in samples if item.success]
        latencies = [item.latency_ms for item in successes]
        throughputs = [item.throughput for item in successes if item.throughput is not None]
        return {
            "samples": len(samples),
            "success_rate": round(len(successes) / len(samples), 3) if samples else None,
            "median_latency_ms": round(median(latencies), 2) if latencies else None,
            "median_throughput": round(median(throughputs), 3) if throughputs else None,
            "implementation_fingerprint": key[3],
            "authority": "operational_hint_only",
        }

    def record_adaptive_decision(
        self,
        *,
        capability: str,
        operation: str,
        selected_node_id: str | None,
        outcome: str,
        candidates: Iterable[dict[str, Any]],
    ) -> None:
        safe_candidates: list[dict[str, Any]] = []
        for raw in list(candidates)[:8]:
            item = dict(raw or {})
            benchmark = dict(item.get("benchmark") or {})
            competence = dict(item.get("competence") or {})
            safe_candidates.append({
                "node_id": str(item.get("node_id") or "")[:160],
                "score": round(float(item.get("score") or 0.0), 3),
                "reason": str(item.get("reason") or "")[:240],
                "load_pressure": round(max(0.0, min(1.0, float(item.get("load_pressure") or 0.0))), 3),
                "competence": {
                    "attempts": max(0, int(competence.get("attempts") or 0)),
                    "reliability": competence.get("reliability"),
                    "evidence_strength": competence.get("evidence_strength"),
                    "freshness": competence.get("freshness"),
                    "score_delta": competence.get("score_delta"),
                    "implementation_fingerprint": competence.get(
                        "implementation_fingerprint", ""
                    ),
                    "stale_records": max(
                        0, int(competence.get("stale_records") or 0)
                    ),
                    "authority": "routing_hint_only",
                },
                "benchmark": {
                    "samples": max(0, int(benchmark.get("samples") or 0)),
                    "success_rate": benchmark.get("success_rate"),
                    "median_latency_ms": benchmark.get("median_latency_ms"),
                    "median_throughput": benchmark.get("median_throughput"),
                    "implementation_fingerprint": benchmark.get(
                        "implementation_fingerprint", ""
                    ),
                    "authority": "operational_hint_only",
                },
            })
        decision = {
            "revision": self.ROUTING_REVISION,
            "capability": str(capability or "").strip().lower()[:80],
            "operation": str(operation or "general").strip().lower()[:80],
            "selected_node_id": (str(selected_node_id)[:160] if selected_node_id else None),
            "outcome": str(outcome or "unknown")[:80],
            "candidates": safe_candidates,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "authority": "operational_observation_only",
            "content_retained": False,
        }
        with self._lock:
            self._last_adaptive_decision = decision

    def last_adaptive_decision(self) -> dict[str, Any]:
        with self._lock:
            return {
                **self._last_adaptive_decision,
                "candidates": [dict(item) for item in self._last_adaptive_decision.get("candidates", [])],
            } if self._last_adaptive_decision else {}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            items = [sample.to_dict() for values in self._samples.values() for sample in values]
            decision = {
                **self._last_adaptive_decision,
                "candidates": [dict(item) for item in self._last_adaptive_decision.get("candidates", [])],
            } if self._last_adaptive_decision else {}
        return {
            "version": self.VERSION,
            "routing_revision": self.ROUTING_REVISION,
            "samples": items,
            "last_adaptive_decision": decision,
            "authority": "operational_hint_only",
            "content_retained": False,
        }


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
    accelerator_fraction: float | None = None
    memory_total_gib: float | None = None
    memory_free_gib: float | None = None
    accelerator_total_gib: float | None = None
    accelerator_free_gib: float | None = None
    unified_memory: bool = False
    stream_critical: bool = False

    @property
    def pressure(self) -> float:
        pressure = min(1.0, 0.28 * self.active_realtime + 0.12 * self.active_background)
        for value in (self.cpu_fraction, self.memory_fraction, self.accelerator_fraction):
            if value is not None:
                pressure = max(pressure, max(0.0, min(1.0, float(value))))
        return pressure


def _explicit_accelerator_requirement(metadata: dict[str, Any], operation: str) -> float | None:
    """Read a bounded explicit footprint hint; never infer one from a model ID."""
    role = {
        "conversation": "conversation",
        "quick_answer": "fast",
        "utility": "utility",
        "general": "general",
    }.get(str(operation or "general").strip().lower(), "general")
    values = dict(metadata or {})
    raw = values.get(f"resource_accelerator_gib_{role}")
    if raw is None and role != "general":
        raw = values.get("resource_accelerator_gib_general")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        required = float(raw)
    except (TypeError, ValueError):
        return None
    if required <= 0.0 or required > 4096.0:
        return None
    return round(required, 3)


def _metadata_number(metadata: dict[str, Any], key: str) -> float | None:
    raw = dict(metadata or {}).get(key)
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value


class HomeComputeScheduler:
    """Rank node candidates without granting execution permission.

    The task broker remains the execution boundary. This class only provides a
    better selection decision using readiness, privacy, cost, measured latency,
    explicit fit evidence, and live load.
    """

    VERSION = "13.56"

    def __init__(
        self,
        registry: NodeRegistry,
        *,
        benchmarks: BenchmarkBook | None = None,
        competence: Any | None = None,
    ) -> None:
        self.registry = registry
        self.benchmarks = benchmarks or BenchmarkBook()
        self.competence = competence
        self._loads: dict[str, NodeLoad] = {}
        self._lock = RLock()

    def update_load(self, load: NodeLoad) -> None:
        with self._lock:
            self._loads[str(load.node_id)] = load

    def load_for(self, node_id: str) -> NodeLoad:
        with self._lock:
            return self._loads.get(str(node_id), NodeLoad(node_id=str(node_id)))

    def _competence_hint(
        self,
        node_id: str,
        capability: str,
        operation: str,
    ) -> dict[str, Any]:
        """Return a small, decayed routing hint from durable outcome evidence.

        The hint never creates candidates or bypasses readiness, privacy,
        permission, or resource-fit checks. Sparse evidence is intentionally
        weak, and old evidence decays because node hardware/runtime can change.
        """
        node = self.registry.get(node_id)
        descriptor = (
            node.capabilities.get(str(capability).strip().lower())
            if node is not None
            else None
        )
        implementation_fingerprint = capability_implementation_fingerprint(
            descriptor
        )
        empty = {
            "attempts": 0,
            "reliability": None,
            "evidence_strength": 0.0,
            "freshness": 0.0,
            "score_delta": 0.0,
            "verified_successes": 0,
            "last_observed_at": "",
            "implementation_fingerprint": implementation_fingerprint,
            "stale_records": 0,
            "authority": "routing_hint_only",
        }
        summary = getattr(self.competence, "summary_for", None)
        if not callable(summary):
            return empty
        try:
            summary_kwargs: dict[str, Any] = {
                "operation": operation,
                "node_ids": (node_id,),
                "limit": 8,
            }
            if implementation_fingerprint:
                summary_kwargs["implementation_fingerprint"] = (
                    implementation_fingerprint
                )
            rows = list(summary(capability, **summary_kwargs) or [])
            exact = [
                dict(row) for row in rows
                if str(row.get("node_id") or "") == str(node_id)
            ]
            if not exact and str(operation or "general").casefold() != "general":
                general_kwargs: dict[str, Any] = {
                    "operation": "general",
                    "node_ids": (node_id,),
                    "limit": 8,
                }
                if implementation_fingerprint:
                    general_kwargs["implementation_fingerprint"] = (
                        implementation_fingerprint
                    )
                rows = list(summary(capability, **general_kwargs) or [])
                exact = [
                    dict(row) for row in rows
                    if str(row.get("node_id") or "") == str(node_id)
                ]
        except TypeError:
            try:
                rows = list(summary(
                    capability,
                    operation=operation,
                    node_ids=(node_id,),
                    limit=8,
                ) or [])
            except Exception:
                return empty
            if implementation_fingerprint:
                rows = [
                    row
                    for row in rows
                    if isinstance(row, dict)
                    and str(
                        row.get("implementation_fingerprint") or ""
                    ).casefold()
                    == implementation_fingerprint
                ]
            exact = [
                dict(row) for row in rows
                if str(row.get("node_id") or "") == str(node_id)
            ]
            if not exact and str(operation or "general").casefold() != "general":
                try:
                    rows = list(summary(
                        capability,
                        operation="general",
                        node_ids=(node_id,),
                        limit=8,
                    ) or [])
                except Exception:
                    rows = []
                if implementation_fingerprint:
                    rows = [
                        row
                        for row in rows
                        if isinstance(row, dict)
                        and str(
                            row.get("implementation_fingerprint") or ""
                        ).casefold()
                        == implementation_fingerprint
                    ]
                exact = [
                    dict(row) for row in rows
                    if str(row.get("node_id") or "") == str(node_id)
                ]
        except Exception:
            return empty

        stale_records = 0
        if implementation_fingerprint:
            try:
                all_rows = list(summary(
                    capability,
                    operation=operation,
                    node_ids=(node_id,),
                    limit=64,
                ) or [])
            except Exception:
                all_rows = []
            stale_records = sum(
                1
                for item in all_rows
                if isinstance(item, dict)
                and int(item.get("attempts") or 0) > 0
                and str(
                    item.get("implementation_fingerprint") or ""
                ).casefold()
                != implementation_fingerprint
            )
        if not exact:
            return {**empty, "stale_records": stale_records}
        row = max(
            exact,
            key=lambda item: (
                float(item.get("evidence_strength") or 0.0),
                int(item.get("attempts") or 0),
                str(item.get("last_observed_at") or ""),
            ),
        )
        try:
            reliability = max(0.0, min(1.0, float(row.get("reliability") or 0.5)))
            strength = max(0.0, min(1.0, float(row.get("evidence_strength") or 0.0)))
        except (TypeError, ValueError):
            return empty

        freshness = 1.0
        observed = str(row.get("last_observed_at") or "").strip()
        if observed:
            try:
                parsed = datetime.fromisoformat(observed.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                age_days = max(
                    0.0,
                    (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
                    / 86400.0,
                )
                freshness = 0.5 ** (age_days / 30.0)
            except (TypeError, ValueError):
                freshness = 0.5
        effective_strength = strength * freshness
        score_delta = 10.0 * (2.0 * (reliability - 0.5)) * effective_strength
        return {
            "attempts": max(0, int(row.get("attempts") or 0)),
            "reliability": round(reliability, 4),
            "evidence_strength": round(strength, 4),
            "freshness": round(freshness, 4),
            "score_delta": round(max(-10.0, min(10.0, score_delta)), 3),
            "verified_successes": max(0, int(row.get("verified_successes") or 0)),
            "last_observed_at": observed[:80],
            "implementation_fingerprint": implementation_fingerprint,
            "stale_records": stale_records,
            "authority": "routing_hint_only",
        }

    def has_competence_evidence(
        self,
        capability: str,
        operation: str,
        node_ids: Iterable[str],
    ) -> bool:
        return any(
            int(self._competence_hint(node_id, capability, operation).get("attempts") or 0) > 0
            for node_id in node_ids
        )

    def _fit_plan(self, node: NodeDescriptor, request: WorkloadRequest, load: NodeLoad):
        cap = node.capabilities[request.capability]
        required = _explicit_accelerator_requirement(dict(cap.metadata or {}), request.operation)
        if required is None:
            return None
        snapshot = ResourceSnapshot(
            node_id=node.node_id,
            ram_total_gb=load.memory_total_gib,
            ram_free_gb=load.memory_free_gib,
            vram_total_gb=load.accelerator_total_gib,
            vram_free_gb=load.accelerator_free_gib,
            active_realtime=bool(load.stream_critical),
        )
        return plan_resource_handoff(
            snapshot,
            WorkloadFootprint(
                name=f"{request.capability}:{request.operation}",
                vram_gb=required,
                realtime=bool(request.realtime),
            ),
            policy="auto",
        )

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

        load = self.load_for(node.node_id)
        fit = self._fit_plan(node, request, load)
        if fit is not None:
            if fit.status == "infeasible":
                return (-10_000.0, f"resource_infeasible:{fit.reason}")
            if fit.status == "fits":
                score += 8.0
                reasons.append("resource_fit")
            elif fit.status in {"handoff", "prefer_other_node"}:
                score -= 36.0
                reasons.append(f"resource_{fit.status}")
            elif fit.status == "unknown":
                reasons.append("resource_fit_unknown")

        implementation_fingerprint = capability_implementation_fingerprint(cap)
        bench = self.benchmarks.summary(
            node.node_id,
            request.capability,
            request.operation,
            implementation_fingerprint=implementation_fingerprint,
        )
        latency = bench.get("median_latency_ms")
        success_rate = bench.get("success_rate")
        static = dict(cap.metadata or {})
        static_used = False
        if success_rate is None:
            candidate = _metadata_number(static, "benchmark_success_rate")
            if candidate is not None and 0.0 <= candidate <= 1.0:
                success_rate = candidate
                static_used = True
        if latency is None:
            candidate = _metadata_number(static, "benchmark_latency_ms")
            if candidate is not None and candidate >= 0.0:
                latency = candidate
                static_used = True
        if success_rate is not None:
            score += 18.0 * float(success_rate)
            reasons.append(f"{'static_' if static_used and bench.get('samples', 0) == 0 else ''}success={success_rate:.2f}")
        if latency is not None:
            budget = 2500.0 if request.realtime else 15_000.0
            latency_factor = max(0.0, 1.0 - min(float(latency), budget) / budget)
            score += (28.0 if request.realtime else 12.0) * latency_factor
            reasons.append(f"{'static_' if static_used and bench.get('samples', 0) == 0 else ''}median={latency:.0f}ms")

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

    def rank(
        self,
        request: WorkloadRequest,
        *,
        allowed_node_ids: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
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
        allowed = (
            None
            if allowed_node_ids is None
            else {str(node_id) for node_id in allowed_node_ids if str(node_id)}
        )
        ranked = []
        for node in self.registry.candidates(capability):
            if allowed is not None and node.node_id not in allowed:
                continue
            score, reason = self._score(node, normalized)
            if score <= -9000:
                continue
            competence = self._competence_hint(
                node.node_id,
                capability,
                normalized.operation,
            )
            score += float(competence.get("score_delta") or 0.0)
            delta = float(competence.get("score_delta") or 0.0)
            if abs(delta) >= 0.05:
                reason = (
                    f"{reason},competence={delta:+.2f}"
                    f"/strength={float(competence.get('evidence_strength') or 0.0):.2f}"
                    f"/fresh={float(competence.get('freshness') or 0.0):.2f}"
                )
            load = self.load_for(node.node_id)
            ranked.append({
                "node_id": node.node_id,
                "score": round(score, 3),
                "reason": reason,
                "load_pressure": round(load.pressure, 3),
                "benchmark": self.benchmarks.summary(
                    node.node_id,
                    capability,
                    normalized.operation,
                    implementation_fingerprint=capability_implementation_fingerprint(
                        node.capabilities[capability]
                    ),
                ),
                "competence": competence,
            })
        ranked.sort(key=lambda item: (-float(item["score"]), str(item["node_id"])))
        return ranked

    def choose(
        self,
        request: WorkloadRequest,
        *,
        allowed_node_ids: Iterable[str] | None = None,
    ) -> NodeDescriptor | None:
        ranked = self.rank(request, allowed_node_ids=allowed_node_ids)
        if ranked:
            selected_id = str(ranked[0]["node_id"])
            self.benchmarks.record_adaptive_decision(
                capability=request.capability,
                operation=request.operation,
                selected_node_id=selected_id,
                outcome="selected",
                candidates=ranked,
            )
            return self.registry.get(selected_id)
        allowed = (
            None
            if allowed_node_ids is None
            else {str(node_id) for node_id in allowed_node_ids if str(node_id)}
        )
        candidates = [
            node
            for node in self.registry.candidates(str(request.capability).strip().lower())
            if allowed is None or node.node_id in allowed
        ]
        if candidates:
            plans = [self._fit_plan(node, request, self.load_for(node.node_id)) for node in candidates]
            if plans and all(plan is not None and plan.status == "infeasible" for plan in plans):
                rejected = []
                for node, plan in zip(candidates, plans):
                    load = self.load_for(node.node_id)
                    rejected.append({
                        "node_id": node.node_id,
                        "score": -10_000.0,
                        "reason": f"resource_infeasible:{plan.reason}",
                        "load_pressure": round(load.pressure, 3),
                        "benchmark": self.benchmarks.summary(
                            node.node_id,
                            request.capability,
                            request.operation,
                            implementation_fingerprint=capability_implementation_fingerprint(
                                node.capabilities[request.capability]
                            ),
                        ),
                    })
                self.benchmarks.record_adaptive_decision(
                    capability=request.capability,
                    operation=request.operation,
                    selected_node_id=None,
                    outcome="measured_no_fit",
                    candidates=rejected,
                )
                raise LookupError(
                    f"No eligible node has measured accelerator capacity for {request.capability}:{request.operation}."
                )
        self.benchmarks.record_adaptive_decision(
            capability=request.capability,
            operation=request.operation,
            selected_node_id=None,
            outcome="no_ranked_candidate",
            candidates=(),
        )
        return None

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
            "policy": "selection never grants permission; explicit fit hints never trigger automatic resource eviction",
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