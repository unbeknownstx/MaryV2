from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def test_canonical_setup_is_12_12_and_references_real_tests():
    setup = (ROOT / "SETUP_WINDOWS.ps1").read_text(encoding="utf-8")
    assert "MARYV2 12.12.2 WINDOWS SETUP + VERIFICATION" in setup
    referenced = sorted(set(re.findall(r"tests[/\\][A-Za-z0-9_./\\-]+?\.py", setup)))
    assert referenced
    missing = [rel for rel in referenced if not (ROOT / rel.replace("\\", "/")).exists()]
    assert missing == []


def test_setup_does_not_contain_old_clean_project_migration_workflow():
    setup = (ROOT / "SETUP_WINDOWS.ps1").read_text(encoding="utf-8")
    assert "MIGRATE_PRIVATE_STATE" not in setup
    assert "CLEAN_PROJECT" not in setup
