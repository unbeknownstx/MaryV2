from __future__ import annotations

import json
from pathlib import Path

from mary.training.corpus_mining import MaryCorpusMiner


def test_corpus_miner_reports_source_balance_boundaries_and_eval_coverage(tmp_path: Path):
    active = tmp_path / "character_sources" / "active"
    active.mkdir(parents=True)
    rows = [
        {
            "heading": "BEHAVIOR-1",
            "labels": ["DNA"],
            "text": (
                "Situation: Unbe asks a direct question. "
                "Mary behavior: Answer directly without a generic closer. "
                "Avoid: support-agent phrasing."
            ),
        },
        {
            "heading": "NEG-1",
            "labels": ["NEG"],
            "text": "Do not answer like a generic customer support assistant.",
        },
        {
            "heading": "FC-1",
            "labels": ["DNA", "FC"],
            "text": (
                "Situation: A fictional scene happens. "
                "Mary behavior: Treat it as fictional calibration only."
            ),
        },
    ]
    source = active / "fixture.jsonl"
    source.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    eval_path = tmp_path / "character_sources" / "mary_evaluation.json"
    eval_path.write_text(
        json.dumps({
            "cases": [
                {"case_id": "direct-1", "prompt": "Be direct.", "category": "naturalism"},
                {"case_id": "boundary-1", "prompt": "Did that fictional event happen to you?", "category": "fiction_boundary"},
            ]
        }),
        encoding="utf-8",
    )

    report = MaryCorpusMiner().inspect(tmp_path)

    assert report.records == 3
    assert report.sources == 1
    assert report.structured_behavior_records == 1
    assert report.training_candidate_records == 1
    assert report.negative_records == 1
    assert report.fictional_reference_records == 1
    assert report.marybench_cases == 2
    assert report.marybench_categories == {
        "fiction_boundary": 1,
        "naturalism": 1,
    }
    assert report.to_dict()["training_performed"] is False
    assert report.to_dict()["automatic_mutation_performed"] is False
