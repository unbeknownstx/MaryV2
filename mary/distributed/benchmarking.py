"""Bounded benchmark/profile helpers for Mary capability nodes.

The benchmark profile is operational evidence only. It contains no prompts,
responses, credentials, memory, or identity data and may be deleted/rebuilt at
any time after hardware/software changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
from statistics import median
from time import perf_counter
from typing import Any, Callable

from .capabilities import CapabilityDescriptor
from .resource_profile import RuntimeResourceProfile


PROFILE_VERSION = "13.11"


def node_id_from_environment() -> str:
    return (
        os.getenv("MARY_NODE_ID", "").strip()
        or os.getenv("COMPUTERNAME", "").strip()
        or socket.gethostname().strip()
        or "mary-node"
    )[:96]


def host_fingerprint(profile: RuntimeResourceProfile | None = None) -> str:
    item = profile or RuntimeResourceProfile.detect()
    raw = f"{item.platform}|{item.machine}|{item.cpu_count}|{item.memory_bytes or 0}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def timed_samples(operation: Callable[[], Any], *, repeats: int = 3) -> tuple[list[float], int]:
    latencies: list[float] = []
    failures = 0
    for _ in range(max(1, min(12, int(repeats)))):
        started = perf_counter()
        try:
            operation()
        except Exception:
            failures += 1
            continue
        latencies.append((perf_counter() - started) * 1000.0)
    return latencies, failures


def cpu_reference_benchmark(*, repeats: int = 3, rounds: int = 90_000) -> dict[str, Any]:
    """Small deterministic CPU reference workload using only stdlib hashlib."""

    payload = b"maryv2-home-compute-fabric-13.11"

    def _work() -> None:
        value = payload
        for _ in range(max(5_000, min(300_000, int(rounds)))):
            value = hashlib.sha256(value).digest()
        if not value:
            raise RuntimeError("unreachable")

    latencies, failures = timed_samples(_work, repeats=repeats)
    total = len(latencies) + failures
    return {
        "operation": "cpu_reference",
        "median_latency_ms": round(median(latencies), 2) if latencies else None,
        "success_rate": round(len(latencies) / total, 3) if total else 0.0,
        "samples": len(latencies),
    }


def benchmark_local_llm(provider: Any, *, repeats: int = 2, max_tokens: int = 24) -> dict[str, Any]:
    """Benchmark an existing local provider with a fixed non-personal prompt."""

    from mary.llm.interface import LLMMessage

    output_tokens: list[int] = []

    def _work() -> None:
        response = provider.generate(
            [LLMMessage(role="user", content="Reply with exactly: benchmark ready")],
            temperature=0.0,
            max_tokens=max(4, min(64, int(max_tokens))),
        )
        usage = dict(getattr(response, "usage", {}) or {})
        output_tokens.append(max(0, int(usage.get("completion_tokens", 0) or 0)))

    latencies, failures = timed_samples(_work, repeats=repeats)
    total = len(latencies) + failures
    median_ms = median(latencies) if latencies else None
    throughput = None
    if median_ms and output_tokens:
        token_median = median([item for item in output_tokens if item >= 0])
        throughput = token_median / (median_ms / 1000.0) if median_ms > 0 else None
    return {
        "model": str(getattr(provider, "model_name", lambda: "")() or "")[:160],
        "num_ctx": int(getattr(provider, "num_ctx", 0) or 0),
        "thinking": bool(getattr(provider, "think", False)),
        "median_latency_ms": round(median_ms, 2) if median_ms is not None else None,
        "success_rate": round(len(latencies) / total, 3) if total else 0.0,
        "samples": len(latencies),
        "throughput_tokens_per_second": round(throughput, 3) if throughput is not None else None,
    }


def build_profile(*, include_local_llm: bool = False, repeats: int = 2) -> dict[str, Any]:
    resource = RuntimeResourceProfile.detect()
    profile: dict[str, Any] = {
        "version": PROFILE_VERSION,
        "node_id": node_id_from_environment(),
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "host_fingerprint": host_fingerprint(resource),
        "resource": resource.to_dict(),
        "cpu_reference": cpu_reference_benchmark(repeats=max(1, repeats)),
        "capabilities": {},
        "authority": "operational_hint_only",
    }

    if include_local_llm:
        try:
            from mary.llm.providers.ollama import OllamaProvider
            provider = OllamaProvider()
            if provider.is_available():
                profile["capabilities"]["llm.ollama"] = benchmark_local_llm(provider, repeats=repeats)
        except Exception:
            profile["capabilities"]["llm.ollama"] = {
                "median_latency_ms": None,
                "success_rate": 0.0,
                "samples": 0,
            }
        try:
            from mary.llm.providers.llama_cpp import LlamaCppProvider
            provider = LlamaCppProvider()
            if provider.is_available():
                profile["capabilities"]["llm.llama_cpp"] = benchmark_local_llm(provider, repeats=repeats)
        except Exception:
            profile["capabilities"].setdefault("llm.llama_cpp", {
                "median_latency_ms": None,
                "success_rate": 0.0,
                "samples": 0,
            })
    return profile


def load_profile(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or str(payload.get("version")) != PROFILE_VERSION:
        raise ValueError("unsupported Mary node benchmark profile")
    if str(payload.get("authority")) != "operational_hint_only":
        raise ValueError("benchmark profile authority marker is invalid")
    return payload


def save_profile(profile: dict[str, Any], path: str | Path) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Round-trip through JSON to prevent accidental non-serializable/runtime
    # objects from entering the profile.
    safe = json.loads(json.dumps(profile, ensure_ascii=False, default=str))
    target.write_text(json.dumps(safe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def apply_benchmark_profile(
    capabilities: list[CapabilityDescriptor],
    profile: dict[str, Any] | None,
) -> list[CapabilityDescriptor]:
    if not profile:
        return list(capabilities)
    capability_results = dict(profile.get("capabilities") or {})
    output: list[CapabilityDescriptor] = []
    for item in capabilities:
        measured = dict(capability_results.get(item.name) or {})
        metadata = dict(item.metadata)

        if measured and item.name.startswith("llm."):
            measured_model = str(measured.get("model") or "").strip()
            configured_model = str(
                metadata.get("configured_model")
                or metadata.get("model")
                or ""
            ).strip()
            measured_ctx = int(measured.get("num_ctx") or 0)
            configured_ctx = int(metadata.get("num_ctx") or 0)
            mismatch = (
                not measured_model
                or (configured_model and measured_model != configured_model)
                or (
                    measured_ctx > 0
                    and configured_ctx > 0
                    and measured_ctx != configured_ctx
                )
            )
            if mismatch:
                metadata["benchmark_ignored_reason"] = (
                    "missing_runtime_fingerprint"
                    if not measured_model
                    else "runtime_fingerprint_mismatch"
                )
                if measured_model:
                    metadata["benchmark_measured_model"] = measured_model[:160]
                output.append(CapabilityDescriptor(
                    name=item.name,
                    available=item.available,
                    private=item.private,
                    local=item.local,
                    cost=item.cost,
                    latency=item.latency,
                    readiness=item.readiness,
                    metadata=metadata,
                ))
                continue

        latency = measured.get("median_latency_ms")
        success = measured.get("success_rate")
        throughput = measured.get("throughput_tokens_per_second")
        if isinstance(latency, (int, float)) and latency >= 0:
            metadata["benchmark_latency_ms"] = round(float(latency), 2)
        if isinstance(success, (int, float)):
            metadata["benchmark_success_rate"] = round(max(0.0, min(1.0, float(success))), 3)
        if isinstance(throughput, (int, float)) and throughput >= 0:
            metadata["benchmark_throughput"] = round(float(throughput), 3)
        if measured:
            metadata["benchmark_profile_version"] = PROFILE_VERSION
            if measured.get("model"):
                metadata["benchmark_model"] = str(measured.get("model"))[:160]
        output.append(CapabilityDescriptor(
            name=item.name,
            available=item.available,
            private=item.private,
            local=item.local,
            cost=item.cost,
            latency=item.latency,
            readiness=item.readiness,
            metadata=metadata,
        ))
    return output
