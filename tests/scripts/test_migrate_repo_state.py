from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import stat

import pytest

import scripts.migrate_repo_state as migration
from scripts.migrate_repo_state import (
    inspect_migration,
    main,
    migrate_repo_state,
)


MOMENT = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def _write_state(root: Path, name: str = "state.json", value: str = "source") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps({"value": value}), encoding="utf-8")


def test_dry_run_reports_counts_and_conflicts_without_writing(tmp_path):
    source = tmp_path / "repo" / "data"
    destination = tmp_path / "canonical" / "data"
    _write_state(source, value="legacy")
    _write_state(destination, value="canonical")
    (source / ".env").write_text("OPENAI_API_KEY=never-copy", encoding="utf-8")

    report = migrate_repo_state(source, destination)

    assert report["applied"] is False
    assert report["source_file_count"] == 1
    assert report["destination_file_count"] == 1
    assert report["source_excluded_count"] == 1
    assert report["conflicts"] == ["state.json"]
    assert json.loads((destination / "state.json").read_text()) == {
        "value": "canonical"
    }
    assert (source / ".env").read_text() == "OPENAI_API_KEY=never-copy"
    assert not list(destination.parent.glob("data.before_repo_migration_*"))


def test_apply_to_empty_destination_copies_and_verifies_exact_files(tmp_path):
    repository = tmp_path / "repo"
    source = repository / "data"
    destination = tmp_path / "canonical" / "data"
    _write_state(source)
    (source / "nested").mkdir()
    (source / "nested" / "memory.bin").write_bytes(b"\x00mary\xff")

    report = migrate_repo_state(
        source,
        destination,
        apply=True,
        repository_root=repository,
        now=lambda: MOMENT,
    )

    assert report["applied"] is True
    assert report["installed_file_count"] == 2
    assert report["preserved_destination"] is None
    assert (destination / "state.json").read_bytes() == (
        source / "state.json"
    ).read_bytes()
    assert (destination / "nested" / "memory.bin").read_bytes() == b"\x00mary\xff"
    assert source.exists()


def test_apply_preserves_existing_destination_before_installing_source(tmp_path):
    repository = tmp_path / "repo"
    source = repository / "data"
    destination = tmp_path / "canonical" / "data"
    _write_state(source, value="legacy")
    _write_state(destination, value="canonical")
    (destination / "only-in-destination.json").write_text("{}", encoding="utf-8")

    report = migrate_repo_state(
        source,
        destination,
        apply=True,
        repository_root=repository,
        now=lambda: MOMENT,
    )

    preserved = report["preserved_destination"]
    assert preserved is not None
    assert preserved.name.startswith(
        "data.before_repo_migration_20260831-120000Z_"
    )
    assert report["preserved_destination"] == preserved
    assert json.loads((destination / "state.json").read_text()) == {
        "value": "legacy"
    }
    assert json.loads((preserved / "state.json").read_text()) == {
        "value": "canonical"
    }
    assert (preserved / "only-in-destination.json").exists()
    assert source.exists()


def test_wal_database_is_copied_as_consistent_integrity_checked_snapshot(tmp_path):
    repository = tmp_path / "repo"
    source = repository / "data"
    destination = tmp_path / "canonical" / "data"
    source.mkdir(parents=True)
    database = source / "mary_vectors.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA wal_autocheckpoint=0")
    connection.execute("CREATE TABLE memories (id INTEGER PRIMARY KEY, text TEXT)")
    connection.commit()
    connection.execute("INSERT INTO memories(text) VALUES (?)", ("continuity",))
    connection.commit()
    assert database.with_name(database.name + "-wal").exists()

    try:
        report = migrate_repo_state(
            source,
            destination,
            apply=True,
            repository_root=repository,
            now=lambda: MOMENT,
        )
    finally:
        connection.close()

    assert report["source_sqlite_sidecar_count"] >= 1
    assert report["installed_sqlite_count"] == 1
    copied = sqlite3.connect(destination / "mary_vectors.sqlite3")
    try:
        assert copied.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert copied.execute("SELECT text FROM memories").fetchall() == [
            ("continuity",)
        ]
    finally:
        copied.close()
    assert not (destination / "mary_vectors.sqlite3-wal").exists()


