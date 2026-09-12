from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_home_node_is_cross_platform_and_reuses_bounded_agent():
    source = _text("scripts/run_home_node.py")
    assert "DesktopCapabilityNodeAgent" in source
    assert "headless_node_capabilities" in source
    assert 'surface="home_node"' in source
    assert "gateway_from_environment" in source


def test_home_node_has_no_arbitrary_shell_executor():
    source = _text("scripts/run_home_node.py") + _text("mary/distributed/benchmarking.py")
    assert "subprocess" not in source
    assert "shell=True" not in source
    assert "os.system" not in source
    assert "Popen(" not in source


def test_benchmark_profile_stays_outside_repository_by_default():
    source = _text("scripts/benchmark_home_node.py")
    assert 'Path.home() / ".maryv2"' in source
    assert "MARY_RUNTIME_DIR" in source
    assert "node_benchmark_13_11.json" in source


def test_current_hardware_acceleration_is_benchmark_first():
    profile = _text("mary/distributed/resource_profile.py")
    assert "vulkan_available" in profile
    assert "metal_available" in profile
    assert "benchmark_vulkan_for_llama_whisper_and_preprocessing" in profile
