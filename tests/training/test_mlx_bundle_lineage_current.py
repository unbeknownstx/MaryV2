from __future__ import annotations

import json
from pathlib import Path

from mary.training.bundle_lineage import build_mlx_bundle_lineage
from mary.training.mlx_preflight import inspect_mlx_bundle


def _write_bundle(root: Path, *, train_suffix: str = "") -> Path:
    data = root / "mlx-data"
    dataset = root / "mary-dataset-v1"
    data.mkdir(parents=True)
    dataset.mkdir(parents=True)

    (root / "manifest.json").write_text(
        json.dumps({
            "version": "mary-mlx-adapter-bundle-v2",
            "profile": {
                "profile_id": "m1-light",
                "model": "mlx-community/Qwen3-1.7B-4bit",
                "upstream_base": "Qwen/Qwen3-1.7B",
                "learning_rate": 1e-5,
                "minimum_train_examples": 1,
            },
            "dataset_fingerprint": "dataset-fixed-123",
        }),
        encoding="utf-8",
    )
    (root / "mlx_lora_config.yaml").write_text(
        'model: "mlx-community/Qwen3-1.7B-4bit"\ntrain: true\n',
        encoding="utf-8",
    )
    (dataset / "manifest.json").write_text(
        json.dumps({
            "version": "mary-dataset-v1",
            "fingerprint": "dataset-fixed-123",
            "sources": {
                "sourcebook": {"hash": "sourcebook-fixed"},
                "marybench": {"fingerprint": "marybench-fixed"},
                "reviewed_novel_behavior": {"sha256": "a" * 64},
                "explicit_feedback": {"source_records": 3},
            },
        }),
        encoding="utf-8",
    )
    (data / "train.jsonl").write_text(
        '{"messages":[{"role":"user","content":"u"},{"role":"assistant","content":"a'
        + train_suffix
        + '"}]}\n',
        encoding="utf-8",
    )
    (data / "valid.jsonl").write_text(
        '{"messages":[{"role":"user","content":"v"},{"role":"assistant","content":"b"}]}\n',
        encoding="utf-8",
    )
    (data / "test.jsonl").write_text(
        '{"messages":[{"role":"user","content":"t"},{"role":"assistant","content":"c"}]}\n',
        encoding="utf-8",
    )
    return root


def test_bundle_lineage_is_path_independent_and_content_free(tmp_path: Path):
    first = build_mlx_bundle_lineage(_write_bundle(tmp_path / "one"))
    second = build_mlx_bundle_lineage(_write_bundle(tmp_path / "two"))

    assert first.bundle_fingerprint == second.bundle_fingerprint
    assert len(first.bundle_fingerprint) == 64
    assert first.dataset_fingerprint == "dataset-fixed-123"
    assert first.novel_review_sha256 == "a" * 64
    assert first.feedback_records == 3
    assert first.missing_files == ()

    payload = first.to_dict()
    assert payload["content_included"] is False
    assert payload["training_performed"] is False
    assert payload["authority"] == "pretraining_lineage_only"


def test_bundle_lineage_changes_when_prepared_training_split_changes(tmp_path: Path):
    baseline = build_mlx_bundle_lineage(_write_bundle(tmp_path / "baseline"))
    changed = build_mlx_bundle_lineage(
        _write_bundle(tmp_path / "changed", train_suffix="-changed")
    )

    assert baseline.train_sha256 != changed.train_sha256
    assert baseline.bundle_fingerprint != changed.bundle_fingerprint
    assert baseline.profile_fingerprint == changed.profile_fingerprint


def test_preflight_detects_prepared_bundle_tampering(tmp_path: Path):
    root = _write_bundle(tmp_path / "verified")
    lineage = build_mlx_bundle_lineage(root)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["bundle_lineage"] = lineage.to_dict()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    clean = inspect_mlx_bundle(
        root,
        host_system="Darwin",
        host_machine="arm64",
        mlx_available=True,
        mlx_lm_available=True,
    )
    assert clean.bundle_lineage_fingerprint == lineage.bundle_fingerprint
    assert clean.bundle_lineage_matches is True
    assert clean.ready_for_training is True

    with (root / "mlx-data" / "train.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            '{"messages":[{"role":"user","content":"tampered"},'
            '{"role":"assistant","content":"row"}]}\n'
        )

    changed = inspect_mlx_bundle(
        root,
        host_system="Darwin",
        host_machine="arm64",
        mlx_available=True,
        mlx_lm_available=True,
    )
    assert changed.bundle_lineage_matches is False
    assert changed.ready_for_training is False
    assert any("reproducibility fingerprint" in item for item in changed.blockers)
