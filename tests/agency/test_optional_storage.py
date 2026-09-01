from __future__ import annotations

from mary.agency.agency import Agency
from mary.agency.curiosity import CuriositySystem
from mary.agency.goals import GoalSystem
from mary.agency.intentions import IntentionSystem


def test_default_agency_stores_keep_state_in_memory_without_creating_data(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    goals = GoalSystem()
    intentions = IntentionSystem()
    curiosities = CuriositySystem()
    agency = Agency(storage_root=None)

    for store in (goals, intentions, curiosities):
        store.load()
        assert store.path is None

    assert goals.add_goal("Keep this goal in memory") is not None
    assert intentions.add_intention("Keep this intention in memory") is not None
    assert curiosities.add_curiosity("Keep this curiosity in memory") is not None

    agency.load()
    assert agency.goals.path is None
    assert agency.intentions.path is None
    assert agency.curiosities.path is None
    assert agency.goals.add_goal("Agency in-memory goal") is not None
    assert agency.intentions.add_intention("Agency in-memory intention") is not None
    assert agency.curiosities.add_curiosity("Agency in-memory curiosity") is not None

    assert len(goals.get_goals()) == 1
    assert len(intentions.get_intentions()) == 1
    assert len(curiosities.get_curiosities()) == 1
    assert not (tmp_path / "data").exists()


def test_agency_storage_root_persists_all_agency_stores(tmp_path):
    storage_root = tmp_path / "agency"
    agency = Agency(storage_root=storage_root)

    assert agency.goals.add_goal("Persist this goal") is not None
    assert agency.intentions.add_intention("Persist this intention") is not None
    assert agency.curiosities.add_curiosity("Persist this curiosity") is not None

    assert (storage_root / "goals.json").exists()
    assert (storage_root / "intentions.json").exists()
    assert (storage_root / "curiosities.json").exists()

    recovered = Agency(storage_root=storage_root)
    recovered.load()

    assert [goal["description"] for goal in recovered.goals.get_goals()] == [
        "Persist this goal"
    ]
    assert [intention["description"] for intention in recovered.intentions.get_intentions()] == [
        "Persist this intention"
    ]
    assert [curiosity["description"] for curiosity in recovered.curiosities.get_curiosities()] == [
        "Persist this curiosity"
    ]