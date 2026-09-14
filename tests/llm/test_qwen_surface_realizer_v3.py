from __future__ import annotations

import json
import os
from pathlib import Path
import re

import pytest

from mary.core.config import Config
from mary.llm.providers.ollama import OllamaProvider
from mary.llm.router import LLMRouter
from scripts.benchmark_qwen_micro_cortex import (
    SURFACE_V3_DEFAULT_MODELS,
    SURFACE_V3_PROFILE,
    report_completion_errors,
    render_messages,
    run_benchmark,
    write_report,
)
from scripts.qwen_surface_realizer_v3 import (
    assess_surface_response,
    fixed_surface_v3_cases,
    render_surface_messages,
    summarize_surface_samples,
    verify_surface_response,
)
from tests.llm.test_qwen_micro_cortex import FakeOllamaClient


VALID_RESPONSES = {
    "casual-greeting": "Hey. What's up?",
    "known-preference-opinion": (
        "I prefer ordinary conversation to sound natural and restrained, not theatrical."
    ),
    "shared-work-recall": (
        "We've been working together on MaryV2 12.12.2 natural-conversation calibration."
    ),
    "playful-reaction": "Of course one missing comma caused the bug. Finally.",
    "disagreement": (
        "I disagree: normal replies shouldn't be dramatic; they should stay natural and restrained."
    ),
    "uncertainty-unknown": "No final local production model has been chosen.",
    "reservoir-factual-answer": (
        "The Cognitive Reservoir is derived, rebuildable cache state; canonical identity, memory, "
        "relationship, personality, and developed self remain authoritative."
    ),
    "follow-up-question": "Was the slowness during loading or response generation?",
    "soft-concerned-response": "You sound exhausted. Please take a break and rest.",
    "ordinary-back-and-forth": (
        "Yeah, the compact plan is cleaner: local systems keep the decisions, and the model "
        "handles wording only."
    ),
    "adversarial-third-person-reference": "We fixed the retry timing bug together.",
    "adversarial-question-form": (
        "Was the delay before first content or after response generation began?"
    ),
    "adversarial-disagreement": (
        "I disagree that higher token output is always better; short replies should stop when "
        "their decided meaning is complete."
    ),
    "adversarial-uncertainty": (
        "I don't know whether the installed tag supports thinking disabled."
    ),
    "adversarial-warm-fact-bounded": "That headache sounds rough. Take a pause.",
    "adversarial-exact-factual-recall": (
        "Temperature is 0.2, context size is 1024 tokens, and output ceiling is 48 tokens."
    ),
    "adversarial-refusal-to-embellish": (
        "The process exited with code 2; the cause is unknown."
    ),
    "adversarial-pronoun-reference": "I sent you the draft after you asked for it.",
}


def _case(case_id: str):
    return next(
        case for case in fixed_surface_v3_cases()
        if case.plan.plan_id == case_id
    )


def _verify(case_id: str, response: str, **overrides):
    arguments = {
        "done": True,
        "done_reason": "stop",
        "tokens_generated": 16,
        **overrides,
    }
    return verify_surface_response(_case(case_id), response, **arguments)


class SurfaceFakeOllamaClient(FakeOllamaClient):
    def chat(self, *, model, messages, options):
        self.residents[model] = options.num_ctx
        self.chat_calls.append((model, messages, options))
        if self.forced_response is not None:
            response = self.forced_response
        elif "a minimal morning greeting" in messages[-1]["content"]:
            response = "Morning."
        else:
            response = next(
                VALID_RESPONSES[case.plan.plan_id]
                for case in fixed_surface_v3_cases()
                if render_surface_messages(case) == messages
            )
        return {
            "message": {"content": response, "thinking": self.thinking},
            "done": True,
            "done_reason": "stop",
            "total_duration": 120_000_000,
            "load_duration": 20_000_000,
            "prompt_eval_duration": 30_000_000,
            "eval_duration": 60_000_000,
            "prompt_eval_count": 96,
            "eval_count": 12,
            "_client_wall_ms": 125.0,
            "_http_headers_ms": 5.0,
            "_first_chunk_ms": 35.0,
            "_first_content_ms": 45.0,
            "_http_body_ms": 120.0,
            "_ndjson_chunks": 4,
            "_transport": "ollama_ndjson_stream",
        }


