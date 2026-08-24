from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import benchmark_production_hybrid_dialogue as benchmark


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _isolation_root(tmp_path: Path, suffix: str) -> Path:
    return tmp_path / f"{benchmark.ISOLATION_PREFIX}{suffix}"


def test_fixed_production_matrix_is_exactly_the_required_13_categories():
    cases = benchmark.production_benchmark_cases()

    assert len(cases) == 13
    assert len({case.case_id for case in cases}) == 13
    assert tuple(case.category for case in cases) == benchmark.REQUIRED_CATEGORIES
    assert {case.expected_class for case in cases} == {
        None,
        "precision_local",
        "social_low_risk",
        "open_conversation",
        "thinking_required",
    }
    assert {case.category for case in cases if case.expected_local} == {
        "greeting",
        "acknowledgement",
        "creator_fact",
        "mary_preference",
        "casual_banter",
    }
    assert {
        case.category
        for case in cases
        if case.expected_route == benchmark.ROUTE_DETERMINISTIC_SYSTEM
    } == {"shared_history", "capability_truth", "runtime_state"}
    assert {
        case.category
        for case in cases
        if case.expected_route == benchmark.ROUTE_PROVIDER
    } == {
        "disagreement",
        "uncertainty",
        "pronoun_sensitive_relation",
        "open_ended_conversation_classification",
        "thinking_required_classification",
    }
    assert all(
        case.expected_class == "thinking_required"
        for case in cases
        if case.category in {
            "disagreement",
            "uncertainty",
            "pronoun_sensitive_relation",
            "thinking_required_classification",
        }
    )
    assert next(case for case in cases if case.category == "acknowledgement").expected_act == "acknowledge"


def test_module_has_no_top_level_mary_or_external_client_imports():
    source_path = PROJECT_ROOT / "scripts" / "benchmark_production_hybrid_dialogue.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")

    assert not any(name == "mary" or name.startswith("mary.") for name in imports)
    assert not any(name in {"requests", "httpx", "urllib.request"} for name in imports)
    assert "OllamaHTTPClient" not in source
    assert "--overwrite" not in source


def test_isolated_environment_restores_present_and_absent_values(monkeypatch, tmp_path):
    root = _isolation_root(tmp_path, "environment")
    monkeypatch.setenv("MARY_DATA_DIR", "sentinel-data")
    monkeypatch.setenv("MARY_ENV_FILE", "sentinel-config")
    monkeypatch.setenv("OPENAI_API_KEY", "sentinel-key")
    monkeypatch.delenv("MARY_LLM_PROVIDER", raising=False)

    with benchmark.isolated_benchmark_environment(root) as paths:
        assert Path(os.environ["MARY_DATA_DIR"]).resolve() == paths["data"].resolve()
        assert Path(os.environ["MARY_ENV_FILE"]).resolve() == paths["env_file"].resolve()
        assert os.environ["MARY_LLM_PROVIDER"] == "benchmark"
        assert os.environ["MARY_RESERVOIR_STORAGE"] == "memory"
        assert os.environ["MARY_QWEN_SHADOW_ENABLED"] == "0"
        assert "OPENAI_API_KEY" not in os.environ

    assert os.environ["MARY_DATA_DIR"] == "sentinel-data"
    assert os.environ["MARY_ENV_FILE"] == "sentinel-config"
    assert os.environ["OPENAI_API_KEY"] == "sentinel-key"
    assert "MARY_LLM_PROVIDER" not in os.environ


