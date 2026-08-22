from __future__ import annotations

from pathlib import Path

from mary.core.mary import Mary


def test_mary_persistent_relationship_and_agency_paths_honor_data_dir(
    tmp_path,
    monkeypatch,
):
    data_root = tmp_path / "private_mary_state"
    monkeypatch.setenv("MARY_DATA_DIR", str(data_root))

    mary = Mary()

    assert mary.config.paths.data == data_root.resolve()
    assert mary.relationship.path == data_root / "relationship" / "relationship.json"
    assert mary.creator_directives.path == data_root / "relationship" / "creator_directives.json"
    assert mary.agency.goals.path == data_root / "goals" / "goals.json"
    assert mary.agency.intentions.path == data_root / "goals" / "intentions.json"
    assert mary.agency.curiosities.path == data_root / "goals" / "curiosities.json"

    expected = {
        data_root / "relationship" / "relationship.json",
        data_root / "relationship" / "creator_directives.json",
        data_root / "goals" / "goals.json",
        data_root / "goals" / "intentions.json",
        data_root / "goals" / "curiosities.json",
    }
    assert all(path.exists() for path in expected)

    # The configured data root is the only location these systems should own.
    for path in expected:
        assert data_root.resolve() in path.resolve().parents


def test_agency_write_stays_inside_configured_data_dir(tmp_path, monkeypatch):
    data_root = tmp_path / "isolated"
    monkeypatch.setenv("MARY_DATA_DIR", str(data_root))
    mary = Mary()

    curiosity = mary.agency.curiosities.add_curiosity(
        "whether this path survives a restart",
        importance=0.7,
        source="test",
    )
    assert curiosity is not None

    restarted = Mary()
    descriptions = {
        str(item.get("description", ""))
        for item in restarted.agency.curiosities.get_curiosities()
    }
    assert "whether this path survives a restart" in descriptions
    assert restarted.agency.curiosities.path == data_root / "goals" / "curiosities.json"
