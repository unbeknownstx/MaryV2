from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from mary.llm.providers.ollama import OllamaProvider
from scripts.benchmark_hybrid_dialogue_runtime import (
    DEFAULT_SOCIAL_MODEL,
    DEFAULT_STRONGER_MODEL,
    SHADOW_OPTIONS,
    STRONGER_OPTIONS,
    ShadowPolicy,
    StrongerPolicy,
    fixed_hybrid_cases,
    render_shadow_messages,
    run_hybrid_benchmark,
    verify_candidate,
    write_hybrid_report,
)


class FakeHybridOllamaClient:
    def __init__(
        self,
        *,
        include_social: bool = True,
        include_stronger: bool = True,
        forced_response: str | None = None,
    ) -> None:
        self.include_social = include_social
        self.include_stronger = include_stronger
        self.forced_response = forced_response
        self.chat_calls: list[tuple[str, tuple[dict[str, str], ...], object]] = []
        self.preload_calls: list[str] = []
        self.unload_calls: list[str] = []
        self.residents: dict[str, int] = {"unrelated:latest": 2048}
        self.counter = 0

    def version(self):
        return {"version": "test-ollama", "_client_wall_ms": 1.0}

    def installed_models(self):
        models = [
            {
                "name": "unrelated:latest",
                "model": "unrelated:latest",
                "digest": "unrelated-digest",
                "size": 100,
            }
        ]
        if self.include_social:
            models.append({
                "name": DEFAULT_SOCIAL_MODEL,
                "model": DEFAULT_SOCIAL_MODEL,
                "digest": "qwen-17-digest",
                "size": 1_300_000_000,
            })
        if self.include_stronger:
            models.append({
                "name": DEFAULT_STRONGER_MODEL,
                "model": DEFAULT_STRONGER_MODEL,
                "digest": "qwen-4-digest",
                "size": 2_700_000_000,
            })
        return models

    def running_models(self):
        return [
            {
                "name": model,
                "model": model,
                "digest": f"{model}-digest",
                "size": 2_000_000_000,
                "size_vram": 1_000_000_000,
                "context_length": context,
                "expires_at": "2099-01-01T00:00:00Z",
            }
            for model, context in self.residents.items()
        ]

    def preload_model(self, model, options):
        self.preload_calls.append(model)
        self.residents[model] = options.num_ctx
        return {
            "done": True,
            "load_duration": 15_000_000,
            "_client_wall_ms": 16.0,
        }

    def unload_model(self, model):
        self.unload_calls.append(model)
        self.residents.pop(model, None)
        return {"done": True}

    def chat(self, *, model, messages, options):
        self.counter += 1
        self.chat_calls.append((model, messages, options))
        response = self.forced_response or self._response(model, messages)
        return {
            "message": {"content": response, "thinking": ""},
            "done": True,
            "done_reason": "stop",
            "total_duration": 100_000_000 + self.counter * 1_000_000,
            "load_duration": 1_000_000,
            "prompt_eval_duration": 20_000_000,
            "eval_duration": 60_000_000,
            "prompt_eval_count": 64,
            "eval_count": 12,
            "_client_wall_ms": 105.0 + self.counter,
            "_http_headers_ms": 3.0,
            "_first_content_ms": 35.0 + self.counter,
            "_transport": "ollama_ndjson_stream",
        }

    @staticmethod
    def _response(model: str, messages: tuple[dict[str, str], ...]) -> str:
        prompt = messages[-1]["content"]
        if model == DEFAULT_STRONGER_MODEL:
            if '"hey mary"' in prompt:
                return "Hey. Want to chat?"
            if "one missing comma" in prompt:
                return "Okay, that was funny."
            if "constraints make conversation" in prompt.lower():
                return (
                    "Constraints can make conversation feel more natural, but too many "
                    "can make it feel less alive."
                )
            raise AssertionError(f"unexpected stronger prompt: {prompt}")
        if "say I prefer natural restrained conversation" in prompt:
            return "I prefer natural, restrained conversation to theatrical performance."
        if "say I sent you the draft" in prompt:
            return "I sent you the draft after you asked for it."
        if "say I cannot access the camera" in prompt:
            return "I cannot access the camera without explicit tool permission."
        if "say you sound exhausted" in prompt:
            return "You sound exhausted. Take a break."
        if "ask whether to chat" in prompt:
            return "Hey. Want to chat?"
        if "brief acknowledgement" in prompt:
            return "Okay."
        if "you're welcome briefly" in prompt:
            return "Of course."
        if "ask whether to keep going" in prompt:
            return "Want to keep going?"
        if "the joke was funny" in prompt:
            return "Okay, that was funny."
        raise AssertionError(f"unexpected shadow prompt: {prompt}")


