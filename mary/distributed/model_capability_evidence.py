"""Measured capability evidence for exact local model instances.

The probe contract stores outcomes, never prompt/response content or hidden
reasoning. It is deliberately adapter-neutral: Ollama, llama.cpp, LM Studio,
vLLM, or another local engine can supply bounded probe callables while the
result projects into Mary's 13.39 measured-capability metadata.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import monotonic
from typing import Any, Callable, Mapping

VERSION = "13.44"


@dataclass(frozen=True)
class CapabilityProbeResult:
    capability: str
    supported: bool | None
    latency_ms: float | None = None
    error_class: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Detail is structural only; discard arbitrary nested/provider prose.
        payload["detail"] = {
            str(key)[:80]: value
            for key, value in list(self.detail.items())[:12]
            if isinstance(value, (bool, int, float, type(None)))
        }
        return payload


@dataclass(frozen=True)
class ModelCapabilityEvidence:
    qualified_model_id: str
    model_fingerprint: str
    probes: tuple[CapabilityProbeResult, ...]
    loaded_context: int | None = None
    trained_context: int | None = None
    version: str = VERSION
    authority: str = "measured_runtime_evidence_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "qualified_model_id": self.qualified_model_id,
            "model_fingerprint": self.model_fingerprint,
            "loaded_context": self.loaded_context,
            "trained_context": self.trained_context,
            "probes": [item.to_dict() for item in self.probes],
            "authority": self.authority,
        }

    def metadata_overlay(self) -> dict[str, Any]:
        """Return sanitized metadata understood by model-instance projection."""
        output: dict[str, Any] = {}
        key_map = {
            "tools": "measured_tools",
            "vision": "measured_vision",
            "thinking": "measured_thinking",
            "embeddings": "measured_embeddings",
            "structured_json": "measured_structured_json",
        }
        for probe in self.probes:
            key = key_map.get(probe.capability)
            if key and probe.supported is not None:
                output[key] = bool(probe.supported)
            if probe.latency_ms is not None:
                output[f"probe_{probe.capability}_latency_ms"] = round(
                    max(0.0, float(probe.latency_ms)), 3
                )
        if self.loaded_context is not None:
            output["loaded_context"] = max(1, int(self.loaded_context))
            output["loaded_context_source"] = "measured"
        if self.trained_context is not None:
            output["trained_context"] = max(1, int(self.trained_context))
            output["trained_context_source"] = "measured"
        output["capability_probe_version"] = VERSION
        output["capability_probe_fingerprint"] = self.model_fingerprint[:64]
        return output


def _error_class(exc: BaseException) -> str:
    name = type(exc).__name__.lower()
    if isinstance(exc, TimeoutError) or "timeout" in name:
        return "timeout"
    if isinstance(exc, PermissionError):
        return "permission"
    if isinstance(exc, ConnectionError):
        return "transport"
    return "probe_failed"


def run_boolean_probe(
    capability: str,
    probe: Callable[[], bool | None],
    *,
    deadline_ms: float = 5000.0,
) -> CapabilityProbeResult:
    """Run one already-bounded adapter probe and normalize structural evidence."""
    name = str(capability or "").strip().lower()[:80]
    if not name:
        raise ValueError("capability name is required")
    started = monotonic()
    try:
        value = probe()
        elapsed = (monotonic() - started) * 1000.0
        if elapsed > max(1.0, float(deadline_ms)):
            return CapabilityProbeResult(name, None, round(elapsed, 3), "deadline_exceeded")
        supported = None if value is None else bool(value)
        return CapabilityProbeResult(name, supported, round(elapsed, 3), None)
    except Exception as exc:
        elapsed = (monotonic() - started) * 1000.0
        return CapabilityProbeResult(
            name,
            None,
            round(elapsed, 3),
            _error_class(exc),
        )


def build_capability_evidence(
    *,
    qualified_model_id: str,
    model_fingerprint: str,
    probes: Mapping[str, Callable[[], bool | None]],
    loaded_context: int | None = None,
    trained_context: int | None = None,
    deadline_ms: float = 5000.0,
) -> ModelCapabilityEvidence:
    """Evaluate a bounded set of structural probes for one exact model runtime."""
    qualified = str(qualified_model_id or "").strip()[:300]
    fingerprint = str(model_fingerprint or "").strip()[:64]
    if not qualified or not fingerprint:
        raise ValueError("qualified model id and fingerprint are required")
    rows = tuple(
        run_boolean_probe(name, callback, deadline_ms=deadline_ms)
        for name, callback in list(probes.items())[:12]
        if callable(callback)
    )
    return ModelCapabilityEvidence(
        qualified_model_id=qualified,
        model_fingerprint=fingerprint,
        probes=rows,
        loaded_context=(max(1, int(loaded_context)) if loaded_context else None),
        trained_context=(max(1, int(trained_context)) if trained_context else None),
    )
