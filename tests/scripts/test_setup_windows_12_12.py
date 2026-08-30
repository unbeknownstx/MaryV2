from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def test_canonical_setup_preserves_character_foundation_and_current_gates():
    setup = (ROOT / "scripts/setup_windows.ps1").read_text(encoding="utf-8")
    assert "MARYV2" in setup and "WINDOWS" in setup and "VERIFICATION" in setup
    assert "scripts.verify_character_runtime_12_12" in setup
    assert "scripts.verify_natural_conversation_12_12_2" in setup
    assert "scripts.verify_maryv2_convergence" in setup
    assert "scripts.verify_repository_structure" in setup
    assert '"-m","pytest","-q"' in setup


def test_setup_does_not_contain_old_clean_project_migration_workflow():
    setup = (ROOT / "scripts/setup_windows.ps1").read_text(encoding="utf-8")
    assert "MIGRATE_PRIVATE_STATE" not in setup
    assert "CLEAN_PROJECT" not in setup
