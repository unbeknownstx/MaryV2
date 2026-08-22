from pathlib import Path


def test_first_boot_windows_preserves_private_state_and_runs_release_gate():
    root = Path(__file__).resolve().parents[2]
    text = (root / "scripts" / "first_boot_windows.ps1").read_text(encoding="utf-8")

    assert "run_release_verification --offline" in text
    assert "& $Python -m pytest -q" in text
    assert "Remove-Item .env" not in text
    assert "Remove-Item data" not in text
    assert "never deletes or replaces your existing data/ or .env" in text


def test_first_boot_windows_keeps_external_skills_optional():
    root = Path(__file__).resolve().parents[2]
    text = (root / "scripts" / "first_boot_windows.ps1").read_text(encoding="utf-8")
    assert "External skills (Twitch/OBS/Vision/Ren'Py) remain disabled by default." in text