def test_failed_sqlite_verification_preserves_source_and_destination(tmp_path):
    repository = tmp_path / "repo"
    source = repository / "data"
    destination = tmp_path / "canonical" / "data"
    source.mkdir(parents=True)
    (source / "broken.sqlite3").write_bytes(b"not a sqlite database")
    _write_state(destination, value="canonical")

    with pytest.raises(ValueError, match="SQLite"):
        migrate_repo_state(
            source,
            destination,
            apply=True,
            repository_root=repository,
            now=lambda: MOMENT,
        )

    assert (source / "broken.sqlite3").read_bytes() == b"not a sqlite database"
    assert json.loads((destination / "state.json").read_text()) == {
        "value": "canonical"
    }
    assert not list(destination.parent.glob("data.before_repo_migration_*"))


def test_failed_final_verification_rolls_existing_destination_back(
    tmp_path,
    monkeypatch,
):
    repository = tmp_path / "repo"
    source = repository / "data"
    destination = tmp_path / "canonical" / "data"
    _write_state(source, value="legacy")
    _write_state(destination, value="canonical")
    def fail_final_verification(guard, name, expected):
        raise ValueError("simulated final verification failure")

    monkeypatch.setattr(
        migration,
        "_verify_installed_directory",
        fail_final_verification,
    )
    with pytest.raises(ValueError, match="simulated"):
        migrate_repo_state(
            source,
            destination,
            apply=True,
            repository_root=repository,
            now=lambda: MOMENT,
        )

    assert json.loads((destination / "state.json").read_text()) == {
        "value": "canonical"
    }
    assert json.loads((source / "state.json").read_text()) == {
        "value": "legacy"
    }
    assert not list(destination.parent.glob("data.before_repo_migration_*"))
    assert list(destination.parent.glob("data.failed_repo_migration_*"))


def test_source_mutation_after_inventory_aborts_before_destination_change(
    tmp_path,
    monkeypatch,
):
    repository = tmp_path / "repo"
    source = repository / "data"
    destination = tmp_path / "canonical" / "data"
    _write_state(source, value="legacy")
    _write_state(destination, value="canonical")
    original_copy = migration._copy_to_staging

    def mutate_then_copy(source_root, staging, records):
        (source_root / "state.json").write_text(
            json.dumps({"value": "changed"}),
            encoding="utf-8",
        )
        return original_copy(source_root, staging, records)

    monkeypatch.setattr(migration, "_copy_to_staging", mutate_then_copy)
    with pytest.raises(ValueError, match="changed after inspection"):
        migrate_repo_state(
            source,
            destination,
            apply=True,
            repository_root=repository,
            now=lambda: MOMENT,
        )

    assert json.loads((destination / "state.json").read_text()) == {
        "value": "canonical"
    }
    assert not list(destination.parent.glob("data.before_repo_migration_*"))


