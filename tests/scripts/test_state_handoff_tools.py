from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile

from scripts.backup_state import create_backup
from scripts.verify_state_integrity import inspect_state


def test_state_integrity_accepts_fresh_missing_data_directory(tmp_path):
    report = inspect_state(tmp_path / "missing")
    assert report["exists"] is False
    assert report["healthy"] is True
    assert report["current_files"] == 0


def test_state_integrity_reports_corrupt_current_file_and_valid_backup(tmp_path):
    root = tmp_path / "data"
    target = root / "relationship" / "relationship.json"
    target.parent.mkdir(parents=True)
    target.write_text("{broken", encoding="utf-8")
    target.with_name("relationship.json.bak1").write_text(
        json.dumps({"relationship": {}}),
        encoding="utf-8",
    )

    report = inspect_state(root)
    assert report["healthy"] is False
    assert len(report["invalid_files"]) == 1
    assert report["invalid_files"][0]["recoverable"] is True
    assert report["invalid_files"][0]["valid_backup"].endswith("relationship.json.bak1")


def test_state_backup_contains_data_and_manifest_but_never_env(tmp_path):
    data = tmp_path / "data"
    (data / "goals").mkdir(parents=True)
    (data / "goals" / "curiosities.json").write_text(
        json.dumps({"curiosities": [{"id": "c1"}]}),
        encoding="utf-8",
    )
    (data / ".env").write_text("OPENAI_API_KEY=do-not-copy\n", encoding="utf-8")

    archive = create_backup(
        data,
        tmp_path / "backups",
        timestamp=datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
    )
    assert archive is not None
    assert archive.name == "MaryV2-state-20260821-120000Z.zip"

    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        assert "data/goals/curiosities.json" in names
        assert "MARYV2_STATE_BACKUP_MANIFEST.json" in names
        assert not any(Path(name).name.startswith(".env") for name in names)
        manifest = json.loads(bundle.read("MARYV2_STATE_BACKUP_MANIFEST.json"))
        assert manifest["contains_environment_secrets"] is False
        assert manifest["file_count"] == 1


def test_state_backup_refuses_destination_inside_data_root(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "state.json").write_text("{}", encoding="utf-8")

    try:
        create_backup(data, data / "backups")
    except ValueError as exc:
        assert "outside Mary's data directory" in str(exc)
    else:
        raise AssertionError("backup destination inside data root should be rejected")


def test_preflight_ollama_status_detects_configured_model():
    from scripts.final_preflight import _ollama_status

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"models": [{"name": "qwen3:4b-instruct"}]}).encode("utf-8")

    def opener(request, timeout):
        assert timeout <= 2.0
        return Response()

    status = _ollama_status(
        "http://localhost:11434",
        "qwen3:4b-instruct",
        opener=opener,
    )
    assert status["reachable"] is True
    assert status["model_present"] is True
    assert status["models"] == 1


def test_state_backup_round_trips_through_safe_restore(tmp_path):
    from scripts.restore_state import restore_backup

    source = tmp_path / "source_data"
    (source / "relationship").mkdir(parents=True)
    original = {"relationship": {"stage": "established"}}
    (source / "relationship" / "relationship.json").write_text(
        json.dumps(original), encoding="utf-8"
    )
    archive = create_backup(
        source,
        tmp_path / "backups",
        timestamp=datetime(2026, 8, 21, 13, 0, tzinfo=timezone.utc),
    )
    assert archive is not None

    target = tmp_path / "restored_data"
    dry = restore_backup(archive, target, apply=False)
    assert dry["applied"] is False
    assert not target.exists()

    applied = restore_backup(archive, target, apply=True)
    assert applied["applied"] is True
    restored = json.loads((target / "relationship" / "relationship.json").read_text())
    assert restored == original


def test_state_restore_refuses_nonempty_target(tmp_path):
    from scripts.restore_state import restore_backup

    source = tmp_path / "source_data"
    source.mkdir()
    (source / "state.json").write_text("{}", encoding="utf-8")
    archive = create_backup(source, tmp_path / "backups")
    assert archive is not None

    target = tmp_path / "target"
    target.mkdir()
    (target / "existing.json").write_text("{}", encoding="utf-8")
    try:
        restore_backup(archive, target, apply=True)
    except FileExistsError as exc:
        assert "will not overwrite" in str(exc)
    else:
        raise AssertionError("restore must refuse a non-empty target")


def test_state_restore_rejects_tampered_backup_hash(tmp_path):
    from scripts.restore_state import inspect_backup

    archive = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("data/state.json", "{}")
        bundle.writestr(
            "MARYV2_STATE_BACKUP_MANIFEST.json",
            json.dumps({
                "format": "maryv2-state-backup-v1",
                "files": [{"path": "data/state.json", "size": 2, "sha256": "0" * 64}],
            }),
        )
    try:
        inspect_backup(archive)
    except ValueError as exc:
        assert "hash mismatch" in str(exc).lower()
    else:
        raise AssertionError("tampered backup should fail validation")