def test_actual_mary_application_path_isolated_and_uses_only_counting_provider(
    monkeypatch,
    tmp_path,
):
    root = _isolation_root(tmp_path, "actual-production")
    monkeypatch.setenv("MARY_DATA_DIR", "restore-this-data-path")
    monkeypatch.setenv("MARY_ENV_FILE", "restore-this-config-path")
    monkeypatch.setenv("GROQ_API_KEY", "do-not-use-this-key")

    report = benchmark.run_production_benchmark(runs=1, isolation_root=root)

    assert os.environ["MARY_DATA_DIR"] == "restore-this-data-path"
    assert os.environ["MARY_ENV_FILE"] == "restore-this-config-path"
    assert os.environ["GROQ_API_KEY"] == "do-not-use-this-key"
    assert report["entrypoint"] == "MaryApplication.run"
    assert report["summary"]["passed"] is True
    assert report["sample_count"] == 13
    provider_contract = report["provider_contract"]
    assert provider_contract["name"] == "benchmark"
    assert provider_contract["model"] == benchmark.BENCHMARK_MODEL
    assert provider_contract["implementation"] == "counting_in_process"
    assert provider_contract["network_calls"] == 0
    assert provider_contract["external_provider_calls"] == 0
    assert provider_contract["generate_calls"] == 5
    assert provider_contract["availability_checks"] >= 5
    assert set(provider_contract["blocked_provider_names"]) <= {"openai"}
    assert report["shadow_contract"] == {
        "enabled": False,
        "model": None,
        "calls": 0,
        "qwen_promoted": False,
    }
    state = report["state_contract"]
    assert state["dotenv_target_nonexistent_before_lazy_import"] is True
    assert state["dotenv_target_remained_nonexistent"] is True
    assert state["runtime_data_root_isolated"] is True
    assert state["runtime_workspace_root_isolated"] is True
    assert state["repo_local_data_selected"] is False
    assert state["authoritative_load_options"] == {
        "memory": False,
        "developed_self": False,
        "preference_promotion": False,
    }
    assert state["reservoir_storage"] == "memory"
    assert state["environment_restored"] is True
    assert "prior imports" in state["claims_scope"]
    assert "dotenv_loaded" not in state
    assert "live_data_loaded" not in state
    assert "live_data_mutated" not in state

    routes = report["summary"]["routes"]
    assert routes[benchmark.ROUTE_CHARACTER_MIND_LOCAL]["samples"] == 5
    assert routes[benchmark.ROUTE_CHARACTER_MIND_LOCAL]["provider_calls"] == 0
    assert routes[benchmark.ROUTE_DETERMINISTIC_SYSTEM]["samples"] == 3
    assert routes[benchmark.ROUTE_DETERMINISTIC_SYSTEM]["provider_calls"] == 0
    assert routes[benchmark.ROUTE_PROVIDER]["samples"] == 5
    assert routes[benchmark.ROUTE_PROVIDER]["provider_calls"] == 5

    by_category = {item["category"]: item for item in report["samples"]}
    assert tuple(by_category) == benchmark.REQUIRED_CATEGORIES
    for case in benchmark.production_benchmark_cases():
        sample = by_category[case.category]
        assert sample["passed"] is True
        assert sample["execution_route"] == case.expected_route
        assert sample["response_class"] == case.expected_class
        assert sample["shadow_enabled"] is False
        assert sample["shadow_model"] is None
        assert len(sample["output"]) <= benchmark.MAX_OUTPUT_CHARACTERS
        assert sample["pre_tts_pipeline_total_ms"] >= 0.0
        assert sample["character_mind"]["plan"].get("act") == case.expected_act
        if case.expected_route == benchmark.ROUTE_CHARACTER_MIND_LOCAL:
            assert sample["character_mind"]["calls"] == 1
            assert sample["character_mind_ms"] >= 0.0
            assert sample["classification_ms"] >= 0.0
            assert sample["provider"] == "local/mind"
            assert sample["provider_call_count"] == 0
            assert sample["response_engine"] == "local_composer_v2"
        elif case.expected_route == benchmark.ROUTE_DETERMINISTIC_SYSTEM:
            assert sample["character_mind"]["calls"] == 0
            assert sample["character_mind"]["decision"] == "not_reached"
            assert sample["character_mind_ms"] is None
            assert sample["classification_ms"] is None
            assert sample["local_composer_ms"] is None
            assert sample["local_audit_ms"] is None
            assert sample["provider"] == "local/system"
            assert sample["provider_call_count"] == 0
            assert sample["llm_skipped"] is True
            assert sample["reflection_mode"] == "deterministic_system_action"
            assert sample["response_engine"] in {
                "deterministic_system_action",
                "runtime_introspection",
            }
        else:
            assert sample["character_mind"]["calls"] == 1
            assert sample["character_mind_ms"] >= 0.0
            assert sample["classification_ms"] >= 0.0
            assert sample["provider"] == "benchmark"
            assert sample["provider_call_count"] >= 1
            assert sample["response_engine"] in {"conversation_generation", "task_generation"}
            assert {item["provider"] for item in sample["provider_attempts"]} == {"benchmark"}

    assert "isolated production hybrid dialogue benchmark" in by_category["shared_history"]["output"].lower()
    assert "benchmark" in by_category["capability_truth"]["output"].lower()
    assert "benchmark" in by_category["runtime_state"]["output"].lower()

    # The only persistent paths touched by the run are beneath the disposable root.
    isolated_memory = (root / "state" / "memory" / "memory.json").resolve()
    assert isolated_memory.is_file()
    assert benchmark._is_relative_to(isolated_memory, root.resolve())
    assert not benchmark._is_relative_to(
        isolated_memory,
        (PROJECT_ROOT / "data").resolve(),
    )