def test_symlinked_source_or_destination_root_is_rejected(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks are not supported")
    external_source = tmp_path / "external-source"
    external_destination = tmp_path / "external-destination"
    _write_state(external_source)
    _write_state(external_destination)
    source_link = tmp_path / "source-link"
    destination_link = tmp_path / "destination-link"
    try:
        source_link.symlink_to(external_source, target_is_directory=True)
        destination_link.symlink_to(external_destination, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not permitted")

    with pytest.raises(ValueError, match="symlink"):
        inspect_migration(source_link, tmp_path / "safe-destination")
    with pytest.raises(ValueError, match="symlink"):
        inspect_migration(external_source, destination_link)
    assert json.loads((external_destination / "state.json").read_text()) == {
        "value": "source"
    }


def test_posix_parent_swap_cannot_redirect_install_or_rollback(
    tmp_path,
    monkeypatch,
):
    if os.name == "nt" or not hasattr(os, "O_DIRECTORY"):
        pytest.skip("descriptor-relative replacement is POSIX-specific")
    trusted_parent = tmp_path / "canonical"
    stage_parent = tmp_path / "stage"
    external = tmp_path / "external"
    moved_parent = tmp_path / "canonical-moved"
    trusted_parent.mkdir()
    stage_parent.mkdir()
    external.mkdir()
    _write_state(trusted_parent / "data", value="canonical")
    _write_state(stage_parent / "data", value="legacy")
    real_replace = migration.os.replace
    swapped = False

    with (
        migration._ParentGuard(trusted_parent) as destination_guard,
        migration._ParentGuard(stage_parent) as staging_guard,
    ):
        destination_guard.replace_from(
            destination_guard,
            "data",
            "data.before",
        )

        def swap_parent_then_replace(source, destination, **kwargs):
            nonlocal swapped
            if not swapped and destination == "data":
                swapped = True
                trusted_parent.rename(moved_parent)
                trusted_parent.symlink_to(external, target_is_directory=True)
            return real_replace(source, destination, **kwargs)

        monkeypatch.setattr(migration.os, "replace", swap_parent_then_replace)
        destination_guard.replace_from(staging_guard, "data", "data")
        with pytest.raises(ValueError, match="symlink|changed"):
            migration._verify_installed_directory(
                destination_guard,
                "data",
                os.lstat(moved_parent / "data"),
            )
        destination_guard.replace_from(
            destination_guard,
            "data",
            "data.failed",
            validate_paths=False,
        )
        destination_guard.replace_from(
            destination_guard,
            "data.before",
            "data",
            validate_paths=False,
        )

    assert not any(external.iterdir())
    assert json.loads((moved_parent / "data" / "state.json").read_text()) == {
        "value": "canonical"
    }
    assert json.loads(
        (moved_parent / "data.failed" / "state.json").read_text()
    ) == {"value": "legacy"}
    assert stat.S_ISLNK(os.lstat(trusted_parent).st_mode)


def test_remove_source_requires_explicit_apply_and_legacy_repo_location(tmp_path):
    custom_source = tmp_path / "custom"
    destination = tmp_path / "canonical" / "data"
    _write_state(custom_source)

    with pytest.raises(ValueError, match="only"):
        migrate_repo_state(
            custom_source,
            destination,
            apply=True,
            remove_source=True,
            repository_root=tmp_path / "repo",
        )
    assert custom_source.exists()


def test_explicit_remove_source_runs_only_after_successful_install(tmp_path):
    repository = tmp_path / "repo"
    source = repository / "data"
    destination = tmp_path / "canonical" / "data"
    _write_state(source, value="legacy")

    report = migrate_repo_state(
        source,
        destination,
        apply=True,
        remove_source=True,
        repository_root=repository,
        now=lambda: MOMENT,
    )

    assert report["source_removed"] is True
    assert not source.exists()
    assert json.loads((destination / "state.json").read_text()) == {
        "value": "legacy"
    }


def test_source_cleanup_failure_is_separate_from_verified_migration(
    tmp_path,
    monkeypatch,
):
    repository = tmp_path / "repo"
    source = repository / "data"
    destination = tmp_path / "canonical" / "data"
    _write_state(source, value="legacy")
    real_rmtree = migration.shutil.rmtree

    def fail_retirement_cleanup(path, *args, **kwargs):
        if ".data.migration-removal_" in str(path):
            raise OSError("simulated cleanup failure")
        return real_rmtree(path, *args, **kwargs)

    fail_retirement_cleanup.avoids_symlink_attacks = getattr(
        real_rmtree,
        "avoids_symlink_attacks",
        False,
    )
    monkeypatch.setattr(migration.shutil, "rmtree", fail_retirement_cleanup)
    report = migrate_repo_state(
        source,
        destination,
        apply=True,
        remove_source=True,
        repository_root=repository,
        now=lambda: MOMENT,
    )

    assert report["applied"] is True
    assert report["source_removed"] is True
    assert report["source_cleanup_error"] == "OSError"
    assert report["source_cleanup_pending"].exists()
    assert not source.exists()
    assert json.loads((destination / "state.json").read_text()) == {
        "value": "legacy"
    }


def test_source_parent_swap_cannot_redirect_explicit_cleanup(
    tmp_path,
    monkeypatch,
):
    if os.name == "nt" or not hasattr(os, "O_DIRECTORY"):
        pytest.skip("descriptor-relative replacement is POSIX-specific")
    repository = tmp_path / "repo"
    source = repository / "data"
    moved_repository = tmp_path / "repo-moved"
    external_repository = tmp_path / "external-repo"
    _write_state(source, value="legacy")
    _write_state(external_repository / "data", value="external")
    parent_details = os.lstat(repository)
    source_details = os.lstat(source)
    real_replace = migration.os.replace
    swapped = False

    def swap_parent_then_replace(source_name, destination_name, **kwargs):
        nonlocal swapped
        if not swapped and str(destination_name).startswith(
            ".data.migration-removal_"
        ):
            swapped = True
            repository.rename(moved_repository)
            repository.symlink_to(external_repository, target_is_directory=True)
        return real_replace(source_name, destination_name, **kwargs)

    monkeypatch.setattr(migration.os, "replace", swap_parent_then_replace)
    removed, pending, error = migration._retire_source(
        source,
        MOMENT,
        expected_parent=(parent_details.st_dev, parent_details.st_ino),
        expected_source=(source_details.st_dev, source_details.st_ino),
    )

    assert removed is True
    assert pending is None
    assert error in {"ValueError", "OSError"}
    assert json.loads(
        (external_repository / "data" / "state.json").read_text()
    ) == {"value": "external"}
    quarantines = list(moved_repository.glob(".data.migration-removal_*"))
    assert len(quarantines) == 1
    assert json.loads((quarantines[0] / "state.json").read_text()) == {
        "value": "legacy"
    }


def test_cleanup_uses_quarantine_when_safe_recursive_delete_is_unavailable(
    tmp_path,
    monkeypatch,
):
    repository = tmp_path / "repo"
    source = repository / "data"
    destination = tmp_path / "canonical" / "data"
    _write_state(source)
    monkeypatch.setattr(
        migration.shutil.rmtree,
        "avoids_symlink_attacks",
        False,
    )

    report = migrate_repo_state(
        source,
        destination,
        apply=True,
        remove_source=True,
        repository_root=repository,
        now=lambda: MOMENT,
    )

    assert report["applied"] is True
    assert report["source_removed"] is True
    assert report["source_cleanup_error"] == "ManualCleanupRequired"
    assert report["source_cleanup_pending"].is_dir()
    assert not source.exists()
    assert (destination / "state.json").exists()


def test_portable_or_configured_source_equal_to_destination_is_safe_noop(tmp_path):
    source = tmp_path / "repo" / "data"
    _write_state(source)

    report = migrate_repo_state(
        source,
        source,
        apply=True,
        repository_root=source.parent,
    )

    assert report["already_canonical"] is True
    assert report["applied"] is False
    assert source.exists()
    with pytest.raises(ValueError, match="already the canonical"):
        migrate_repo_state(
            source,
            source,
            apply=True,
            remove_source=True,
            repository_root=source.parent,
        )


def test_cli_uses_configured_mary_data_dir_and_is_dry_run_by_default(
    tmp_path,
    monkeypatch,
    capsys,
):
    repository_data = tmp_path / "repo" / "data"
    configured = tmp_path / "configured" / "data"
    _write_state(repository_data)
    monkeypatch.setenv("MARY_DATA_DIR", str(configured))

    exit_code = main(["--source", str(repository_data)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert str(configured.resolve()) in output
    assert "DRY RUN ONLY" in output
    assert not configured.exists()


def test_inspection_rejects_nested_source_and_destination(tmp_path):
    source = tmp_path / "data"
    _write_state(source)
    with pytest.raises(ValueError, match="separate"):
        inspect_migration(source, source / "nested")