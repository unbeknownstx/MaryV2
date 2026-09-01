from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile

from scripts.backup_state import create_backup
from scripts.verify_state_integrity import inspect_state
from mary.runtime.backup import (
    BACKUP_FORMAT,
    durable_fingerprint,
    verify_reconstruction,
)


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
    assert archive.name.startswith("MaryV2-state-20260821-120000Z-")
    assert archive.suffix == ".zip"

    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        assert "data/goals/curiosities.json" in names
        assert "MARYV2_STATE_BACKUP_MANIFEST.json" in names
        assert not any(Path(name).name.startswith(".env") for name in names)
        manifest = json.loads(bundle.read("MARYV2_STATE_BACKUP_MANIFEST.json"))
        assert manifest["contains_environment_secrets"] is False
        assert manifest["file_count"] == 1
        assert manifest["format"] == BACKUP_FORMAT
        assert len(manifest["durable_state_fingerprint"]) == 64
        assert "node_sessions" in manifest["excluded_state"]


def test_state_backup_refuses_destination_inside_data_root(tmp_path):
    data = tmp_path / "data"
    target = data / "memory" / "memory.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")

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
    state = source / "memory" / "memory.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}", encoding="utf-8")
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


def test_state_backup_excludes_ephemeral_unknown_and_credential_files(tmp_path):
    data = tmp_path / "data"
    durable = data / "runtime" / "node_enrollment.json"
    durable.parent.mkdir(parents=True)
    durable.write_text(
        json.dumps({
            "version": 2,
            "grants": [{"grant_id": "old-grant", "digest": "a" * 64}],
            "audit": [{"event": "issued", "grant_id": "old-grant"}],
            "session_generations": {"device-a": 7},
            "trusted_devices": [{
                "node_id": "device-a",
                "credential_digest": "b" * 64,
                "enrolled_at": "2026-08-31T00:00:00+00:00",
            }],
        }),
        encoding="utf-8",
    )
    (data / "runtime" / "node_sessions.json").write_text("{}", encoding="utf-8")
    (data / "runtime" / "provider_token.json").write_text(
        json.dumps({"access_token": "must-not-copy"}),
        encoding="utf-8",
    )
    reservoir = data / "reservoir" / "mary_reservoir.sqlite3"
    reservoir.parent.mkdir(parents=True)
    reservoir.write_bytes(b"rebuildable")

    archive = create_backup(data, tmp_path / "backups")
    assert archive is not None
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
    assert "data/runtime/node_enrollment.json" in names
    assert "data/runtime/node_sessions.json" not in names
    assert "data/runtime/provider_token.json" not in names
    assert "data/reservoir/mary_reservoir.sqlite3" not in names
    with zipfile.ZipFile(archive) as bundle:
        enrollment = json.loads(bundle.read("data/runtime/node_enrollment.json"))
    assert enrollment["grants"] == []
    assert enrollment["audit"] == []
    assert enrollment["session_generations"] == {}
    assert enrollment["trusted_devices"][0]["node_id"] == "device-a"


def test_engagement_projection_excludes_process_local_plan_from_fingerprint(
    tmp_path,
):
    first = tmp_path / "first"
    second = tmp_path / "second"
    durable = {
        "schema_version": 1,
        "mode": "adaptive",
        "active_session": {
            "mode": "engaged",
            "turns_remaining": 3,
            "thread_id": "thread-a",
            "started_at": "2026-08-31T00:00:00+00:00",
        },
        "stats": {"engaged_turns": 8, "deep_turns": 2},
    }
    for root, last_plan, asked in (
        (first, {"target_length": "brief", "rationale": "first"}, True),
        (second, {"target_length": "long", "rationale": "second"}, False),
    ):
        state = root / "runtime" / "conversation_engagement.json"
        state.parent.mkdir(parents=True)
        state.write_text(
            json.dumps({
                **durable,
                "last_plan": last_plan,
                "last_question_asked": asked,
            }),
            encoding="utf-8",
        )

    first_fingerprint = durable_fingerprint(first)
    second_fingerprint = durable_fingerprint(second)
    assert (
        first_fingerprint["durable_state_fingerprint"]
        == second_fingerprint["durable_state_fingerprint"]
    )
    assert first_fingerprint["projection_version"] == 2

    archive = create_backup(first, tmp_path / "backups")
    assert archive is not None
    with zipfile.ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read("MARYV2_STATE_BACKUP_MANIFEST.json"))
        engagement = json.loads(
            bundle.read("data/runtime/conversation_engagement.json")
        )
    record = next(
        item
        for item in manifest["files"]
        if item["path"] == "data/runtime/conversation_engagement.json"
    )
    assert manifest["projection_version"] == 2
    assert record["sanitized_for_recovery"] is True
    assert engagement["last_plan"] == {}
    assert engagement["last_question_asked"] is False
    assert engagement["mode"] == durable["mode"]
    assert engagement["active_session"] == durable["active_session"]
    assert engagement["stats"] == durable["stats"]


