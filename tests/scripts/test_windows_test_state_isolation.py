from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_full_suite_uses_bounded_system_temp_state_and_restores_environment():
    script = _read("scripts/test_full.ps1")

    assert "[System.IO.Path]::GetTempPath()" in script
    assert "maryv2-full-tests-" in script
    assert "[guid]::NewGuid()" in script
    assert '$env:MARY_DATA_DIR = $FullTestDataDirectory' in script
    assert '$FullTestEnvironmentFile = Join-Path $FullTestRoot "no-live-config"' in script
    assert 'Test-Path -LiteralPath $FullTestEnvironmentFile' in script
    assert '$env:MARY_ENV_FILE = $FullTestEnvironmentFile' in script
    assert '$env:MARY_RESERVOIR_STORAGE = "memory"' in script
    assert '$env:PYTEST_DEBUG_TEMPROOT = $FullTestPytestTempRoot' in script
    assert '$env:PYTEST_ADDOPTS = "-p no:cacheprovider"' in script
    assert "& $Python -m pytest -q" in script

    for previous, environment_name in (
        ("PreviousMaryDataDirectory", "MARY_DATA_DIR"),
        ("PreviousMaryEnvironmentFile", "MARY_ENV_FILE"),
        ("PreviousMaryReservoirStorage", "MARY_RESERVOIR_STORAGE"),
        ("PreviousPytestTempRoot", "PYTEST_DEBUG_TEMPROOT"),
        ("PreviousPytestAddopts", "PYTEST_ADDOPTS"),
    ):
        assert f"${previous} = $env:{environment_name}" in script
        assert f"Remove-Item Env:{environment_name}" in script
        assert f"$env:{environment_name} = ${previous}" in script

    cleanup = script.index(
        "Remove-Item -LiteralPath $ResolvedFullTestRoot -Recurse -Force"
    )
    assert script.index("$env:MARY_DATA_DIR = $PreviousMaryDataDirectory") < cleanup
    assert script.index("$env:MARY_ENV_FILE = $PreviousMaryEnvironmentFile") < cleanup
    assert script.index("$env:MARY_RESERVOIR_STORAGE = $PreviousMaryReservoirStorage") < cleanup
    assert script.index("$env:PYTEST_DEBUG_TEMPROOT = $PreviousPytestTempRoot") < cleanup
    assert script.index("$env:PYTEST_ADDOPTS = $PreviousPytestAddopts") < cleanup
    assert "ResolvedFullTestParent.Equals($ResolvedSystemTempRoot" in script
    assert 'FullTestLeaf.StartsWith("maryv2-full-tests-"' in script
    assert "[System.IO.FileAttributes]::ReparsePoint" in script
    assert "Remove-Item -LiteralPath $ResolvedFullTestRoot -Recurse -Force" in script


