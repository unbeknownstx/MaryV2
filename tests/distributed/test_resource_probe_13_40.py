from __future__ import annotations

from types import SimpleNamespace

import mary.distributed.resource_probe as probe


def _runner(stdout: str, returncode: int = 0):
    def run(argv, **kwargs):
        assert kwargs["timeout"] <= 2.0
        assert "shell" not in kwargs or kwargs["shell"] is False
        return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)
    return run


def test_nvidia_probe_parses_total_and_free_without_shell(monkeypatch):
    monkeypatch.setattr(probe.shutil, "which", lambda name: "/bin/nvidia-smi" if name == "nvidia-smi" else None)
    observed = probe._probe_nvidia(
        runner=_runner("NVIDIA RTX 3090, 24576, 20000\n")
    )
    assert len(observed) == 1
    assert observed[0].backend == "cuda"
    assert observed[0].total_gib == 24.0
    assert observed[0].free_gib == round(20000 / 1024, 3)


def test_live_probe_soft_fails_and_falls_back_to_environment(monkeypatch):
    monkeypatch.setattr(probe, "_system_memory", lambda: (32.0, 11.5))
    monkeypatch.setattr(probe.platform, "system", lambda: "Linux")
    monkeypatch.setattr(probe.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(probe, "_probe_nvidia", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("nope")))
    monkeypatch.setattr(probe, "_probe_rocm", lambda **kwargs: ())
    monkeypatch.setattr(probe, "_probe_windows_adapter_hint", lambda **kwargs: ())
    monkeypatch.setenv("MARY_NODE_GPU_LABEL", "RX 580")
    monkeypatch.setenv("MARY_NODE_GPU_MEMORY_GIB", "4")

    observed = probe.observe_live_resources()
    assert observed.ram_total_gib == 32.0
    assert observed.gpus[0].source == "environment_hint"
    assert observed.gpus[0].total_gib == 4.0
    assert "nvidia" in observed.probe_failures


def test_apple_unified_memory_is_not_reported_as_dedicated_vram(monkeypatch):
    monkeypatch.setattr(probe, "_system_memory", lambda: (16.0, 8.0))
    monkeypatch.setattr(probe.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(probe.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(probe, "_probe_nvidia", lambda **kwargs: ())
    monkeypatch.setattr(probe, "_probe_rocm", lambda **kwargs: ())
    monkeypatch.setattr(probe, "_probe_windows_adapter_hint", lambda **kwargs: ())
    monkeypatch.setenv("MARY_NODE_GPU_MEMORY_GIB", "16")

    observed = probe.observe_live_resources()
    assert observed.apple_unified_memory is True
    assert observed.ram_total_gib == 16.0
    assert observed.gpus[0].total_gib is None


def test_resource_snapshot_feeds_measured_facts_to_broker(monkeypatch):
    monkeypatch.setattr(
        probe,
        "observe_live_resources",
        lambda **kwargs: probe.LiveResourceObservation(
            platform="linux",
            ram_total_gib=32.0,
            ram_free_gib=20.0,
            gpus=(
                probe.GPUObservation(
                    label="GPU",
                    total_gib=12.0,
                    free_gib=8.0,
                    backend="cuda",
                    source="nvidia_smi",
                ),
            ),
        ),
    )
    snapshot = probe.resource_snapshot("node-a", loaded_models=("qwen",))
    assert snapshot.node_id == "node-a"
    assert snapshot.vram_total_gb == 12.0
    assert snapshot.vram_free_gb == 8.0
    assert snapshot.loaded_models == ("qwen",)
