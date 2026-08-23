from __future__ import annotations

from pathlib import Path

from mary.core.mary import Mary
from mary.ecosystem import MaryEcosystem
from mary.presence import PresenceEventType, PresenceManager


def test_companion_pulse_reads_existing_workspaces_without_new_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("MARY_DATA_DIR", str(tmp_path / "data"))
    mary = Mary()
    ecosystem = MaryEcosystem(mary)

    ecosystem.command.add("Polish Mary Home", kind="project", priority=4)
    project = ecosystem.study.create_project("CompTIA")
    ecosystem.study.add_card(project["id"], "HTTPS port?", "443")
    ecosystem.inbox.add("Quiet note", importance=.5)

    pulse = ecosystem.companion_snapshot()
    assert pulse["counts"]["active_tasks"] == 1
    assert pulse["counts"]["study_due"] == 1
    assert pulse["counts"]["inbox_unread"] == 1
    assert pulse["top_tasks"][0]["title"] == "Polish Mary Home"
    assert "not an autonomous planner" in pulse["semantics"]
    assert not (ecosystem.root / "companion.json").exists()


def test_workspace_presence_pathways_do_not_force_interruption(tmp_path):
    presence = PresenceManager(tmp_path)
    command = presence.publish(
        PresenceEventType.COMMAND_CHANGED,
        "Command Center added a task.",
        source="mary_desktop",
        importance=.58,
    )
    study = presence.publish(
        PresenceEventType.STUDY_CHANGED,
        "Study card reviewed.",
        source="mary_desktop",
        importance=.55,
    )
    focus = presence.publish(
        PresenceEventType.FOCUS_CHANGED,
        "Focus started.",
        source="mary_desktop",
        importance=.65,
    )
    assert command["decision"]["speak"] is False
    assert study["decision"]["speak"] is False
    assert focus["decision"]["speak"] is False
    assert all(item["event"]["source"] == "mary_desktop" for item in (command, study, focus))


def test_focus_idle_behavior_is_local_animation_only(tmp_path):
    presence = PresenceManager(tmp_path)
    for _ in range(25):
        result = presence.idle_tick(focus_active=True)
        assert result["focus_quiet"] is True
        assert result["action"]["kind"] == "animation"
        assert not result["action"].get("sound")
        assert not result["action"].get("phrase")


def test_companion_pulse_focus_mode_has_priority(tmp_path, monkeypatch):
    monkeypatch.setenv("MARY_DATA_DIR", str(tmp_path / "data"))
    mary = Mary()
    ecosystem = MaryEcosystem(mary)
    ecosystem.command.add("One task")
    ecosystem.focus.start(25, task="Finish the desktop pass")
    pulse = ecosystem.companion_snapshot()
    assert pulse["mode"] == "focus"
    assert pulse["focus"]["active"] is True
    assert pulse["primary_action"]["screen"] == "focus"
