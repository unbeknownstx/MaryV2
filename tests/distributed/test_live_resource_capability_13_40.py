from __future__ import annotations

from types import SimpleNamespace

import mary.distributed.capabilities as capabilities
from mary.distributed.resource_probe import GPUObservation, LiveResourceObservation


class _Environment:
    def snapshot(self):
        return {"capabilities": {}, "providers": {}}


def test_resource_capability_advertises_live_free_vram_without_granting_authority(monkeypatch):
    profile = SimpleNamespace(
        llama_cpp_available=False,
        to_dict=lambda: {
            "platform": "linux",
            "machine": "x86_64",
            "cpu_count": 8,
            "memory_gib": 32.0,
            "apple_silicon": False,
            "ollama_available": True,
            "llama_cpp_available": False,
            "whisper_cpp_available": False,
        },
    )
    monkeypatch.setattr(capabilities.RuntimeResourceProfile, "detect", lambda: profile)

    import mary.distributed.resource_probe as resource_probe

    monkeypatch.setattr(
        resource_probe,
        "observe_live_resources",
        lambda: LiveResourceObservation(
            platform="linux",
            ram_total_gib=32.0,
            ram_free_gib=15.25,
            gpus=(
                GPUObservation(
                    label="Test GPU",
                    total_gib=12.0,
                    free_gib=7.5,
                    backend="cuda",
                    source="nvidia_smi",
                ),
            ),
        ),
    )

    items = capabilities.capabilities_from_environment(_Environment())
    resource = next(item for item in items if item.name == "runtime.resource_profile")
    metadata = resource.to_dict()["metadata"]

    assert resource.private is True
    assert metadata["memory_free_gib"] == 15.25
    assert metadata["gpu_memory_gib_live"] == 12.0
    assert metadata["gpu_memory_free_gib"] == 7.5
    assert metadata["gpu_resource_source"] == "nvidia_smi"
    assert "authorized" not in metadata
    assert "permission" not in metadata