def test_setup_wraps_each_test_or_verifier_except_explicit_read_only_integrity():
    setup = _read("scripts/setup_windows.ps1")

    assert "function Invoke-IsolatedPythonStage" in setup
    assert "[System.IO.Path]::GetTempPath()" in setup
    assert '"maryv2-setup-$SafeStageName-"' in setup
    assert '$env:MARY_DATA_DIR = $IsolatedDataDirectory' in setup
    assert '$IsolatedEnvironmentFile = Join-Path $IsolationRoot "no-live-config"' in setup
    assert 'Test-Path -LiteralPath $IsolatedEnvironmentFile' in setup
    assert '$env:MARY_ENV_FILE = $IsolatedEnvironmentFile' in setup
    assert '$env:MARY_RESERVOIR_STORAGE = "memory"' in setup
    assert '$env:PYTEST_DEBUG_TEMPROOT = $IsolatedPytestTempRoot' in setup
    assert '$env:PYTEST_ADDOPTS = "-p no:cacheprovider"' in setup
    assert "Remove-BoundedTemporaryDirectory" in setup
    assert "ResolvedTargetParent.Equals($ResolvedSystemTempRoot" in setup
    assert "TargetLeaf.StartsWith($ExpectedLeafPrefix" in setup
    assert "[System.IO.FileAttributes]::ReparsePoint" in setup
    assert "Remove-Item -LiteralPath $ResolvedTarget -Recurse -Force" in setup

    helper_start = setup.index("function Invoke-IsolatedPythonStage")
    helper_end = setup.index('Write-Host "===', helper_start)
    helper = setup[helper_start:helper_end]
    cleanup = helper.index("Remove-BoundedTemporaryDirectory")
    assert helper.index("$env:MARY_DATA_DIR = $PreviousMaryDataDirectory") < cleanup
    assert helper.index("$env:MARY_ENV_FILE = $PreviousMaryEnvironmentFile") < cleanup
    assert helper.index("$env:MARY_RESERVOIR_STORAGE = $PreviousMaryReservoirStorage") < cleanup
    assert helper.index("$env:PYTEST_DEBUG_TEMPROOT = $PreviousPytestTempRoot") < cleanup
    assert helper.index("$env:PYTEST_ADDOPTS = $PreviousPytestAddopts") < cleanup

    expected_isolated_stages = {
        "step-5-structure",
        "step-5-convergence",
        "step-6-character-runtime",
        "step-6-natural-conversation",
        "step-7-full-suite",
        "step-8-release-gate",
        "step-9-standalone",
    }
    actual_isolated_stages = set(
        re.findall(r'Invoke-IsolatedPythonStage -StageName "([^"]+)"', setup)
    )
    assert actual_isolated_stages == expected_isolated_stages

    direct_test_or_verifier_calls = re.findall(
        r"(?m)^\s*& \$Python -m (pytest|scripts\.verify_[A-Za-z0-9_]+)", setup
    )
    assert direct_test_or_verifier_calls == []
    assert 'StageName "step-8-release-gate"' in setup
    assert 'StageName "step-9-standalone"' in setup
    assert "RepoLocalDataDirectory" not in setup


def test_fast_check_isolates_pytest_and_verifiers_without_loading_live_config():
    script = _read("scripts/test_fast.ps1")

    assert "[System.IO.Path]::GetTempPath()" in script
    assert "maryv2-fast-check-" in script
    assert "[guid]::NewGuid()" in script
    assert '$FastCheckDataDirectory = Join-Path $FastCheckRoot "state"' in script
    assert '$FastCheckPytestTempRoot = Join-Path $FastCheckRoot "pytest"' in script
    assert '$FastCheckEnvironmentFile = Join-Path $FastCheckRoot "no-live-config"' in script
    assert 'Test-Path -LiteralPath $FastCheckEnvironmentFile' in script
    assert '$env:MARY_DATA_DIR = $FastCheckDataDirectory' in script
    assert '$env:MARY_ENV_FILE = $FastCheckEnvironmentFile' in script
    assert '$env:MARY_RESERVOIR_STORAGE = "memory"' in script
    assert '$env:PYTEST_DEBUG_TEMPROOT = $FastCheckPytestTempRoot' in script
    assert '$env:PYTEST_ADDOPTS = "-p no:cacheprovider"' in script

    for previous, environment_name in (
        ("PreviousMaryDataDirectory", "MARY_DATA_DIR"),
        ("PreviousMaryEnvironmentFile", "MARY_ENV_FILE"),
        ("PreviousMaryReservoirStorage", "MARY_RESERVOIR_STORAGE"),
        ("PreviousPytestTempRoot", "PYTEST_DEBUG_TEMPROOT"),
        ("PreviousPytestAddopts", "PYTEST_ADDOPTS"),
    ):
        assert f"${previous} = $env:{environment_name}" in script
        assert f"Remove-Item Env:{environment_name}" in script
        assert f"$env:{environment_name} = ${previous}" in script

    cleanup = script.index(
        "Remove-Item -LiteralPath $ResolvedFastCheckRoot -Recurse -Force"
    )
    assert script.index("$env:MARY_DATA_DIR = $PreviousMaryDataDirectory") < cleanup
    assert script.index("$env:MARY_ENV_FILE = $PreviousMaryEnvironmentFile") < cleanup
    assert script.index("$env:MARY_RESERVOIR_STORAGE = $PreviousMaryReservoirStorage") < cleanup
    assert script.index("$env:PYTEST_DEBUG_TEMPROOT = $PreviousPytestTempRoot") < cleanup
    assert script.index("$env:PYTEST_ADDOPTS = $PreviousPytestAddopts") < cleanup
    assert "ResolvedFastCheckParent.Equals($ResolvedSystemTempRoot" in script
    assert 'FastCheckLeaf.StartsWith("maryv2-fast-check-"' in script
    assert "[System.IO.FileAttributes]::ReparsePoint" in script


