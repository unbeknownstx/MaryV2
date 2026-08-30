from pathlib import Path

from scripts.verify_repository_structure import violations


def test_current_repository_passes_structure_gate():
    root = Path(__file__).resolve().parents[2]
    assert violations(root) == []


def test_structure_gate_rejects_repo_local_data(tmp_path):
    for rel in (
        "README.md", "MARY_ROOT.md", "AGENTS.md", "mary", "tests", "scripts",
        "docs/architecture/SYSTEM_REGISTRY.md", "character_sources/active",
        "character_sources/drafts", "projects/unbeknownst",
    ):
        path = tmp_path / rel
        if Path(rel).suffix:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text("x", encoding="utf-8")
        else:
            path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir()
    assert any("forbidden active root directory: data" in item for item in violations(tmp_path))
