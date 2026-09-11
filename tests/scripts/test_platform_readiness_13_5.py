from __future__ import annotations

import json

from scripts import platform_readiness


def test_readiness_contract_is_safe_and_complete() -> None:
    report = platform_readiness.collect_readiness()

    assert report["schema"] == "maryv2.platform_readiness.v1"
    assert report["core_startup_requires_optional_host_extras"] is False
    assert report["shell_execution_surface_added"] is False
    assert all(report["repo_contracts"].values())
    assert "mcp" in report["optional_modules"]
    assert "ollama" in report["optional_executables"]
    assert "native_iphone_project" in report["surface"]


def test_strict_mode_ignores_missing_optional_tools(monkeypatch) -> None:
    monkeypatch.setattr(platform_readiness, "_module_available", lambda _name: False)
    monkeypatch.setattr(platform_readiness, "_which_any", lambda _names: None)

    report = platform_readiness.collect_readiness()
    assert platform_readiness._strict_failures(report) == []


def test_json_output_never_contains_environment_secret_values(monkeypatch, capsys) -> None:
    marker = "DO-NOT-PRINT-SECRET-MARKER"
    monkeypatch.setenv("OPENAI_API_KEY", marker)
    monkeypatch.setenv("MARY_MCP_LANGFLOW_URL", marker)

    assert platform_readiness.main(["--json", "--strict"]) == 0
    output = capsys.readouterr().out
    parsed = json.loads(output)

    assert marker not in output
    assert parsed["configuration"]["OPENAI_API_KEY"] is True
    assert parsed["configuration"]["MARY_MCP_LANGFLOW_URL"] is True


def test_human_output_does_not_expose_secret_values(monkeypatch, capsys) -> None:
    marker = "ANOTHER-SECRET-MARKER"
    monkeypatch.setenv("ELEVENLABS_API_KEY", marker)

    assert platform_readiness.main([]) == 0
    output = capsys.readouterr().out
    assert marker not in output
    assert "ELEVENLABS_API_KEY" in output
