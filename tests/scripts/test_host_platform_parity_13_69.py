from __future__ import annotations

from pathlib import Path

from mary.distributed.hardware_profiles import HARDWARE_PROFILES, SAFE_LOCAL_MODEL

ROOT = Path(__file__).resolve().parents[2]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_windows_and_macos_use_the_same_canonical_home_node() -> None:
    mac = _text("scripts/launch_home_node_macos.sh")
    windows = _text("scripts/launch_home_node_windows.ps1")
    assert "scripts.run_home_node" in mac
    assert "scripts.run_home_node" in windows
    assert "mac-apple-silicon" in mac
    assert "windows-rx580-4gb" in windows
    assert "node_benchmark_13_11.json" in mac
    assert "node_benchmark_13_11.json" in windows


def test_windows_and_macos_profiles_share_the_same_bounded_role_contract() -> None:
    required = {
        "MARY_OLLAMA_MODEL",
        "MARY_OLLAMA_CONVERSATION_MODEL",
        "MARY_OLLAMA_UTILITY_MODEL",
        "MARY_OLLAMA_NUM_CTX",
        "MARY_DEVICE_OLLAMA_MAX_CTX",
        "MARY_OLLAMA_KEEP_ALIVE",
        "MARY_OLLAMA_THINK",
        "MARY_LOCAL_FAST_MAX_TOKENS",
        "MARY_NODE_GPU_LABEL",
    }
    for name in ("windows-rx580-4gb", "mac-apple-silicon"):
        profile = HARDWARE_PROFILES[name]
        assert required <= set(profile)
        assert profile["MARY_OLLAMA_MODEL"] == SAFE_LOCAL_MODEL
        assert profile["MARY_OLLAMA_CONVERSATION_MODEL"] == SAFE_LOCAL_MODEL
        assert profile["MARY_OLLAMA_UTILITY_MODEL"] == SAFE_LOCAL_MODEL
        assert profile["MARY_OLLAMA_THINK"] == "false"


def test_windows_and_macos_setup_run_the_same_core_verification_stages() -> None:
    mac = _text("scripts/setup_macos.sh")
    windows = _text("scripts/setup_windows.ps1")
    for stage in (
        "scripts.verify_repository_structure",
        "scripts.verify_maryv2_convergence",
        "scripts.verify_character_runtime_12_12",
        "scripts.verify_natural_conversation_12_12_2",
        "scripts.run_release_verification",
        "scripts.verify_standalone_readiness",
        "pytest",
    ):
        assert stage in mac
        assert stage in windows
