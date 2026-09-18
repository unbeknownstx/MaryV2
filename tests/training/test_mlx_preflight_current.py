from __future__ import annotations

import json
from pathlib import Path

from mary.training.mlx_preflight import inspect_mlx_bundle


def _bundle(tmp_path: Path) -> Path:
    root = tmp_path / "bundle"
    data = root / "mlx-data"
    adapter = root / "adapter"
    data.mkdir(parents=True)
    adapter.mkdir(parents=True)
    manifest = {
        "version": "mary-mlx-adapter-bundle-v2",
        "profile": {
            "profile_id": "m1-smoke",
            "model": "mlx-community/Qwen3-0.6B-4bit",
            "upstream_base": "Qwen/Qwen3-0.6B",
            "minimum_train_examples": 6,
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "mlx_lora_config.yaml").write_text(
        'model: "mlx-community/Qwen3-0.6B-4bit"\ntrain: true\n',
        encoding="utf-8",
    )
    rows = [
        {"messages": [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}]}
        for i in range(6)
    ]
    (data / "train.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    return root


def test_mlx_preflight_requires_apple_silicon_packages_dataset_and_lineage(tmp_path: Path):
    root = _bundle(tmp_path)
    report = inspect_mlx_bundle(
        root,
        host_system="Darwin",
        host_machine="arm64",
        mlx_available=True,
        mlx_lm_available=True,
    )

    assert report.ready_for_training is True
    assert report.ready_for_evaluation is False
    assert report.dataset_ready is True
    assert report.config_lineage_matches is True
    assert report.adapter_present is False
    assert report.blockers == ()


def test_mlx_preflight_rejects_wrong_host_and_adapter_lineage(tmp_path: Path):
    root = _bundle(tmp_path)
    adapter = root / "adapter"
    (adapter / "adapter_config.json").write_text(
        json.dumps({
            "model": "some-other-base",
            "fine_tune_type": "lora",
        }),
        encoding="utf-8",
    )
    (adapter / "adapters.safetensors").write_bytes(b"fixture")

    report = inspect_mlx_bundle(
        root,
        host_system="Linux",
        host_machine="x86_64",
        mlx_available=True,
        mlx_lm_available=True,
    )

    assert report.ready_for_training is False
    assert report.ready_for_evaluation is False
    assert report.adapter_present is True
    assert report.adapter_lineage_matches is False
    assert any("Apple Silicon" in item for item in report.blockers)
    assert any("exact" in item.lower() for item in report.warnings)


def test_mlx_preflight_marks_exact_adapter_ready_for_evaluation(tmp_path: Path):
    root = _bundle(tmp_path)
    adapter = root / "adapter"
    (adapter / "adapter_config.json").write_text(
        json.dumps({
            "model": "mlx-community/Qwen3-0.6B-4bit",
            "fine_tune_type": "lora",
        }),
        encoding="utf-8",
    )
    (adapter / "adapters.safetensors").write_bytes(b"fixture")

    report = inspect_mlx_bundle(
        root,
        host_system="Darwin",
        host_machine="arm64",
        mlx_available=True,
        mlx_lm_available=True,
    )

    assert report.ready_for_training is True
    assert report.ready_for_evaluation is True
    assert report.adapter_lineage_matches is True
