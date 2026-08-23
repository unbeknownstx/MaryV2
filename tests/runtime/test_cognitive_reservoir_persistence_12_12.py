from __future__ import annotations

from pathlib import Path

from mary.runtime.application import create_application


def test_persistent_application_keeps_reservoir_beside_isolated_state(tmp_path: Path):
    app = create_application(
        memory_path=tmp_path / "memory" / "memory.json",
        developed_self_path=tmp_path / "personality" / "developed.json",
        preference_promotion_path=tmp_path / "personality" / "promotion.json",
        load_memory=False,
        load_developed_self=False,
        load_preference_promotion=False,
    )
    try:
        status = app.mary.mind.status()["reservoir"]
        assert Path(status["path"]).is_relative_to(tmp_path)
        assert Path(status["path"]).exists()
        result = app.run("hey mary")
        assert result.success is True
        cycle = result.metadata["pipeline_values"]["cognitive_cycle"]
        assert cycle.metadata["handled_by"] == "mary_local_mind"
    finally:
        app.close()