def test_reconstruction_verifies_pre_projection_v2_manifest(tmp_path):
    state = tmp_path / "data" / "runtime" / "conversation_engagement.json"
    state.parent.mkdir(parents=True)
    state.write_text(
        json.dumps({
            "schema_version": 1,
            "mode": "adaptive",
            "active_session": {},
            "last_plan": {"target_length": "brief"},
            "last_question_asked": True,
            "stats": {"engaged_turns": 1, "deep_turns": 0},
        }),
        encoding="utf-8",
    )
    old_manifest = durable_fingerprint(
        tmp_path / "data",
        projection_version=1,
    )
    assert "projection_version" not in old_manifest
    verified = verify_reconstruction(
        tmp_path / "data",
        old_manifest,
        sourcebook=None,
    )
    assert verified["reconstruction_verified"] is True


def test_state_backup_refuses_sensitive_field_without_touching_source(tmp_path):
    data = tmp_path / "data"
    state = data / "relationship" / "relationship.json"
    state.parent.mkdir(parents=True)
    original = json.dumps({"relationship": {}, "access_token": "must-not-copy"})
    state.write_text(original, encoding="utf-8")

    try:
        create_backup(data, tmp_path / "backups")
    except ValueError as exc:
        assert "credential-like field" in str(exc)
    else:
        raise AssertionError("credential-like fields must fail closed")

    assert state.read_text(encoding="utf-8") == original
    assert not list((tmp_path / "backups").glob("*")) if (tmp_path / "backups").exists() else True


def test_state_backup_fingerprint_is_deterministic_for_same_state(tmp_path):
    data = tmp_path / "data"
    state = data / "memory" / "memory.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"memories": [{"id": "m1"}]}), encoding="utf-8")

    first = create_backup(
        data,
        tmp_path / "first",
        timestamp=datetime(2026, 8, 21, 13, 0, tzinfo=timezone.utc),
    )
    second = create_backup(
        data,
        tmp_path / "second",
        timestamp=datetime(2026, 8, 22, 13, 0, tzinfo=timezone.utc),
    )
    assert first is not None and second is not None
    with zipfile.ZipFile(first) as bundle:
        first_manifest = json.loads(bundle.read("MARYV2_STATE_BACKUP_MANIFEST.json"))
    with zipfile.ZipFile(second) as bundle:
        second_manifest = json.loads(bundle.read("MARYV2_STATE_BACKUP_MANIFEST.json"))
    assert first_manifest["created_at_utc"] != second_manifest["created_at_utc"]
    assert (
        first_manifest["durable_state_fingerprint"]
        == second_manifest["durable_state_fingerprint"]
    )


def test_state_backup_fails_closed_for_unclassified_durable_json(tmp_path):
    data = tmp_path / "data"
    unknown = data / "relationship" / "shadow_authority.json"
    unknown.parent.mkdir(parents=True)
    unknown.write_text("{}", encoding="utf-8")

    try:
        create_backup(data, tmp_path / "backups")
    except ValueError as exc:
        assert "Unclassified durable-state JSON" in str(exc)
    else:
        raise AssertionError("unknown durable files must be classified before backup")