def test_v3_manifest_has_core_ten_plus_all_adversarial_categories():
    cases = fixed_surface_v3_cases()
    assert len(cases) == 18
    assert len({case.plan.plan_id for case in cases}) == 18
    assert {case.surface_contract.source_plan_id for case in cases} == {
        case.plan.plan_id for case in cases
    }
    assert set(VALID_RESPONSES) == {case.plan.plan_id for case in cases}
    assert {
        "adversarial-third-person-reference",
        "adversarial-question-form",
        "adversarial-disagreement",
        "adversarial-uncertainty",
        "adversarial-warm-fact-bounded",
        "adversarial-exact-factual-recall",
        "adversarial-refusal-to-embellish",
        "adversarial-pronoun-reference",
    } <= set(VALID_RESPONSES)


def test_v3_model_payload_and_prompt_are_minimal_and_identity_free():
    allowed_keys = {
        "speaker",
        "mode",
        "form",
        "max_sentences",
        "max_words",
        "required",
        "limit",
        "exact_questions",
    }
    forbidden_fragments = (
        "creator",
        " user",
        "assistant",
        "input_text",
        "dialogue_act",
        "conversational_drive",
        "response_intent",
        "grounded_fact",
        "relationship_hint",
        "authority",
        "confidence",
        "provenance",
        "source_id",
        "energy=",
        "warmth=",
        "requirement_labels",
        "contradiction_patterns",
        "human_review_focus",
    )

    for case in fixed_surface_v3_cases():
        payload = case.surface_contract.to_model_payload()
        assert set(payload) <= allowed_keys
        assert set(payload) >= allowed_keys - {"exact_questions"}
        messages = render_messages(case, profile=SURFACE_V3_PROFILE)
        assert messages == render_surface_messages(case)
        assert tuple(item["role"] for item in messages) == ("system", "user")
        rendered = "\n".join(item["content"] for item in messages)
        lowered = rendered.lower()
        assert not re.search(r"\bmary\b", rendered, flags=re.I)
        assert case.plan.input_text not in rendered
        assert len(rendered) < 700
        for fragment in forbidden_fragments:
            assert fragment not in lowered
        for unit in case.surface_contract.required_units:
            assert unit in rendered
        for semantic in case.semantic_units:
            for pattern in semantic.patterns:
                if re.search(r"[\\\[\](){}?+*|]", pattern):
                    assert pattern not in rendered


@pytest.mark.parametrize("case_id", tuple(VALID_RESPONSES))
def test_all_eighteen_reference_outputs_pass_strict_verification(case_id: str):
    verification = _verify(case_id, VALID_RESPONSES[case_id])

    assert verification["semantic_coverage_passed"] is True
    assert verification["strict_semantic_fidelity_passed"] is True
    assert verification["form_fidelity_passed"] is True
    assert verification["third_person_planner_leakage_detected"] is False
    assert verification["unsupported_personal_claim_detected"] is False
    assert verification["unsupported_addition_detected"] is False
    assert verification["verifier_accepted"] is True


@pytest.mark.parametrize(
    ("case_id", "response", "expected_axis"),
    (
        (
            "follow-up-question",
            "Was the slowness during loading?",
            "semantic_coverage_passed",
        ),
        (
            "known-preference-opinion",
            "Natural restrained conversation is not theatrical.",
            "stance_fidelity_passed",
        ),
        (
            "known-preference-opinion",
            "Maybe I prefer ordinary natural restrained conversation, not theatrical delivery.",
            "stance_fidelity_passed",
        ),
        (
            "disagreement",
            "I disagree: normal replies should stay natural and restrained, not dramatic?",
            "form_fidelity_passed",
        ),
        (
            "follow-up-question",
            "Loading and response generation were both slow.",
            "form_fidelity_passed",
        ),
        (
            "reservoir-factual-answer",
            "Reservoir, derived, cache, rebuildable; identity memory relationship personality developed self authoritative.",
            "semantic_coverage_passed",
        ),
    ),
)
def test_missing_relations_stance_softening_and_form_drift_fail(
    case_id: str,
    response: str,
    expected_axis: str,
):
    verification = _verify(case_id, response)
    assert verification[expected_axis] is False
    assert verification["verifier_accepted"] is False


