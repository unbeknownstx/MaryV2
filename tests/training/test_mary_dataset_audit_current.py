from __future__ import annotations

import json
from pathlib import Path

from mary.training.dataset_audit import MaryDatasetV1Auditor


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _dataset(tmp_path: Path) -> Path:
    root = tmp_path / "dataset"
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps({"fingerprint": "dataset-fp"}),
        encoding="utf-8",
    )
    _write_jsonl(root / "mary_character_training_candidates.jsonl", [])
    _write_jsonl(root / "mary_negative_examples.jsonl", [])
    _write_jsonl(root / "mary_character_corpus.jsonl", [])
    _write_jsonl(root / "mary_character_eval.jsonl", [])
    _write_jsonl(root / "explicit_feedback" / "mary_sft.jsonl", [])
    return root


def _row(example_id: str, prompt: str, answer: str, split: str):
    return {
        "example_id": example_id,
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ],
        "split": split,
        "source_name": "creator-source",
        "training_eligible": True,
        "labels": ["DNA"],
    }


def test_dataset_audit_accepts_clean_minimum_bundle(tmp_path: Path):
    root = _dataset(tmp_path)
    rows = [
        _row(f"e-{i}", f"prompt {i}", f"answer {i}", "train" if i < 8 else "validation")
        for i in range(9)
    ]
    _write_jsonl(root / "mary_behavior_sft.jsonl", rows)

    report = MaryDatasetV1Auditor().audit(root)

    assert report.training_ready is True
    assert report.training_rows == 9
    assert report.split_leakage_groups == 0
    assert report.marybench_prompt_leaks == 0
    assert report.boundary_violations == 0
    assert report.to_dict()["promotion_performed"] is False


def test_dataset_audit_blocks_split_leakage_eval_leak_and_boundary_violation(tmp_path: Path):
    root = _dataset(tmp_path)
    repeated = _row("e-1", "same prompt", "same answer", "train")
    leak = _row("e-2", "same prompt", "same answer", "validation")
    unsafe = _row("e-3", "fiction prompt", "fiction answer", "train")
    unsafe["labels"] = ["FC"]
    unsafe["boundary"] = "fictional_reference_not_lived_memory"

    rows = [repeated, leak, unsafe] + [
        _row(f"e-{i}", f"prompt {i}", f"answer {i}", "train")
        for i in range(4, 11)
    ]
    _write_jsonl(root / "mary_behavior_sft.jsonl", rows)
    _write_jsonl(
        root / "mary_character_eval.jsonl",
        [{"case_id": "held-out", "prompt": "same prompt"}],
    )

    report = MaryDatasetV1Auditor().audit(root)

    assert report.training_ready is False
    assert report.split_leakage_groups == 1
    assert report.marybench_prompt_leaks == 1
    assert report.boundary_violations >= 1
    assert any("held-out MaryBench" in item for item in report.blocking_issues)
