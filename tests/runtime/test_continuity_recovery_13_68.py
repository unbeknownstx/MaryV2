from types import SimpleNamespace

from mary.memory.manager import MemoryManager
from mary.relationship.manager import RelationshipManager
from mary.runtime.continuity_recovery import (
    apply_recovery_payload,
    build_recovery_plan,
    capture_continuity_state,
    normalize_recovery_payload,
    restore_continuity_state,
)


def _mary():
    relationship = RelationshipManager()
    mary = SimpleNamespace(
        memory=MemoryManager(),
        relationship=relationship,
    )
    mary.user_model = relationship.user_model
    mary.relationship_history = relationship.history
    mary.relationship_understanding = relationship.understanding
    mary.relationship_milestones = relationship.milestones
    return mary


def _payload():
    return {
        "memory": {
            "episodic": [
                {
                    "id": "episode_old_1",
                    "content": "We worked on the Windows Mary desktop together.",
                    "timestamp": "2026-08-20T10:00:00+00:00",
                    "importance": 0.8,
                    "source": "interaction",
                    "event_type": "shared_work",
                    "participants": ["creator", "mary"],
                    "emotional_context": {},
                    "metadata": {},
                }
            ],
            "semantic": [],
            "working": [{"content": "must never import"}],
        },
        "relationship": {
            "user_model": {
                "creator_id": "creator",
                "name": "unbe",
                "facts": {"job": "older local value"},
                "preferences": {},
                "interests": ["open source AI"],
                "values": [],
                "goals": [],
                "communication_style": {},
                "profile_records": [
                    {
                        "id": "profile_1",
                        "category": "fact",
                        "key": "job",
                        "value": "older local value",
                        "status": "current",
                        "source": "creator_natural",
                        "confidence": 1.0,
                        "explicitly_shared": True,
                        "created_at": "2026-08-20T10:00:00+00:00",
                        "updated_at": "2026-08-20T10:00:00+00:00",
                    }
                ],
            },
            "history": {
                "creator_id": "creator",
                "events": [
                    {
                        "id": "relationship_old_1",
                        "creator_id": "creator",
                        "type": "shared_experience",
                        "description": "Built Mary on Windows.",
                        "importance": 0.8,
                        "source": "relationship",
                        "metadata": {},
                        "created_at": "2026-08-20T10:00:00+00:00",
                    }
                ],
            },
            "understanding": {
                "observations": [],
                "inferences": [],
                "patterns": [],
            },
            "milestones": [],
        },
    }


def test_recovery_normalization_excludes_working_memory():
    normalized = normalize_recovery_payload(_payload())
    assert "working" not in normalized["memory"]
    assert list(normalized["memory"]) == ["episodic", "semantic"]


def test_recovery_plan_is_content_free_counts_and_detects_current_profile_conflict():
    mary = _mary()
    mary.relationship.user_model.record_profile(
        category="fact",
        key="job",
        value="newer core value",
        source="creator_natural",
        confidence=1.0,
        explicitly_shared=True,
    )

    plan = build_recovery_plan(mary, _payload())

    assert plan["source"]["episodic"] == 1
    assert plan["source"]["relationship_history"] == 1
    assert plan["additions"]["episodic"] == 1
    assert plan["conflicts"]["creator_profile_scalar_conflicts"] == 1
    assert plan["policy"]["current_core_wins_profile_conflicts"] is True
    assert plan["policy"]["working_memory_imported"] is False


def test_recovery_merge_preserves_current_core_scalar_and_keeps_old_value_historical():
    mary = _mary()
    mary.relationship.user_model.record_profile(
        category="fact",
        key="job",
        value="newer core value",
        source="creator_natural",
        confidence=1.0,
        explicitly_shared=True,
    )

    result = apply_recovery_payload(mary, _payload())

    assert result["added"]["episodic"] == 1
    assert result["added"]["relationship_history"] == 1
    assert mary.memory.episodic.count() == 1
    assert mary.relationship.history.count() == 1
    assert mary.relationship.user_model.facts["job"] == "newer core value"

    recovered = [
        item
        for item in mary.relationship.user_model.profile_records
        if item.get("value") == "older local value"
    ]
    assert len(recovered) == 1
    assert recovered[0]["status"] == "historical"
    assert result["profile_conflicts_preserved_as_history"] == 1


def test_recovery_is_idempotent_for_same_source_payload():
    mary = _mary()

    first = apply_recovery_payload(mary, _payload())
    second = apply_recovery_payload(mary, _payload())

    assert first["added"]["episodic"] == 1
    assert first["added"]["relationship_history"] == 1
    assert second["added"]["episodic"] == 0
    assert second["added"]["relationship_history"] == 0
    assert mary.memory.episodic.count() == 1
    assert mary.relationship.history.count() == 1


def test_recovery_snapshot_can_restore_premerge_state_and_aliases():
    mary = _mary()
    mary.relationship.user_model.record_profile(
        category="fact",
        key="city",
        value="current city",
        source="creator_natural",
        explicitly_shared=True,
    )
    snapshot = capture_continuity_state(mary)

    apply_recovery_payload(mary, _payload())
    assert mary.memory.episodic.count() == 1

    restore_continuity_state(mary, snapshot)

    assert mary.memory.episodic.count() == 0
    assert mary.relationship.history.count() == 0
    assert mary.user_model is mary.relationship.user_model
    assert mary.relationship_history is mary.relationship.history
    assert mary.relationship.user_model.facts["city"] == "current city"


def test_legacy_profile_facade_is_recovered_without_requiring_profile_records():
    mary = _mary()
    payload = {
        "memory": {},
        "relationship": {
            "user_model": {
                "facts": {"favorite_tool": "terminal"},
                "interests": ["local AI"],
            },
        },
    }

    result = apply_recovery_payload(mary, payload)

    assert result["added"]["creator_profile_records"] == 2
    assert mary.relationship.user_model.facts["favorite_tool"] == "terminal"
    assert "local AI" in mary.relationship.user_model.interests
