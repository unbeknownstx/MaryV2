from mary.relationship.manager import RelationshipManager
from mary.relationship.relational_presence import RelationalPresenceRuntime


def test_relationship_mode_uses_existing_history(tmp_path):
    manager = RelationshipManager(path=tmp_path / "relationship.json")
    manager.load()
    presence = RelationalPresenceRuntime(manager)
    assert presence.relationship_mode() == "friend"
    assert manager.history.summary()["relationship_mode"] == "friend"
    changed = presence.set_relationship_mode("partner")
    assert changed["changed"] is True
    assert manager.history.summary()["relationship_mode"] == "partner"
    restarted = RelationshipManager(path=tmp_path / "relationship.json")
    restarted.load()
    assert RelationalPresenceRuntime(restarted).relationship_mode() == "partner"
    assert restarted.history.summary()["relationship_mode"] == "partner"


def test_shared_activity_completion_becomes_existing_shared_experience(tmp_path):
    manager = RelationshipManager(path=tmp_path / "relationship.json")
    manager.load()
    presence = RelationalPresenceRuntime(manager)
    activity = presence.start_activity("movie", "Watch a movie together")
    assert activity["activity_type"] == "movie"
    presence.note_activity("We both laughed at the opening scene.")
    event = presence.complete_activity(summary="Mary and creator watched a movie together.")
    assert event["type"] == "shared_experience"
    assert event["metadata"]["activity_type"] == "movie"
    assert manager.history.summary()["shared_experiences"] == 1
    assert presence.snapshot()["active_activity"] is None


def test_presence_is_proposal_only_and_bounded():
    manager = RelationshipManager()
    presence = RelationalPresenceRuntime(manager, proposal_capacity=2)
    presence.propose_presence("unfinished conversation", priority=0.3)
    presence.propose_presence("creator returned", priority=0.9)
    presence.propose_presence("shared event approaching", priority=0.7)
    pending = presence.pending_proposals()
    assert len(pending) == 2
    assert pending[0]["priority"] >= pending[1]["priority"]
    assert "send" not in presence.snapshot()


def test_social_graph_is_derived_not_authoritative():
    manager = RelationshipManager()
    presence = RelationalPresenceRuntime(manager)
    graph = presence.social_graph()
    assert graph["authority"] == "derived_projection_only"
    assert {node["id"] for node in graph["nodes"]} >= {"mary", "creator"}
