from __future__ import annotations

import json
from pathlib import Path

import pytest

from mary.training.adapter_candidate import build_mlx_adapter_candidate_proposal


def _ready_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "bundle"
    data = root / "mlx-data"
    adapter = root / "adapter"
    data.mkdir(parents=True)
    adapter.mkdir(parents=True)
    manifest = {
        "profile": {
            "profile_id": "m1-smoke",
            "model": "mlx-community/Qwen3-0.6B-4bit",
            "upstream_base": "Qwen/Qwen3-0.6B",
            "minimum_train_examples": 2,
            "experiment_class": "pipeline_smoke",
        },
        "dataset_fingerprint": "dataset-abc",
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "mlx_lora_config.yaml").write_text(
        'model: "mlx-community/Qwen3-0.6B-4bit"\n',
        encoding="utf-8",
    )
    (data / "train.jsonl").write_text(
        '{"messages":[]}\n{"messages":[]}\n',
        encoding="utf-8",
    )
    (adapter / "adapter_config.json").write_text(
        json.dumps({
            "model": "mlx-community/Qwen3-0.6B-4bit",
            "fine_tune_type": "lora",
        }),
        encoding="utf-8",
    )
    (adapter / "adapters.safetensors").write_bytes(b"adapter-fixture")
    return root


def test_candidate_proposal_hashes_exact_ready_adapter_without_promoting(tmp_path: Path):
    root = _ready_bundle(tmp_path)
    proposal = build_mlx_adapter_candidate_proposal(
        root,
        candidate_id="mary-smoke-v1",
        host_system="Darwin",
        host_machine="arm64",
        mlx_available=True,
        mlx_lm_available=True,
    )

    assert proposal.status == "review_required"
    assert proposal.candidate_id == "mary-smoke-v1"
    assert proposal.runtime == "mlx_lm"
    assert proposal.upstream_base == "Qwen/Qwen3-0.6B"
    assert len(proposal.adapter_weights_sha256) == 64
    assert proposal.adapter_weights_bytes > 0
    assert proposal.dataset_fingerprint == "dataset-abc"
    assert proposal.benchmark_required is True
    assert proposal.catalog_write_performed is False
    assert proposal.runtime_load_performed is False
    assert proposal.promotion_performed is False


def test_candidate_proposal_refuses_unready_adapter(tmp_path: Path):
    root = _ready_bundle(tmp_path)
    (root / "adapter" / "adapter_config.json").write_text(
        json.dumps({
            "model": "wrong-base",
            "fine_tune_type": "lora",
        }),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        build_mlx_adapter_candidate_proposal(
            root,
            host_system="Darwin",
            host_machine="arm64",
            mlx_available=True,
            mlx_lm_available=True,
        )