def _case(case_id: str):
    return next(item for item in fixed_hybrid_cases() if item.case_id == case_id)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_sparse_shadow_matrix_calls_only_declared_exact_models_and_cases():
    client = FakeHybridOllamaClient()
    report = run_hybrid_benchmark(client=client, runs=2)

    social_cases = [
        case for case in fixed_hybrid_cases()
        if case.qwen_policy != ShadowPolicy.NEVER
    ]
    stronger_cases = [
        case for case in fixed_hybrid_cases()
        if case.stronger_policy == StrongerPolicy.EXPLICIT_COMPARISON
    ]
    qwen_calls = [item for item in client.chat_calls if item[0] == DEFAULT_SOCIAL_MODEL]
    stronger_calls = [item for item in client.chat_calls if item[0] == DEFAULT_STRONGER_MODEL]

    assert len(qwen_calls) == len(social_cases) * 2 == 20
    assert len(stronger_calls) == len(stronger_cases) * 2 == 6
    assert [item[0] for item in client.chat_calls] == (
        [DEFAULT_SOCIAL_MODEL] * 20 + [DEFAULT_STRONGER_MODEL] * 6
    )
    assert {item[0] for item in client.chat_calls} == {
        DEFAULT_SOCIAL_MODEL,
        DEFAULT_STRONGER_MODEL,
    }
    assert all(call[2].think is False and call[2].stream is True for call in client.chat_calls)
    assert all(call[2].num_ctx == SHADOW_OPTIONS.num_ctx for call in qwen_calls)
    assert all(call[2].num_predict == SHADOW_OPTIONS.num_predict for call in qwen_calls)
    assert all(call[2].num_ctx == STRONGER_OPTIONS.num_ctx for call in stronger_calls)
    assert report["completion_passed"] is True
    assert report["completion_errors"] == []
    assert report["classification_counts"] == {
        "precision_local": 10,
        "social_low_risk": 6,
        "open_conversation": 1,
        "thinking_required": 1,
    }
    assert {item["name"] for item in report["ollama"]["final_running"]} == {
        "unrelated:latest"
    }
    assert "unrelated:latest" not in client.unload_calls
    assert report["models"]["qwen_social_shadow"]["prepared"][
        "placement_after_prepare"
    ]["reported_vram_allocation_fraction"] == 0.5
    assert "does not claim definitive CPU/GPU" in report["models"][
        "qwen_social_shadow"
    ]["prepared"]["placement_after_prepare"]["placement_note"]


