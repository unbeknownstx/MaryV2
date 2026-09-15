from types import SimpleNamespace

import pytest

from mary.distributed.compute_fabric import NodeLoad
from mary.distributed.resource_telemetry import (
    merge_resource_load,
    sanitize_resource_telemetry,
    telemetry_from_observation,
)


def test_resource_report_is_strict_and_computes_pressure():
    report = sanitize_resource_telemetry({
        "ram_total_gib": 32,
        "ram_free_gib": 8,
        "vram_total_gib": 24,
        "vram_free_gib": 6,
        "apple_unified_memory": False,
        "source": "nvidia_smi",
    })
    assert report.memory_fraction == 0.75
    assert report.accelerator_fraction == 0.75
    assert report.to_dict()["authority"] == "operational_measurement_only"


def test_unknown_resource_fields_are_rejected():
    with pytest.raises(ValueError, match="Unsupported resource telemetry fields"):
        sanitize_resource_telemetry({
            "ram_total_gib": 32,
            "process_list": ["secret"],
        })


def test_free_memory_cannot_exceed_total():
    with pytest.raises(ValueError, match="ram_free_gib"):
        sanitize_resource_telemetry({
            "ram_total_gib": 8,
            "ram_free_gib": 16,
        })
    with pytest.raises(ValueError, match="vram_free_gib"):
        sanitize_resource_telemetry({
            "vram_total_gib": 4,
            "vram_free_gib": 8,
        })


def test_non_finite_and_boolean_measurements_are_rejected():
    with pytest.raises(ValueError):
        sanitize_resource_telemetry({"ram_total_gib": float("inf")})
    with pytest.raises(ValueError):
        sanitize_resource_telemetry({"ram_total_gib": True})


def test_apple_unified_memory_uses_system_pressure_without_fake_vram():
    report = sanitize_resource_telemetry({
        "ram_total_gib": 16,
        "ram_free_gib": 4,
        "vram_total_gib": None,
        "vram_free_gib": None,
        "apple_unified_memory": True,
        "source": "apple_unified_memory",
    })
    assert report.memory_fraction == 0.75
    assert report.accelerator_fraction == 0.75


def test_resource_pressure_merges_with_existing_task_pressure():
    base = NodeLoad(
        node_id="node-a",
        active_realtime=1,
        active_background=2,
        stream_critical=True,
    )
    report = sanitize_resource_telemetry({
        "ram_total_gib": 32,
        "ram_free_gib": 16,
        "vram_total_gib": 8,
        "vram_free_gib": 1,
        "source": "nvidia_smi",
    })
    merged = merge_resource_load(base, report)
    assert merged.active_realtime == 1
    assert merged.active_background == 2
    assert merged.memory_fraction == 0.5
    assert merged.accelerator_fraction == 0.875
    assert merged.pressure == 0.875


def test_live_resource_observation_projects_only_allowlisted_fields():
    gpu = SimpleNamespace(total_gib=12.0, free_gib=3.0, source="rocm_smi")
    observation = SimpleNamespace(
        ram_total_gib=32.0,
        ram_free_gib=20.0,
        primary_gpu=gpu,
        apple_unified_memory=False,
        probe_failures=("private detail",),
        platform="linux",
    )
    payload = telemetry_from_observation(observation)
    assert payload["ram_total_gib"] == 32.0
    assert payload["vram_total_gib"] == 12.0
    assert "probe_failures" not in payload
    assert "platform" not in payload
    assert "private detail" not in str(payload)