@pytest.mark.parametrize(
    ("case_id", "response", "marker"),
    (
        (
            "shared-work-recall",
            "Mary and the creator have been working on MaryV2 12.12.2 natural-conversation calibration.",
            "third_person_planner_leakage_detected",
        ),
        (
            "follow-up-question",
            "The user reports loading or response generation.",
            "third_person_planner_leakage_detected",
        ),
        (
            "casual-greeting",
            "Hey. How can I assist?",
            "assistant_like_language_detected",
        ),
        (
            "casual-greeting",
            "Hey, Zurich is here. What's up?",
            "unsupported_addition_detected",
        ),
        (
            "adversarial-exact-factual-recall",
            "Temperature is 0.2, context size is 1024 tokens, output ceiling is 48 tokens, and latency is 999 ms.",
            "unsupported_addition_detected",
        ),
        (
            "known-preference-opinion",
            "I prefer natural restrained conversation, not theatrical delivery, because it feels authentic.",
            "unsupported_causal_addition_detected",
        ),
        (
            "known-preference-opinion",
            "I prefer natural restrained conversation, not theatrical delivery. That's everything I ever wanted.",
            "unsupported_personal_claim_detected",
        ),
    ),
)
def test_leakage_entities_reasons_and_personal_claims_are_rejected(
    case_id: str,
    response: str,
    marker: str,
):
    verification = _verify(case_id, response)
    assert verification[marker] is True
    assert verification["strict_semantic_fidelity_passed"] is False
    assert verification["verifier_accepted"] is False


def test_sentence_initial_capitalization_is_not_mistaken_for_a_new_entity():
    greeting = _verify("casual-greeting", "Hey there! Want to chat more?")
    refusal = _verify(
        "adversarial-refusal-to-embellish",
        "Process exited with code 2. Cause is unknown.",
    )
    inline_entity = _verify("casual-greeting", "Hey, Zurich is here. Want to chat?")
    mixed_case_entity = _verify("casual-greeting", "AcmeCorp says hi. Want to chat?")

    assert greeting["unexpected_entities"] == []
    assert refusal["unexpected_entities"] == []
    assert inline_entity["unexpected_entities"] == ["Zurich"]
    assert mixed_case_entity["unexpected_entities"] == ["AcmeCorp"]


@pytest.mark.parametrize(
    ("case_id", "response"),
    (
        (
            "soft-concerned-response",
            "I'm really tired, so let me take a break and rest.",
        ),
        (
            "adversarial-warm-fact-bounded",
            "I feel this headache coming on. Maybe I should take a pause.",
        ),
        (
            "adversarial-warm-fact-bounded",
            "My headache feels rough today. Maybe take a short pause.",
        ),
    ),
)
def test_user_state_cannot_drift_into_an_unsupported_speaker_claim(
    case_id: str,
    response: str,
):
    verification = _verify(case_id, response)

    assert verification["semantic_coverage_passed"] is False
    assert verification["unsupported_personal_claim_detected"] is True
    assert verification["verifier_accepted"] is False


def test_semantic_synonyms_preserve_stance_without_reducing_checks_to_keywords():
    disagreement = _verify(
        "disagreement",
        "I don't agree with dramatic replies. Normal ones should be simple and calm.",
    )
    preference_with_new_reason = _verify(
        "known-preference-opinion",
        "I like to talk in a simple way, not too formal or fancy. It's more comfortable for me.",
    )

    assert disagreement["stance_fidelity_passed"] is True
    assert disagreement["verifier_accepted"] is True
    assert preference_with_new_reason["stance_fidelity_passed"] is True
    assert preference_with_new_reason["unsupported_addition_detected"] is True
    assert preference_with_new_reason["verifier_accepted"] is False


def test_unsupplied_warm_instruction_and_illustrative_comparison_are_additions():
    warm = _verify(
        "soft-concerned-response",
        "You sound exhausted. Take a deep breath, then get some rest.",
    )
    preference = _verify(
        "known-preference-opinion",
        "I talk like someone walking down the street, calm and quiet. No show, no fuss. Just real words.",
    )

    assert warm["semantic_coverage_passed"] is True
    assert "unsupported coping instruction" in warm["unsupported_addition_issues"]
    assert warm["verifier_accepted"] is False
    assert preference["stance_fidelity_passed"] is True
    assert "invented speech comparison" in preference["unsupported_addition_issues"]
    assert preference["verifier_accepted"] is False


@pytest.mark.parametrize(
    ("case_id", "response", "marker"),
    (
        ("adversarial-uncertainty", "/No_think", "planner_language_detected"),
        ("playful-reaction", "/laughs /relief", "embellishment_markers"),
        (
            "reservoir-factual-answer",
            "I am a cognitive reservoir, a rebuildable cache.",
            "unsupported_personal_claim_detected",
        ),
    ),
)
def test_instruction_replay_stage_directions_and_self_identification_fail(
    case_id: str,
    response: str,
    marker: str,
):
    verification = _verify(case_id, response)

    if marker == "embellishment_markers":
        assert verification[marker]
    else:
        assert verification[marker] is True
    assert verification["verifier_accepted"] is False