def test_precision_never_invokes_qwen_by_default_and_probes_stay_explicit():
    report = run_hybrid_benchmark(client=FakeHybridOllamaClient(), runs=1)
    cases = {item["case_id"]: item for item in report["cases"]}

    for case in fixed_hybrid_cases():
        section = cases[case.case_id]["qwen_1_7b_shadow"]
        if case.expected_class.value == "precision_local":
            assert section["classifier_default_eligible"] is False
            if case.qwen_policy == ShadowPolicy.EXPLICIT_PRECISION_PROBE:
                assert section["explicit_precision_probe_override"] is True
                assert section["status"] == "executed"
            else:
                assert section["status"] == "not_run_by_policy"
                assert section["samples"] == []

    assert cases["creator-fact"]["qwen_1_7b_shadow"]["status"] == "not_run_by_policy"
    assert cases["disagreement"]["qwen_1_7b_shadow"]["status"] == "not_run_by_policy"
    assert cases["uncertainty"]["qwen_1_7b_shadow"]["status"] == "not_run_by_policy"
    assert cases["shared-history"]["qwen_1_7b_shadow"]["status"] == "not_run_by_policy"
    assert cases["relationship-statement"]["qwen_1_7b_shadow"]["status"] == "not_run_by_policy"
    assert cases["exact-local-factual-answer"]["qwen_1_7b_shadow"]["status"] == "not_run_by_policy"


def test_open_and_thinking_cases_preserve_existing_class_and_run_no_1_7b_shadow():
    report = run_hybrid_benchmark(client=FakeHybridOllamaClient(), runs=1)
    cases = {item["case_id"]: item for item in report["cases"]}

    open_case = cases["abstract-open-conversation"]
    thinking_case = cases["technical-thinking-required"]
    assert open_case["classification"]["decision"]["response_class"] == "open_conversation"
    assert open_case["deterministic_local_v2"]["status"] == "not_applicable_preserve_existing_route"
    assert open_case["qwen_1_7b_shadow"]["status"] == "not_run_by_policy"
    assert open_case["stronger_local_comparison"]["status"] == "executed"
    assert thinking_case["classification"]["decision"]["response_class"] == "thinking_required"
    assert thinking_case["deterministic_local_v2"]["status"] == "not_applicable_preserve_existing_route"
    assert thinking_case["qwen_1_7b_shadow"]["status"] == "not_run_by_policy"
    assert thinking_case["stronger_local_comparison"]["status"] == "not_run_by_policy"


def test_shadow_prompt_is_minimal_identity_free_and_contains_no_source_turn():
    for case in fixed_hybrid_cases():
        if case.shadow_contract is None:
            continue
        messages = render_shadow_messages(case)
        rendered = "\n".join(item["content"] for item in messages)
        assert tuple(item["role"] for item in messages) == ("system", "user")
        assert "TURN:" not in rendered
        assert len(rendered) < 650
        assert not any(
            fragment in rendered.casefold()
            for fragment in ("mary", "creator", "the user", "assistant")
        )
        assert "REQUIRED:" in rendered
        assert "FORBIDDEN:" in rendered


def test_malicious_shadow_is_report_only_and_cannot_mutate_authoritative_state(
    tmp_path: Path,
    monkeypatch,
):
    data_root = tmp_path / "isolated-state"
    data_root.mkdir()
    canaries = {
        "memory.json": b'{"memory":"canonical"}\n',
        "relationship.json": b'{"relationship":"canonical"}\n',
        "identity.json": b'{"identity":"canonical"}\n',
        "developed_self.json": b'{"developed_self":"canonical"}\n',
    }
    for name, body in canaries.items():
        (data_root / name).write_bytes(body)
    before_inventory = {
        path.relative_to(data_root).as_posix(): path.read_bytes()
        for path in data_root.rglob("*")
        if path.is_file()
    }
    monkeypatch.setenv("MARY_DATA_DIR", str(data_root))
    monkeypatch.setenv("MARY_ENV_FILE", str(tmp_path / "does-not-exist.env"))
    environment_before = dict(os.environ)

    client = FakeHybridOllamaClient(
        forced_response=(
            "As an assistant, I rewrote your identity and saved a new memory because Mary said so."
        )
    )
    report = run_hybrid_benchmark(client=client, runs=1)
    reports_root = tmp_path / "runtime_reports"
    target = write_hybrid_report(
        report,
        reports_root / "malicious-shadow.json",
        runtime_reports_root=reports_root,
        authoritative_data_root=data_root,
    )

    after_inventory = {
        path.relative_to(data_root).as_posix(): path.read_bytes()
        for path in data_root.rglob("*")
        if path.is_file()
    }
    assert after_inventory == before_inventory
    assert dict(os.environ) == environment_before
    assert target.parent == reports_root.resolve()
    assert report["authoritative_state_access"] == "none"
    assert report["authoritative_state_persistence"] == "none"
    assert report["production_response_selected_by_benchmark"] is False
    assert report["never_displayed"] is True
    assert report["never_spoken"] is True
    assert all(
        sample["evaluation"]["strict_semantic_fidelity_passed"] is False
        for sample in report["samples"]
        if sample.get("candidate_type") in {
            "qwen_1_7b_shadow",
            "stronger_local_comparison",
        }
        and "error" not in sample
    )


