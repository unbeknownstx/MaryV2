from __future__ import annotations

import json
from pathlib import Path

from mary.training.bundle_lineage import build_mlx_bundle_lineage


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
            },
            "dataset_fingerprint": "dataset-fixed-123",
        }),
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