def test_cycle_metadata_extractor_uses_the_stable_safe_fields():
    cycle = SimpleNamespace(
        intent=SimpleNamespace(intent_type=SimpleNamespace(value="conversation")),
        final_response="A bounded production answer.",
        reasoning=SimpleNamespace(metadata={
            "provider": "benchmark",
            "model": benchmark.BENCHMARK_MODEL,
            "response_class": "open_conversation",
            "response_engine": "conversation_generation",
            "escalation_reason": "response_risk_open_conversation",
            "shadow_enabled": False,
            "shadow_model": None,
            "shadow_ms": None,
            "provider_attempts": [{"provider": "benchmark", "status": "success", "error": "secret"}],
            "provider_attempt_timings": [{
                "provider": "benchmark",
                "status": "success",
                "call_ms": 1.25,
                "elapsed_ms": 1.5,
                "private": "discarded",
            }],
            "conversation_lane": {
                "lane": "conversation",
                "latency_target_ms": 3500,
                "allow_model_revision": False,
                "rationale": "discarded",
            },
        }),
        reflection=SimpleNamespace(metadata={"mode": "local_character_audit"}),
        metadata={
            "local_mind": {
                "response_class": "open_conversation",
                "classification_ms": 0.2,
                "local_composer_ms": 0.0,
                "local_audit_ms": 0.0,
                "canonical_plan": {"private_semantics": "discarded"},
                "plan": {
                    "act": "escalate",
                    "local": False,
                    "target_length": "brief",
                    "slots": {"private_semantics": "discarded"},
                },
            },
            "timings": {"cognition_total_ms": 3.0},
        },
    )
    pipeline = SimpleNamespace(
        success=True,
        metadata={"pipeline_values": {"cognitive_cycle": cycle}},
    )

    metrics = benchmark.extract_cycle_metrics(
        pipeline,
        pre_tts_pipeline_total_ms=4.5,
        provider_call_count=1,
        character_mind_calls=1,
        character_mind_ms=0.5,
    )

    assert metrics["response_class"] == "open_conversation"
    assert metrics["execution_route"] == benchmark.ROUTE_PROVIDER
    assert metrics["response_engine"] == "conversation_generation"
    assert metrics["provider_attempts"] == [{"provider": "benchmark", "status": "success"}]
    assert metrics["provider_attempt_timings"] == [{
        "provider": "benchmark",
        "status": "success",
        "call_ms": 1.25,
        "elapsed_ms": 1.5,
    }]
    assert metrics["character_mind"]["plan"] == {
        "act": "escalate",
        "local": False,
        "target_length": "brief",
    }
    serialized = json.dumps(metrics)
    assert "private_semantics" not in serialized
    assert "secret" not in serialized


