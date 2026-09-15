"""Bounded benchmark/profile helpers for Mary capability nodes.

The benchmark profile is operational evidence only. It contains no prompts,
responses, credentials, memory, or identity data and may be deleted/rebuilt at
any time after hardware/software changes.

13.37 extends the original latency-only evidence with correctness, token economy
and termination metadata. The fixed benchmark prompts themselves are constants;
raw model responses are never persisted in the profile.
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


# Keep the on-disk profile wire version stable for existing node profiles.
PROFILE_VERSION = "13.11"
RELIABILITY_REVISION = "13.37"


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    prompt: str
    expected: Callable[[str], bool]
    max_tokens: int = 96


def _contains_last_integer(expected: int) -> Callable[[str], bool]:
    def _check(text: str) -> bool:
        import re
        values = re.findall(r"-?\d+", str(text or ""))
        return bool(values) and int(values[-1]) == expected
    return _check


STANDARD_LLM_CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        name="instruction",
        prompt="Reply with exactly: benchmark ready",
        expected=lambda text: str(text or "").strip().lower() == "benchmark ready",
        max_tokens=12,
    ),
    BenchmarkCase(
        name="reasoning",
        prompt="A farmer has 17 sheep. All but 9 run away. How many sheep are left? End with the number only.",
        expected=_contains_last_integer(9),
        max_tokens=96,
    ),
    BenchmarkCase(
        name="structured",
        prompt='Return exactly this JSON object and nothing else: {"mary_benchmark":true,"value":7}',
        expected=lambda text: _valid_structured_benchmark(text),
        max_tokens=48,
    ),
)


def _valid_structured_benchmark(text: str) -> bool:
    try:
        value = json.loads(str(text or "").strip())
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    return isinstance(value, dict) and value == {"mary_benchmark": True, "value": 7}


def useful_throughput(tokens_per_second: float | None, correctness: float | None) -> float | None:
    """Quality-adjusted throughput: fast wrong output is not useful throughput."""
    if tokens_per_second is None:
        return None
    speed = max(0.0, float(tokens_per_second))
    if correctness is None:
        return speed
    return speed * max(0.0, min(1.0, float(correctness)))


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


def _usage_int(response: Any, key: str) -> int:
    usage = dict(getattr(response, "usage", {}) or {})
    try:
        return max(0, int(usage.get(key, 0) or 0))
    except (TypeError, ValueError):
        return 0


def benchmark_local_llm(
    provider: Any,
    *,
    repeats: int = 2,
    max_tokens: int = 24,
    quality_suite: bool = False,
) -> dict[str, Any]:
    """Benchmark an existing local provider with fixed non-personal prompts.

    ``quality_suite=False`` preserves the inexpensive historical probe. When
    explicitly enabled, Mary runs a three-case deterministic suite and stores
    only verdicts/metrics, never response text.
    """

    from mary.llm.interface import LLMMessage

    cases = STANDARD_LLM_CASES if quality_suite else (
        BenchmarkCase(
            name="instruction",
            prompt="Reply with exactly: benchmark ready",
            expected=lambda text: str(text or "").strip().lower() == "benchmark ready",
            max_tokens=max(4, min(64, int(max_tokens))),
        ),
    )
    samples = max(1, min(8, int(repeats)))
    latencies: list[float] = []
    output_tokens: list[int] = []
    correct: list[bool] = []
    finish_reasons: list[str] = []
    failures = 0

    for _ in range(samples):
        for case in cases:
            started = perf_counter()
            try:
                response = provider.generate(
                    [LLMMessage(role="user", content=case.prompt)],
                    temperature=0.0,
                    max_tokens=max(4, min(256, int(case.max_tokens))),
                )
            except Exception:
                failures += 1
                continue
            latencies.append((perf_counter() - started) * 1000.0)
            content = str(getattr(response, "content", "") or "")
            correct.append(bool(case.expected(content)))
            output_tokens.append(_usage_int(response, "completion_tokens"))
            finish_reasons.append(str(getattr(response, "finish_reason", "") or "")[:40])

    total_attempts = len(latencies) + failures
    median_ms = median(latencies) if latencies else None
    throughput = None
    if median_ms and output_tokens:
        nonzero = [item for item in output_tokens if item > 0]
        if nonzero:
            throughput = median(nonzero) / (median_ms / 1000.0) if median_ms > 0 else None
    accuracy = (sum(1 for item in correct if item) / len(correct)) if correct else None
    useful = useful_throughput(throughput, accuracy)
    truncated = sum(1 for reason in finish_reasons if reason.lower() in {"length", "max_tokens"})

    return {
        "model": str(getattr(provider, "model_name", lambda: "")() or "")[:160],
        "num_ctx": int(getattr(provider, "num_ctx", 0) or 0),
        "thinking": bool(getattr(provider, "think", False)),
        "median_latency_ms": round(median_ms, 2) if median_ms is not None else None,
        "success_rate": round(len(latencies) / total_attempts, 3) if total_attempts else 0.0,
        "correctness_rate": round(accuracy, 3) if accuracy is not None else None,
        "samples": len(latencies),
        "cases": [case.name for case in cases],
        "median_output_tokens": round(median(output_tokens), 2) if output_tokens else None,
        "throughput_tokens_per_second": round(throughput, 3) if throughput is not None else None,
        "useful_throughput": round(useful, 3) if useful is not None else None,
        "truncated_runs": truncated,
        "reliability_revision": RELIABILITY_REVISION,
        "raw_outputs_retained": False,
    }


def build_profile(*, include_local_llm: bool = False, repeats: int = 2, quality_suite: bool | None = None) -> dict[str, Any]:
    resource = RuntimeResourceProfile.detect()
    if quality_suite is None:
        quality_suite = os.getenv("MARY_NODE_BENCHMARK_QUALITY", "").strip().lower() in {"1", "true", "yes", "on"}
    profile: dict[str, Any] = {
        "version": PROFILE_VERSION,
        "reliability_revision": RELIABILITY_REVISION,
        "node_id": node_id_from_environment(),
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "host_fingerprint": host_fingerprint(resource),
        "resource": resource.to_dict(),
        "cpu_reference": cpu_reference_benchmark(repeats=max(1, repeats)),
        "capabilities": {},
        "authority": "operational_hint_only",
        "content_retained": False,
    }

    if include_local_llm:
        try:
            from mary.llm.providers.ollama import OllamaProvider
            provider = OllamaProvider()
            if provider.is_available():
                profile["capabilities"]["llm.ollama"] = benchmark_local_llm(
                    provider,
                    repeats=repeats,
                    quality_suite=bool(quality_suite),
                )
        except Exception:
            profile["capabilities"]["llm.ollama"] = {
                "median_latency_ms": None,
                "success_rate": 0.0,
                "samples": 0,
                "reliability_revision": RELIABILITY_REVISION,
            }
        try:
            from mary.llm.providers.llama_cpp import LlamaCppProvider
            provider = LlamaCppProvider()
            if provider.is_available():
                profile["capabilities"]["llm.llama_cpp"] = benchmark_local_llm(
                    provider,
                    repeats=repeats,
                    quality_suite=bool(quality_suite),
                )
        except Exception:
            profile["capabilities"].setdefault("llm.llama_cpp", {
                "median_latency_ms": None,
                "success_rate": 0.0,
                "samples": 0,
                "reliability_revision": RELIABILITY_REVISION,
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
            configured_model = str(metadata.get("configured_model") or metadata.get("model") or "").strip()
            measured_ctx = int(measured.get("num_ctx") or 0)
            configured_ctx = int(metadata.get("num_ctx") or 0)
            mismatch = (
                not measured_model
                or (configured_model and measured_model != configured_model)
                or (measured_ctx > 0 and configured_ctx > 0 and measured_ctx != configured_ctx)
            )
            if mismatch:
                metadata["benchmark_ignored_reason"] = (
                    "missing_runtime_fingerprint" if not measured_model else "runtime_fingerprint_mismatch"
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

        metrics = {
            "benchmark_latency_ms": measured.get("median_latency_ms"),
            "benchmark_success_rate": measured.get("success_rate"),
            "benchmark_throughput": measured.get("throughput_tokens_per_second"),
            "benchmark_accuracy": measured.get("correctness_rate"),
            "benchmark_useful_throughput": measured.get("useful_throughput"),
            "benchmark_output_tokens": measured.get("median_output_tokens"),
            "benchmark_truncated_runs": measured.get("truncated_runs"),
        }
        for key, value in metrics.items():
            if not isinstance(value, (int, float)):
                continue
            if key.endswith("rate") or key.endswith("accuracy"):
                metadata[key] = round(max(0.0, min(1.0, float(value))), 3)
            elif float(value) >= 0:
                metadata[key] = round(float(value), 3)
        if measured:
            metadata["benchmark_profile_version"] = PROFILE_VERSION
            metadata["benchmark_reliability_revision"] = str(measured.get("reliability_revision") or profile.get("reliability_revision") or "")[:32]
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
