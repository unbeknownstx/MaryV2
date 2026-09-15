from pathlib import Path


def test_windows_node_task_uses_canonical_home_node_launcher():
    root = Path(__file__).resolve().parents[2]
    install = (root / "scripts" / "install_windows_node_task.ps1").read_text(encoding="utf-8")
    launcher = (root / "scripts" / "launch_home_node_windows.ps1").read_text(encoding="utf-8")
    legacy_launcher = (root / "scripts" / "launch_windows_node.ps1").read_text(encoding="utf-8")
    legacy_python = (root / "scripts" / "run_windows_node.py").read_text(encoding="utf-8")
    migration = (root / "scripts" / "migrate_windows_node_trust.ps1").read_text(encoding="utf-8")

    assert "MaryV2 Home Capability Node" in install
    assert "MaryV2 Windows Capability Node" in install
    assert "launch_home_node_windows.ps1" in install
    assert "New-ScheduledTaskTrigger -AtLogOn" in install
    assert "WindowStyle Hidden" in install
    assert "scripts.run_home_node" in launcher
    assert "windows-rx580-4gb" in launcher
    assert "OLLAMA_GPU_OVERHEAD" in launcher
    assert "OLLAMA_MAX_LOADED_MODELS" in launcher
    assert "launch_home_node_windows.ps1" in legacy_launcher
    assert "run_home_node_main" in legacy_python
    assert 'surface="windows_node"' not in legacy_python
    assert "run_desktop" not in install
    assert "MARY_NODE_ENROLLMENT_GRANT" not in install
    assert "MARY_NODE_DEVICE_CREDENTIAL" not in install
    assert "Read-Host" in migration
    assert "-AsSecureString" in migration
    assert "scripts.run_home_node" in migration
    assert "--enroll-only" in migration
    assert "SetEnvironmentVariable" not in migration
