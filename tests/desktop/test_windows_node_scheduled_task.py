from pathlib import Path


def test_windows_node_task_is_headless_and_uses_existing_launcher():
    root = Path(__file__).resolve().parents[2]
    install = (root / "scripts" / "install_windows_node_task.ps1").read_text(encoding="utf-8")
    launcher = (root / "scripts" / "launch_windows_node.ps1").read_text(encoding="utf-8")
    migration = (root / "scripts" / "migrate_windows_node_trust.ps1").read_text(encoding="utf-8")

    assert "MaryV2 Windows Capability Node" in install
    assert "launch_windows_node.ps1" in install
    assert "New-ScheduledTaskTrigger -AtLogOn" in install
    assert "WindowStyle Hidden" in install
    assert "run_windows_node" in launcher
    assert "ollama" in launcher.lower()
    assert "run_desktop" not in install
    assert "MARY_NODE_ENROLLMENT_GRANT" not in install
    assert "MARY_NODE_DEVICE_CREDENTIAL" not in install
    assert "Read-Host" in migration
    assert "-AsSecureString" in migration
    assert "--enroll-only" in migration
    assert "SetEnvironmentVariable" not in migration