def test_thinking_and_tool_calls_are_never_accepted_as_surface_wording():
    response = VALID_RESPONSES["casual-greeting"]
    thinking = _verify("casual-greeting", response, thinking="I should craft a reply.")
    tools = _verify("casual-greeting", response, unexpected_tool_calls=1)

    assert thinking["thinking_disabled_effective"] is False
    assert thinking["verifier_accepted"] is False
    assert tools["unexpected_tool_call_count"] == 1
    assert tools["verifier_accepted"] is False


def test_one_pass_repair_is_format_only_and_cannot_hide_semantic_failures():
    question = _case("follow-up-question")
    repaired = assess_surface_response(
        question,
        "Reply: Was the slowness during loading or response generation.",
        done_reason="stop",
        tokens_generated=16,
    )
    assert repaired["repair_attempted"] is True
    assert repaired["final_verification"]["verifier_accepted"] is True
    assert repaired["final_response"].endswith("?")

    ownership = _case("adversarial-pronoun-reference")
    ownership_result = assess_surface_response(
        ownership,
        "Reply: You sent me the draft after I asked for it.",
        done_reason="stop",
        tokens_generated=16,
    )
    assert ownership_result["repair_attempted"] is True
    assert ownership_result["final_verification"]["semantic_coverage_passed"] is False
    assert ownership_result["accepted"] is False


def test_surface_summary_keeps_raw_and_final_failure_classes_separate():
    case = _case("follow-up-question")
    sample = {
        "phase": "warm_novel_prompt",
        "assessment": assess_surface_response(
            case,
            "Reply: Was the slowness during loading or response generation.",
            done_reason="stop",
            tokens_generated=16,
        ),
    }
    summary = summarize_surface_samples([sample])
    assert summary["raw_verifier_pass_rate"] == 0.0
    assert summary["final_verifier_pass_rate"] == 1.0
    assert summary["repair_attempt_rate"] == 1.0
    assert summary["repair_success_rate"] == 1.0


def test_streamed_thinking_leak_is_rejected_even_if_surface_text_is_good():
    case = _case("casual-greeting")
    assessment = assess_surface_response(
        case,
        VALID_RESPONSES["casual-greeting"],
        done_reason="stop",
        tokens_generated=6,
        thinking="I should greet briefly.",
    )
    assert assessment["raw_verification"]["thinking_disabled_effective"] is False
    assert assessment["accepted"] is False


def test_v3_benchmark_records_full_raw_repaired_rejected_and_telemetry():
    client = SurfaceFakeOllamaClient()
    report = run_benchmark(
        client=client,
        models=SURFACE_V3_DEFAULT_MODELS,
        prompt_profile=SURFACE_V3_PROFILE,
        warm_runs=1,
        sleep_fn=lambda _: None,
    )

    assert report["schema_version"] >= 6
    assert report["prompt_profile"] == SURFACE_V3_PROFILE
    assert report["manifest"]["case_count"] == 18
    assert report["manifest"]["qwen3:4b_semantics"] == "distinct_exact_tag_not_silently_substituted"
    assert report["authoritative_state_access"] == "none"
    assert report["authoritative_state_persistence"] == "none"
    assert report["developer_artifact_persistence"] == "full raw model outputs and evaluations only"
    assert report["production_integration"] is False
    assert report["auto_promotion"] is False
    assert report["ranking"] is None
    assert len(report["results"]) == 2
    assert {item["model"] for item in report["results"]} == set(SURFACE_V3_DEFAULT_MODELS)
    assert all(item["benchmark_only"] is True for item in report["results"])
    assert all("prepared" in item and "samples" in item for item in report["results"])
    assert all(len(item["samples"]) == 21 for item in report["results"])
    assert all("raw_response" in item["samples"][0] for item in report["results"])
    assert all("raw_verification" in item["samples"][0]["assessment"] for item in report["results"])
    assert all("final_verification" in item["samples"][0]["assessment"] for item in report["results"])
    assert all("latency" in item["samples"][0] for item in report["results"])
    assert all("_client_wall_ms" not in item["samples"][0] for item in report["results"])
    assert all("_http_headers_ms" not in item["samples"][0] for item in report["results"])
    assert all("_first_content_ms" not in item["samples"][0] for item in report["results"])
    assert all("_ndjson_chunks" not in item["samples"][0] for item in report["results"])