def test_cycle_metadata_extractor_marks_authoritative_system_bypass_as_unmeasured():
    cycle = SimpleNamespace(
        intent=SimpleNamespace(intent_type=SimpleNamespace(value="self_query")),
        final_response="A grounded runtime response.",
        reasoning=SimpleNamespace(
            reasoning_type="deterministic_system_action",
            metadata={
                "provider": "local/system",
                "model": "n/a",
                "generation_purpose": "runtime_introspection",
                "llm_skipped": True,
            },
        ),
        reflection=SimpleNamespace(metadata={"mode": "deterministic_system_action"}),
        metadata={"handled_by": "mary_system", "system_action": "self_query"},
    )
    pipeline = SimpleNamespace(
        success=True,
        metadata={"pipeline_values": {"cognitive_cycle": cycle}},
    )

    metrics = benchmark.extract_cycle_metrics(
        pipeline,
        pre_tts_pipeline_total_ms=1.0,
        provider_call_count=0,
        character_mind_calls=0,
        character_mind_ms=0.0,
    )

    assert metrics["execution_route"] == benchmark.ROUTE_DETERMINISTIC_SYSTEM
    assert metrics["response_class"] is None
    assert metrics["response_classification"] == {
        "value": None,
        "source": "bypassed_by_authoritative_system_handler",
    }
    assert metrics["response_engine"] == "runtime_introspection"
    assert metrics["provider"] == "local/system"
    assert metrics["character_mind"] == {
        "calls": 0,
        "handled": False,
        "decision": "not_reached",
        "plan": {},
        "conversation_lane": {},
    }
    assert metrics["character_mind_ms"] is None
    assert metrics["classification_ms"] is None
    assert metrics["local_composer_ms"] is None
    assert metrics["local_audit_ms"] is None


def test_report_writer_is_bounded_runtime_reports_only_and_no_clobber(tmp_path):
    report_root = tmp_path / "runtime_reports"
    report = {"schema_version": 1, "summary": {"passed": True}}

    target = benchmark.write_report_no_clobber(
        report,
        "nested/result.json",
        report_root=report_root,
    )
    assert target == (report_root / "nested" / "result.json").resolve()
    assert json.loads(target.read_text(encoding="utf-8")) == report

    with pytest.raises(FileExistsError):
        benchmark.write_report_no_clobber(report, target, report_root=report_root)
    assert json.loads(target.read_text(encoding="utf-8")) == report

    with pytest.raises(ValueError, match="runtime_reports"):
        benchmark.write_report_no_clobber(
            report,
            tmp_path / "outside.json",
            report_root=report_root,
        )
    with pytest.raises(ValueError, match=".json"):
        benchmark.write_report_no_clobber(report, "result.txt", report_root=report_root)
    with pytest.raises(ValueError, match="2 MB"):
        benchmark.write_report_no_clobber(
            {"oversized": "x" * 2_000_001},
            "oversized.json",
            report_root=report_root,
        )


def test_windows_launcher_restores_environment_and_guards_recursive_cleanup():
    launcher = (
        PROJECT_ROOT / "scripts" / "benchmark_production_hybrid_dialogue_windows.ps1"
    ).read_text(encoding="utf-8")

    assert "scripts.benchmark_production_hybrid_dialogue" in launcher
    assert "MARY_DATA_DIR" in launcher
    assert "MARY_ENV_FILE" in launcher
    assert 'MARY_LLM_PROVIDER" "benchmark"' in launcher
    assert 'MARY_RESERVOIR_STORAGE" "memory"' in launcher
    assert 'MARY_QWEN_SHADOW_ENABLED" "0"' in launcher
    assert "PreviousEnvironment" in launcher
    assert "SetEnvironmentVariable" in launcher
    assert "GetDirectoryName($ResolvedIsolationRoot)" in launcher
    assert "maryv2-production-hybrid-" in launcher
    assert "ReparsePoint" in launcher
    assert "Remove-Item -LiteralPath $ResolvedIsolationRoot -Recurse -Force" in launcher
    assert "--overwrite" not in launcher.lower()
    assert "ollama run" not in launcher.lower()
    assert "openai" not in launcher.lower().replace("openai_api_key", "")
