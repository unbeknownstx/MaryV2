from pathlib import Path

from scripts.verify_repository_structure import REQUIRED, violations


def _create_required_paths(root: Path) -> None:
    for rel in REQUIRED:
        path = root / rel
        if Path(rel).suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x", encoding="utf-8")
        else:
            path.mkdir(parents=True, exist_ok=True)


def test_current_repository_passes_structure_gate():
    root = Path(__file__).resolve().parents[2]
    assert violations(root) == []


def test_structure_gate_rejects_repo_local_data(tmp_path):
    _create_required_paths(tmp_path)
    (tmp_path / "data").mkdir()
    assert any("forbidden active root directory: data" in item for item in violations(tmp_path))


def test_structure_gate_allows_only_reserved_user_upload_staging(tmp_path):
    _create_required_paths(tmp_path)
    upload = tmp_path / "attached_assets" / "task-material"
    upload.mkdir(parents=True)
    (upload / "specification.txt").write_text("preserved user input", encoding="utf-8")
    assert violations(tmp_path) == []


def test_structure_gate_still_rejects_runtime_roots_with_upload_staging(tmp_path):
    _create_required_paths(tmp_path)
    (tmp_path / "attached_assets").mkdir()
    for name in ("data", "payload", "upgrade_backups"):
        (tmp_path / name).mkdir()

    errors = violations(tmp_path)
    for name in ("data", "payload", "upgrade_backups"):
        assert f"forbidden active root directory: {name}" in errors


def test_structure_gate_rejects_generated_state_report_at_root(tmp_path):
    _create_required_paths(tmp_path)
    (tmp_path / "mary_state_local_inventory.json").write_text("{}", encoding="utf-8")
    assert any("generated Mary state report" in item for item in violations(tmp_path))