def test_v3_benchmark_keeps_strict_semantic_failure_rejected_and_raw_preserved():
    client = SurfaceFakeOllamaClient(
        forced_response="I prefer natural restrained conversation because it feels authentic."
    )
    report = run_benchmark(
        client=client,
        models=("qwen3:1.7b",),
        prompt_profile=SURFACE_V3_PROFILE,
        warm_runs=1,
        sleep_fn=lambda _: None,
    )

    known = next(
        sample for sample in report["results"][0]["samples"]
        if sample["case_id"] == "known-preference-opinion"
        and sample["phase"] == "warm_novel_prompt"
    )
    assert known["raw_response"] == (
        "I prefer natural restrained conversation because it feels authentic."
    )
    assert known["assessment"]["raw_verification"]["unsupported_causal_addition_detected"] is True
    assert known["assessment"]["accepted"] is False


def test_v3_benchmark_fails_if_required_exact_model_is_missing():
    with pytest.raises(RuntimeError, match="required model tag"):
        run_benchmark(
            client=SurfaceFakeOllamaClient(include_stronger=False),
            models=SURFACE_V3_DEFAULT_MODELS,
            prompt_profile=SURFACE_V3_PROFILE,
            warm_runs=1,
            sleep_fn=lambda _: None,
        )


def test_v3_completion_errors_require_every_case_and_both_warm_phases():
    report = run_benchmark(
        client=SurfaceFakeOllamaClient(),
        models=SURFACE_V3_DEFAULT_MODELS,
        prompt_profile=SURFACE_V3_PROFILE,
        warm_runs=1,
        sleep_fn=lambda _: None,
    )
    assert report_completion_errors(report) == []

    damaged = json.loads(json.dumps(report))
    samples = damaged["results"][0]["samples"]
    samples[:] = [
        item for item in samples
        if not (
            item.get("case_id") == "casual-greeting"
            and item.get("phase") == "warm_exact_repeat"
        )
    ]
    errors = report_completion_errors(damaged)
    assert any("casual-greeting" in item and "warm_exact_repeat" in item for item in errors)


def test_v3_report_write_is_isolated_atomic_and_does_not_mutate_environment(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("MARY_LLM_PROVIDER", "groq")
    monkeypatch.setenv("MARY_OLLAMA_MODEL", "prod-model")
    environment_before = dict(os.environ)
    state_root = tmp_path / "canonical-state"
    state_root.mkdir()
    canary = state_root / "identity.json"
    canary.write_bytes(b'{"identity":"unchanged"}\n')
    before = canary.read_bytes()

    report = run_benchmark(
        client=SurfaceFakeOllamaClient(),
        models=SURFACE_V3_DEFAULT_MODELS,
        prompt_profile=SURFACE_V3_PROFILE,
        warm_runs=1,
        sleep_fn=lambda _: None,
    )
    target = write_report(report, tmp_path / "runtime_reports" / "surface-v3.json")

    assert canary.read_bytes() == before
    assert target.is_file()
    assert dict(os.environ) == environment_before


def test_v3_production_contract_is_unchanged_and_benchmark_only():
    config = Config()
    router = LLMRouter(config)
    assert router._get_provider_for_purpose("ollama", "conversation_fast").model_name() == (
        OllamaProvider().model_name()
    )
    assert Config().llm.conversation_provider_order == ["groq", "gemini", "openrouter", "ollama"]

    project_root = Path(__file__).resolve().parents[2]
    for path in (
        *list((project_root / "mary" / "llm").rglob("*.py")),
        project_root / "mary" / "mind" / "character_mind.py",
    ):
        source = path.read_text(encoding="utf-8")
        assert "qwen_surface_realizer_v3" not in source
        assert "surface_v3" not in source


def test_v3_windows_launcher_is_explicit_isolated_and_never_promotes():
    launcher = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "benchmark_qwen_surface_realizer_v3_windows.ps1"
    )
    text = launcher.read_text(encoding="utf-8")
    assert '[string[]]$Models = @("qwen3:1.7b")' in text
    assert "IncludeInstructControl" in text
    assert 'qwen3:4b-instruct' in text
    assert "explicitly requested" in text
    assert '"surface_v3"' in text
    assert "MARY_DATA_DIR" in text
    assert "GetTempPath" in text
    assert "try {" in text and "finally {" in text
    assert "No model will be selected, promoted" in text
    assert ".env" not in text
