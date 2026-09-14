"""Cold-load resource calibration for local Mary model workers.

Calibration is explicit benchmark tooling, not runtime routing. It observes a
synthetic benchmark from a known provider, proves model residency when the
runtime supports it, and may produce a conservative *suggested* general-role
accelerator requirement. It never mutates environment variables or Mary state.
"""
from __future__ import annotations

import json
import math
from typing import Any, Callable
import urllib.request

from .resource_probe import LiveResourceObservation, observe_live_resources


REVISION = "13.56"


def _normal_model(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.endswith(":latest"):
        text = text[:-7]
    return text


def ollama_residency(
    provider: Any,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> str:
    """Return loaded/not_loaded/unknown for the provider's exact Ollama model."""
    try:
        provider_name = str(provider.provider_name()).strip().lower()
    except Exception:
        provider_name = ""
    base_url = str(getattr(provider, "base_url", "") or "").rstrip("/")
    try:
        model = _normal_model(provider.model_name())
    except Exception:
        model = _normal_model(getattr(provider, "model", ""))
    if provider_name != "ollama" or not base_url or not model:
        return "unknown"

    request = urllib.request.Request(
        f"{base_url}/api/ps",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with opener(request, timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return "unknown"
    rows = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return "unknown"
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        for key in ("name", "model"):
            candidate = _normal_model(raw.get(key))
            if candidate and candidate == model:
                return "loaded"
    return "not_loaded"


def _accelerator_view(observation: LiveResourceObservation) -> tuple[float | None, float | None, str]:
    if observation.apple_unified_memory:
        return observation.ram_total_gib, observation.ram_free_gib, "apple_unified_memory"
    primary = observation.primary_gpu
    if primary is None:
        return None, None, "unknown"
    return primary.total_gib, primary.free_gib, str(primary.source or "unknown")[:64]


def _delta(before_free: float | None, after_free: float | None) -> float | None:
    if before_free is None or after_free is None:
        return None
    return round(max(0.0, float(before_free) - float(after_free)), 3)


def _suggest_requirement(delta_gib: float) -> float:
    """Add transparent safety headroom and round upward to 0.25 GiB."""
    measured = max(0.0, float(delta_gib))
    headroom = max(0.5, measured * 0.10)
    return round(math.ceil((measured + headroom) * 4.0) / 4.0, 2)


def measure_provider_fit(
    provider: Any,
    operation: Callable[[], Any],
    *,
    observer: Callable[[], LiveResourceObservation] = observe_live_resources,
    residency_probe: Callable[[Any], str] = ollama_residency,
) -> tuple[Any, dict[str, Any]]:
    """Run one synthetic benchmark operation and return result + safe measurements.

    A fit suggestion requires a proven not-loaded -> loaded transition plus a
    measurable accelerator-memory delta. Otherwise measurements are retained for
    diagnostics but recommendation fields remain null.
    """
    try:
        model = str(provider.model_name() or "")[:160]
    except Exception:
        model = str(getattr(provider, "model", "") or "")[:160]
    try:
        num_ctx = max(0, int(getattr(provider, "num_ctx", 0) or 0))
    except (TypeError, ValueError):
        num_ctx = 0

    before_residency = residency_probe(provider)
    try:
        before = observer()
    except Exception:
        before = None

    result = operation()

    try:
        after = observer()
    except Exception:
        after = None
    after_residency = residency_probe(provider)

    ram_delta = None
    accelerator_delta = None
    accelerator_total = None
    accelerator_free_after = None
    accelerator_source = "unknown"
    unified = False
    if before is not None and after is not None:
        ram_delta = _delta(before.ram_free_gib, after.ram_free_gib)
        before_total, before_free, before_source = _accelerator_view(before)
        after_total, after_free, after_source = _accelerator_view(after)
        if before_total is not None and after_total is not None and abs(before_total - after_total) <= 0.125:
            accelerator_total = after_total
            accelerator_free_after = after_free
            accelerator_delta = _delta(before_free, after_free)
            accelerator_source = after_source if after_source != "unknown" else before_source
        unified = bool(after.apple_unified_memory)

    proven_cold_load = before_residency == "not_loaded" and after_residency == "loaded"
    measurable = accelerator_delta is not None and accelerator_delta >= 0.125
    safe_to_suggest = bool(proven_cold_load and measurable)
    suggested = _suggest_requirement(accelerator_delta) if safe_to_suggest and accelerator_delta is not None else None

    if safe_to_suggest:
        status = "cold_load_measured"
    elif before_residency == "loaded":
        status = "model_already_resident"
    elif before_residency == "unknown" or after_residency == "unknown":
        status = "residency_unverified"
    elif accelerator_delta is None:
        status = "accelerator_measurement_unavailable"
    elif accelerator_delta < 0.125:
        status = "cold_load_delta_too_small"
    else:
        status = "fit_suggestion_unavailable"

    measurement = {
        "revision": REVISION,
        "model": model,
        "num_ctx": num_ctx,
        "role": "general",
        "residency_before": before_residency,
        "residency_after": after_residency,
        "ram_observed_delta_gib": ram_delta,
        "accelerator_observed_delta_gib": accelerator_delta,
        "accelerator_total_gib": accelerator_total,
        "accelerator_free_after_gib": accelerator_free_after,
        "accelerator_source": accelerator_source,
        "apple_unified_memory": unified,
        "fit_hint_status": status,
        "suggested_accelerator_gib_general": suggested,
        "suggestion_safe_to_apply": safe_to_suggest,
        "suggestion_policy": "cold-load observed delta + max(0.5 GiB, 10%) headroom; rounded upward to 0.25 GiB",
        "authority": "operational_measurement_only",
        "content_retained": False,
    }
    return result, measurement