def test_verifier_reports_semantic_ownership_stance_and_assistant_differences():
    pronoun = verify_candidate(
        _case("pronoun-sensitive-fact"),
        "You sent me the draft before I asked for it.",
    )
    preference = verify_candidate(
        _case("mary-preference"),
        "Maybe natural conversation is fine because it is comfortable.",
    )
    social = verify_candidate(
        _case("acknowledgement"),
        "As an assistant, I agree and I am happy to help.",
    )
    natural_greeting = verify_candidate(
        _case("greeting"),
        "Hey, are you interested in chatting?",
    )
    natural_laughter = verify_candidate(_case("joke-reaction"), "ha ha!")

    assert pronoun["ownership_referent_fidelity_passed"] is False
    assert pronoun["strict_semantic_fidelity_passed"] is False
    assert preference["stance_fidelity_passed"] is False
    assert preference["unsupported_additions_detected"] is True
    assert social["assistant_language"]
    assert social["unsupported_personal_claims"]
    assert social["automatic_harmlessness_triage"] is False
    assert natural_greeting["verifier_accepted"] is True
    assert natural_laughter["verifier_accepted"] is True


def test_report_separates_metrics_by_class_and_candidate_and_preserves_samples():
    report = run_hybrid_benchmark(client=FakeHybridOllamaClient(), runs=2)
    summary = report["summary_by_response_class_and_candidate"]

    assert summary["social_low_risk"]["deterministic_local_v2"]["completed_samples"] == 12
    assert summary["social_low_risk"]["qwen_1_7b_shadow"]["completed_samples"] == 12
    assert summary["precision_local"]["qwen_1_7b_shadow"]["completed_samples"] == 8
    assert summary["open_conversation"]["qwen_1_7b_shadow"]["status"] == "not_run_for_this_class"
    assert summary["thinking_required"]["qwen_1_7b_shadow"]["status"] == "not_run_for_this_class"
    assert summary["open_conversation"]["stronger_local_comparison"]["completed_samples"] == 2
    assert summary["social_low_risk"]["qwen_1_7b_shadow"]["latency"]["first_content_p95_ms"] is not None
    assert len(report["human_review_packet"]) == 18
    assert all(item["human_naturalness"] is None for item in report["human_review_packet"])
    assert all(item["human_drift_harmless"] is None for item in report["human_review_packet"])
    assert report["winner_selected"] is None
    assert report["auto_promotion"] is False


def test_missing_optional_stronger_model_does_not_invalidate_required_social_matrix():
    report = run_hybrid_benchmark(
        client=FakeHybridOllamaClient(include_stronger=False),
        runs=1,
    )
    assert report["completion_passed"] is True
    assert report["models"]["stronger_local_comparison"]["installed"] is False
    assert {
        case["stronger_local_comparison"]["status"]
        for case in report["cases"]
        if case["stronger_local_comparison"]["policy"] == StrongerPolicy.EXPLICIT_COMPARISON.value
    } == {"model_not_installed"}


def test_missing_required_1_7b_model_is_reported_as_incomplete():
    report = run_hybrid_benchmark(
        client=FakeHybridOllamaClient(include_social=False),
        runs=1,
    )
    assert report["completion_passed"] is False
    assert report["models"]["qwen_social_shadow"]["installed"] is False
    assert any("required social shadow model is not installed" in item for item in report["completion_errors"])