def test_release_gate_uses_fresh_isolated_state_and_restores_environment():
    script = _read("scripts/test_release.ps1")

    assert "[System.IO.Path]::GetTempPath()" in script
    assert "maryv2-release-gate-" in script
    assert "[guid]::NewGuid()" in script
    assert '$ReleaseGateEnvironmentFile = Join-Path $ReleaseGateRoot "no-live-config"' in script
    assert 'Test-Path -LiteralPath $ReleaseGateEnvironmentFile' in script
    assert '$env:MARY_DATA_DIR = $ReleaseGateDataDirectory' in script
    assert '$env:MARY_ENV_FILE = $ReleaseGateEnvironmentFile' in script
    assert '$env:MARY_RESERVOIR_STORAGE = "memory"' in script
    assert '$env:PYTEST_DEBUG_TEMPROOT = $ReleaseGatePytestTempRoot' in script
    assert '$env:PYTEST_ADDOPTS = "-p no:cacheprovider"' in script
    assert "-m scripts.run_release_verification --offline" in script

    for previous, environment_name in (
        ("PreviousMaryDataDirectory", "MARY_DATA_DIR"),
        ("PreviousMaryEnvironmentFile", "MARY_ENV_FILE"),
        ("PreviousMaryReservoirStorage", "MARY_RESERVOIR_STORAGE"),
        ("PreviousPytestTempRoot", "PYTEST_DEBUG_TEMPROOT"),
        ("PreviousPytestAddopts", "PYTEST_ADDOPTS"),
    ):
        assert f"${previous} = $env:{environment_name}" in script
        assert f"Remove-Item Env:{environment_name}" in script
        assert f"$env:{environment_name} = ${previous}" in script

    cleanup = script.index(
        "Remove-Item -LiteralPath $ResolvedReleaseGateRoot -Recurse -Force"
    )
    assert script.index("$env:MARY_DATA_DIR = $PreviousMaryDataDirectory") < cleanup
    assert script.index("$env:MARY_ENV_FILE = $PreviousMaryEnvironmentFile") < cleanup
    assert script.index("$env:MARY_RESERVOIR_STORAGE = $PreviousMaryReservoirStorage") < cleanup
    assert "ResolvedReleaseGateParent.Equals($ResolvedSystemTempRoot" in script
    assert 'ReleaseGateLeaf.StartsWith("maryv2-release-gate-"' in script
    assert "[System.IO.FileAttributes]::ReparsePoint" in script


def test_vscode_full_tests_runs_the_canonical_isolated_script():
    tasks = json.loads(_read(".vscode/tasks.json"))["tasks"]
    full_task = next(task for task in tasks if task["label"] == "Mary: Full Tests")

    assert full_task["command"] == "powershell"
    assert full_task["args"] == [
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        ".\\scripts\\test_full.ps1",
    ]

    release_task = next(task for task in tasks if task["label"] == "Mary: Release Gate")
    assert release_task["command"] == "powershell"
    assert release_task["args"] == [
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        ".\\scripts\\test_release.ps1",
    ]
