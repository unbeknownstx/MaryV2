from pathlib import Path

from mary.runtime.recovery import MaryRecovery


def test_recovery_manifest_excludes_env_and_verifies(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "memory.json").write_text('{"safe":true}', encoding="utf-8")
    (state / ".env").write_text("OPENAI_API_KEY=never-copy", encoding="utf-8")
    target = tmp_path / "backup"

    result = MaryRecovery.create_snapshot({"state": state}, target, copy_files=True)
    assert result["copied"] == 1
    assert not (target / "roots" / "state" / ".env").exists()
    verified = MaryRecovery.verify(result["manifest"], {"state": state})
    assert verified["ok"] is True
