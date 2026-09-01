from __future__ import annotations

from mary.relationship.directives import CreatorDirectiveSystem
from mary.relationship.manager import RelationshipManager


def test_default_relationship_subsystems_keep_state_in_memory_without_creating_data(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    relationship = RelationshipManager()
    directives = CreatorDirectiveSystem()

    relationship.load()
    directives.load()
    learned = relationship.learn_explicit("my favorite color is blue")
    directive = directives.add(
        "Be curious about my creative work.",
        category="curiosity",
        target="creative_work",
    )

    assert relationship.path is None
    assert directives.path is None
    assert learned is not None
    assert relationship.profile()["preferences"]["favorite_color"] == "blue"
    assert directive is not None
    assert directives.get_active() == [directive]
    assert not (tmp_path / "data").exists()


def test_explicit_relationship_paths_still_persist_state(tmp_path):
    relationship_path = tmp_path / "relationship.json"
    directives_path = tmp_path / "creator_directives.json"

    relationship = RelationshipManager(path=relationship_path)
    relationship.load()
    relationship.learn_explicit("my favorite color is green")

    directives = CreatorDirectiveSystem(path=directives_path)
    directives.load()
    directive = directives.add(
        "Prioritize clear answers.",
        category="communication",
        target="answers",
    )

    assert relationship_path.exists()
    assert directives_path.exists()
    assert directive is not None

    restored_relationship = RelationshipManager(path=relationship_path)
    restored_relationship.load()
    restored_directives = CreatorDirectiveSystem(path=directives_path)
    restored_directives.load()

    assert restored_relationship.profile()["preferences"]["favorite_color"] == "green"
    assert restored_directives.get_active() == [directive]