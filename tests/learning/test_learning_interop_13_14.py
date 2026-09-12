from __future__ import annotations

import json

from mary.character import MaryEvalCase, MaryEvaluationSet
from mary.learning.interop import (
    dspy_examples,
    phoenix_rows,
    promptfoo_tests,
    proposal,
    records_from_evaluation_set,
    write_bundle,
)


def _suite() -> MaryEvaluationSet:
    return MaryEvaluationSet([
        MaryEvalCase(
            case_id="voice-1",
            prompt="Hey Mary, what do you think?",
            category="voice",
            forbidden_phrases=("How can I assist you today?",),
            expected_labels=("DNA",),
        )
    ])


def test_marybench_exports_are_dependency_free_and_bounded(tmp_path) -> None:
    rows = records_from_evaluation_set(_suite())
    assert len(rows) == 1
    assert dspy_examples(rows)[0]["input"]["prompt"].startswith("Hey Mary")
    assert promptfoo_tests(rows)[0]["assert"][0]["type"] == "not-contains"
    assert phoenix_rows(rows)[0]["metadata"]["case_id"] == "voice-1"
    target = tmp_path / "marybench.json"
    summary = write_bundle(target, rows)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert summary["records"] == 1
    assert payload["semantics"]["automatic_training"] is False
    assert payload["semantics"]["automatic_prompt_mutation"] is False


def test_optimizer_output_is_only_a_proposal() -> None:
    item = proposal(
        "dspy_gepa",
        "character_runtime",
        {"instruction": "candidate instruction"},
        {"marybench_score": 0.97},
    )
    assert item.status == "proposal_only"
    assert item.proposal_id.startswith("mary_opt_")
