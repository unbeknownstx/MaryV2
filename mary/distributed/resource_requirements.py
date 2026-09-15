"""Explicit resource-footprint hints for local model capability nodes.

Mary never infers model memory requirements from model names, parameter counts,
or marketing labels. These hints exist only when the device operator supplies a
measured/configured value. They remain scheduling evidence, never permission.
"""
from __future__ import annotations

from dataclasses import replace
import math
import os
from typing import Iterable

from .capabilities import CapabilityDescriptor
from .resource_hint_provenance import role_hint_is_current


VERSION = "13.58"
_ROLES = ("general", "conversation", "fast", "utility")
_PREFIXES = {
    "llm.ollama": "MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB",
    "llm.llama_cpp": "MARY_LLAMA_CPP_RESOURCE_ACCELERATOR_GIB",
}


def _gib(value: str | None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0.0 or number > 4096.0:
        return None
    return round(number, 3)


def explicit_resource_hints(capability: str) -> dict[str, float]:
    """Return only current fixed per-role accelerator-memory hints.

    Legacy explicit hints without provenance remain compatible. When 13.58
    provenance is supplied, a model/context mismatch suppresses that role until
    the operator remeasures and explicitly reapplies the recommendation.
    """
    normalized = str(capability or "").strip().lower()
    prefix = _PREFIXES.get(normalized)
    if prefix is None:
        return {}
    common = _gib(os.getenv(prefix))
    output: dict[str, float] = {}
    for role in _ROLES:
        specific = _gib(os.getenv(f"{prefix}_{role.upper()}"))
        value = specific if specific is not None else common
        if value is not None and role_hint_is_current(normalized, role):
            output[f"resource_accelerator_gib_{role}"] = value
    return output


def apply_explicit_resource_requirements(
    capabilities: Iterable[CapabilityDescriptor],
) -> list[CapabilityDescriptor]:
    """Project explicit device-local fit hints into existing capability metadata."""
    output: list[CapabilityDescriptor] = []
    for capability in capabilities:
        hints = explicit_resource_hints(capability.name)
        if not hints:
            output.append(capability)
            continue
        metadata = dict(capability.metadata or {})
        # Capability metadata has a 16-field transport limit. Refuse to crowd out
        # existing evidence rather than silently depending on truncation order.
        available_slots = max(0, 16 - len(metadata))
        if available_slots <= 0:
            output.append(capability)
            continue
        for key in (
            "resource_accelerator_gib_general",
            "resource_accelerator_gib_conversation",
            "resource_accelerator_gib_fast",
            "resource_accelerator_gib_utility",
        ):
            if key in hints and key not in metadata and available_slots > 0:
                metadata[key] = hints[key]
                available_slots -= 1
        output.append(replace(capability, metadata=metadata))
    return output
