from __future__ import annotations

from mary.core.mary import Mary
from mary.runtime.application import create_application
from scripts import run_release_verification as release


def test_application_can_use_ephemeral_reservoir_for_disposable_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("MARY_RESERVOIR_STORAGE", "memory")
    app = create_application(
        mary=Mary(),
        memory_path=tmp_path / "memory" / "memory.json",
        auto_save=False,
        load_memory=False,
        load_developed_self=False,
        load_preference_promotion=False,
    )
    try:
        status = app.mary.mind.reservoir.status()
        assert status["persistent"] is False
        assert not (tmp_path / "reservoir" / "mary_reservoir.sqlite3").exists()
    finally:
        app.close()


def test_offline_process_environment_restores_reservoir_mode(monkeypatch):
    monkeypatch.setenv("MARY_RESERVOIR_STORAGE", "persistent")
    with release._offline_process_environment():
        assert release.os.environ["MARY_RESERVOIR_STORAGE"] == "memory"
    assert release.os.environ["MARY_RESERVOIR_STORAGE"] == "persistent"
