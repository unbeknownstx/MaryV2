from __future__ import annotations

from pathlib import Path

from mary.training import MaryCorpusMiner, MaryDatasetV1Auditor
from mary.training.mlx_bundle import prepare_mlx_bundle


def test_checked_in_mary_training_baseline_is_structurally_ready(tmp_path: Path, monkeypatch):
    """Exercise the real repo corpus/eval baseline without training or promotion."""

    monkeypatch.delenv("MARY_CHARACTER_SOURCES", raising=False)
    monkeypatch.delenv("MARY_CHARACTER_EVALS", raising=False)

    root = Path(__file__).resolve().parents[2]
    corpus = MaryCorpusMiner().inspect(root)

    assert corpus.records >= 197
    assert corpus.sources >= 8
    assert corpus.training_candidate_records >= 147
    assert corpus.structured_behavior_records >= 37
    assert corpus.negative_records >= 36
    assert corpus.marybench_cases >= 60
    assert corpus.duplicate_content_groups == 0

    bundle = tmp_path / "mary-mlx-light"
    manifest = prepare_mlx_bundle(
        root=root,
        output_dir=bundle,
        profile_id="m1-light",
    )

    dataset = manifest["mary_dataset"]
    audit = MaryDatasetV1Auditor().audit(
        bundle / "mary-dataset-v1",
        minimum_train_examples=12,
    )

    assert dataset["sourcebook_records"] >= 197
    assert dataset["behavior_sft"] >= 37
    assert dataset["marybench_eval"] >= 60
    assert manifest["dataset_fingerprint"] == dataset["fingerprint"]

    assert audit.training_ready is True
    assert audit.training_rows >= 37
    assert audit.marybench_prompt_leaks == 0
    assert audit.split_leakage_groups == 0
    assert audit.boundary_violations == 0

    assert manifest["training_readiness"]["dataset_ready"] is True
    assert manifest["training_readiness"]["ready_for_training"] is False
    assert manifest["training_readiness"]["manual_creator_gate_required"] is True
    assert manifest["boundaries"]["marybench_in_training_data"] is False
    assert manifest["boundaries"]["training_performed"] is False
