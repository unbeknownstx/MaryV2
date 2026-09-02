import json

from mary.learning.adapter_runner import AdapterExperimentRunner, AdapterMix, EvalCase, ExperimentConfiguration
from mary.llm.interface import LLMResponse


class _Provider:
    def generate_with_lora(self, messages, *, lora, temperature, max_tokens, model, timeout_seconds=None):
        suffix = "adapter" if lora else "base"
        return LLMResponse(content=f"response-{suffix}", provider="llama_cpp", model=model, usage={"total_tokens": 4})


def test_adapter_runner_creates_blind_creator_review_without_canonical_writes(tmp_path):
    runner = AdapterExperimentRunner(_Provider(), output_root=tmp_path)
    cases = [EvalCase(case_id="E1", prompt="Hey Mary", relationship="close_friend")]
    configs = [
        ExperimentConfiguration(config_id="base", label="Base", base_model="qwen"),
        ExperimentConfiguration(config_id="rp", label="Roleplay", base_model="qwen", adapters=(AdapterMix(0, .5),)),
    ]
    summary = runner.run(cases, configs, seed=7)
    run_dir = tmp_path / summary.run_id
    assert summary.generations == 2
    assert (run_dir / "blind_review.json").exists()
    review = json.loads((run_dir / "blind_review.json").read_text())
    assert {option["response"] for option in review[0]["options"]} == {"response-base", "response-adapter"}
    assert all("config_id" not in option for option in review[0]["options"])
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert "canonical Mary state" in manifest["policy"]


def test_adapter_runner_includes_creator_sourcebook_without_treating_fiction_as_lived_memory(tmp_path):
    from mary.character.sourcebook import CharacterSourceRecord, CharacterSourcebook
    sourcebook = CharacterSourcebook((CharacterSourceRecord(
        record_id="r1", text="[DNA] Mary answers teasing with dry warmth rather than defensiveness.",
        source_path="test", source_name="test.md", source_kind="character_corpus", labels=("DNA",), content_hash="x"
    ),))
    runner = AdapterExperimentRunner(_Provider(), output_root=tmp_path, sourcebook=sourcebook)
    case = EvalCase(case_id="E2", prompt="I am teasing you, Mary. You're weird.", relationship="close_friend")
    config = ExperimentConfiguration(config_id="base", label="Base", base_model="qwen")
    messages = runner._messages(case, config)
    assert "dry warmth" in messages[0].content
    assert "fictional canon is reference rather than AI-lived memory" in messages[0].content


def test_adapter_runner_writes_explicit_automatic_regression_review(tmp_path):
    runner = AdapterExperimentRunner(_Provider(), output_root=tmp_path)
    cases = [
        EvalCase(
            case_id="E3",
            prompt="Respond naturally.",
            must_have=("natural response",),
            should_have=("relationship-appropriate familiarity",),
            fail_if=("customer-service style",),
            literal_must_have=("response",),
            literal_should_have=("base",),
            literal_fail_if=("generic customer service",),
        )
    ]
    configs = [ExperimentConfiguration(config_id="base", label="Base", base_model="qwen")]
    summary = runner.run(cases, configs, seed=11)
    payload = json.loads((tmp_path / summary.run_id / "automatic_review.json").read_text())
    assert payload["leaderboard"][0]["config_id"] == "base"
    assert payload["leaderboard"][0]["hard_failures"] == 0
    assert payload["scores"][0]["must_coverage"] == 1.0
    assert payload["scores"][0]["should_coverage"] == 1.0
    assert "Mary likeness requires blinded creator review" in payload["policy"]


def test_blind_creator_review_summary_stays_experiment_only(tmp_path):
    runner = AdapterExperimentRunner(_Provider(), output_root=tmp_path)
    cases = [EvalCase(case_id="E4", prompt="Hey Mary", score_dimensions=("mary_fit", "naturalism"))]
    configs = [
        ExperimentConfiguration(config_id="base", label="Base", base_model="qwen"),
        ExperimentConfiguration(config_id="rp", label="Roleplay", base_model="qwen", adapters=(AdapterMix(0, .5),)),
    ]
    summary = runner.run(cases, configs, seed=13)
    run_dir = tmp_path / summary.run_id
    review = json.loads((run_dir / "blind_review.json").read_text())
    review[0]["options"][0]["scores"] = {"mary_fit": .9, "naturalism": .8}
    review[0]["options"][0]["preferred"] = True
    review[0]["options"][1]["scores"] = {"mary_fit": .4, "naturalism": .5}
    (run_dir / "blind_review.json").write_text(json.dumps(review, indent=2), encoding="utf-8")

    payload = AdapterExperimentRunner.summarize_blind_review(run_dir)
    assert payload["scored_options"] == 2
    assert payload["leaderboard"][0]["preferred_count"] == 1
    assert payload["leaderboard"][0]["creator_score"] == .85
    assert "no automatic character/canon/memory promotion" in payload["policy"]
    assert (run_dir / "creator_review_summary.json").exists()
