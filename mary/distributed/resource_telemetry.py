"""Strict transport-safe resource telemetry for Mary capability nodes.

This module converts a tiny allowlisted resource report into scheduler pressure.
It is operational evidence only: no paths, process names, model names, prompts,
results, environment variables, or arbitrary metadata are accepted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

from .compute_fabric import NodeLoad


VERSION = "13.53"
_ALLOWED_KEYS = {
    "ram_total_gib",
    "ram_free_gib",
    "vram_total_gib",
    "vram_free_gib",
    "apple_unified_memory",
    "source",
}
_MAX_GIB = 1_048_576.0
_ALLOWED_SOURCES = {
    "nvidia_smi",
    "rocm_smi",
    "win32_videocontroller_hint",
    "system_memory",
    "apple_unified_memory",
    "environment_hint",
    "mixed",
    "unknown",
}


def _bounded_gib(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric or null.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric or null.") from exc
    if not math.isfinite(number) or number < 0.0 or number > _MAX_GIB:
        raise ValueError(f"{field_name} is outside the supported range.")
    return round(number, 3)


@dataclass(frozen=True)
class ResourceTelemetry:
    ram_total_gib: float | None = None
    ram_free_gib: float | None = None
    vram_total_gib: float | None = None
    vram_free_gib: float | None = None
    apple_unified_memory: bool = False
    source: str = "unknown"

    @property
    def memory_fraction(self) -> float | None:
        return _used_fraction(self.ram_total_gib, self.ram_free_gib)

    @property
    def accelerator_fraction(self) -> float | None:
        if self.apple_unified_memory and self.vram_total_gib is None:
            return self.memory_fraction
        return _used_fraction(self.vram_total_gib, self.vram_free_gib)

    def transport_dict(self) -> dict[str, Any]:
        """Return only fields permitted to cross the node/Core boundary."""
        return asdict(self)

    def to_dict(self) -> dict[str, Any]:
        payload = self.transport_dict()
        payload["memory_fraction"] = self.memory_fraction
        payload["accelerator_fraction"] = self.accelerator_fraction
        payload["authority"] = "operational_measurement_only"
        return payload


def _used_fraction(total: float | None, free: float | None) -> float | None:
    if total is None or free is None or total <= 0:
        return None
    return round(max(0.0, min(1.0, 1.0 - free / total)), 4)


def sanitize_resource_telemetry(payload: dict[str, Any] | None) -> ResourceTelemetry:
    values = dict(payload or {})
    unknown = sorted(set(values) - _ALLOWED_KEYS)
    if unknown:
        raise ValueError("Unsupported resource telemetry fields: " + ", ".join(unknown))

    unified = values.get("apple_unified_memory", False)
    if not isinstance(unified, bool):
        raise ValueError("apple_unified_memory must be boolean.")

    source = str(values.get("source") or "unknown").strip().lower()
    if source not in _ALLOWED_SOURCES:
        source = "unknown"

    report = ResourceTelemetry(
        ram_total_gib=_bounded_gib(values.get("ram_total_gib"), "ram_total_gib"),
        ram_free_gib=_bounded_gib(values.get("ram_free_gib"), "ram_free_gib"),
        vram_total_gib=_bounded_gib(values.get("vram_total_gib"), "vram_total_gib"),
        vram_free_gib=_bounded_gib(values.get("vram_free_gib"), "vram_free_gib"),
        apple_unified_memory=unified,
        source=source,
    )

    if report.ram_total_gib is not None and report.ram_free_gib is not None:
        if report.ram_free_gib > report.ram_total_gib:
            raise ValueError("ram_free_gib cannot exceed ram_total_gib.")
    if report.vram_total_gib is not None and report.vram_free_gib is not None:
        if report.vram_free_gib > report.vram_total_gib:
            raise ValueError("vram_free_gib cannot exceed vram_total_gib.")
    return report


def merge_resource_load(base: NodeLoad, telemetry: ResourceTelemetry) -> NodeLoad:
    """Add measured resource pressure without changing task-count pressure."""
    return NodeLoad(
        node_id=base.node_id,
        active_realtime=base.active_realtime,
        active_background=base.active_background,
        cpu_fraction=base.cpu_fraction,
        memory_fraction=telemetry.memory_fraction,
        accelerator_fraction=telemetry.accelerator_fraction,
        stream_critical=base.stream_critical,
    )


def telemetry_from_observation(observation: Any) -> dict[str, Any]:
    """Project a 13.40 LiveResourceObservation into the transport-safe shape."""
    primary = getattr(observation, "primary_gpu", None)
    sources = []
    if primary is not None:
        sources.append(str(getattr(primary, "source", "") or ""))
    if getattr(observation, "ram_total_gib", None) is not None:
        sources.append("system_memory")
    clean_sources = {item for item in sources if item}
    source = next(iter(clean_sources)) if len(clean_sources) == 1 else ("mixed" if clean_sources else "unknown")
    payload = {
        "ram_total_gib": getattr(observation, "ram_total_gib", None),
        "ram_free_gib": getattr(observation, "ram_free_gib", None),
        "vram_total_gib": (getattr(primary, "total_gib", None) if primary is not None else None),
        "vram_free_gib": (getattr(primary, "free_gib", None) if primary is not None else None),
        "apple_unified_memory": bool(getattr(observation, "apple_unified_memory", False)),
        "source": source,
    }
    return sanitize_resource_telemetry(payload).transport_dict()