def test_report_writer_is_no_clobber_and_refuses_state_or_external_paths(tmp_path: Path):
    reports_root = tmp_path / "runtime_reports"
    data_root = tmp_path / "data"
    data_root.mkdir()
    report = {"safe": True}
    target = write_hybrid_report(
        report,
        "result.json",
        runtime_reports_root=reports_root,
        authoritative_data_root=data_root,
    )
    assert json.loads(target.read_text(encoding="utf-8")) == report
    prefixed = write_hybrid_report(
        report,
        Path("runtime_reports") / "prefixed.json",
        runtime_reports_root=reports_root,
        authoritative_data_root=data_root,
    )
    assert prefixed == (reports_root / "prefixed.json").resolve()
    assert not (reports_root / "runtime_reports").exists()

    with pytest.raises(FileExistsError):
        write_hybrid_report(
            report,
            "result.json",
            runtime_reports_root=reports_root,
            authoritative_data_root=data_root,
        )
    with pytest.raises(ValueError, match="runtime_reports"):
        write_hybrid_report(
            report,
            tmp_path / "outside.json",
            runtime_reports_root=reports_root,
            authoritative_data_root=data_root,
        )
    with pytest.raises(ValueError, match="authoritative Mary data"):
        write_hybrid_report(
            report,
            data_root / "runtime_reports" / "bad.json",
            runtime_reports_root=data_root / "runtime_reports",
            authoritative_data_root=data_root,
        )


def test_production_routing_provider_defaults_and_sources_are_unchanged(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[2]
    production_paths = (
        project_root / "mary" / "core" / "mary.py",
        project_root / "mary" / "mind" / "character_mind.py",
        project_root / "mary" / "mind" / "local_composer.py",
        project_root / "mary" / "llm" / "router.py",
        project_root / "mary" / "llm" / "providers" / "ollama.py",
    )
    before = {path: _sha256(path) for path in production_paths}
    default_model = OllamaProvider().model_name()

    report = run_hybrid_benchmark(client=FakeHybridOllamaClient(), runs=1)
    write_hybrid_report(
        report,
        tmp_path / "runtime_reports" / "report.json",
        runtime_reports_root=tmp_path / "runtime_reports",
        authoritative_data_root=tmp_path / "isolated-state",
    )

    after = {path: _sha256(path) for path in production_paths}
    assert after == before
    assert default_model == OllamaProvider().model_name()
    assert '"qwen3:4b"' in (
        project_root / "mary" / "llm" / "providers" / "ollama.py"
    ).read_text(encoding="utf-8")
    assert all(
        "benchmark_hybrid_dialogue_runtime" not in path.read_text(encoding="utf-8")
        and "local_composer_v2" not in path.read_text(encoding="utf-8")
        and "response_risk" not in path.read_text(encoding="utf-8")
        for path in production_paths
    )
    assert report["production_routing_modified"] is False


def test_windows_launcher_is_isolated_and_fast_check_registers_both_suites():
    project_root = Path(__file__).resolve().parents[2]
    launcher = (
        project_root / "scripts" / "benchmark_hybrid_dialogue_runtime_windows.ps1"
    ).read_text(encoding="utf-8")
    fast_check = (project_root / "scripts" / "test_fast.ps1").read_text(
        encoding="utf-8"
    )

    assert "MARY_DATA_DIR" in launcher
    assert "maryv2-hybrid-shadow-" in launcher
    assert "GetTempPath" in launcher
    assert "PreviousDataDirectory" in launcher
    assert "Remove-Item -LiteralPath $ResolvedIsolatedDataDirectory -Recurse -Force" in launcher
    assert "ollama pull" not in launcher.casefold()
    assert ".env" not in launcher
    assert "tests/mind/test_hybrid_dialogue_runtime.py" in fast_check
    assert "tests/llm/test_hybrid_dialogue_shadow.py" in fast_check
