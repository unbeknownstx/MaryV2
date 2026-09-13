from mary.memory.temporal_projection import TemporalKnowledgeProjection
from mary.relationship.user import UserModel


def test_user_model_history_rebuilds_temporal_creator_fact():
    user = UserModel()
    user.record_profile(category="communication", key="explanation_style", value="examples_first", source="creator", explicitly_shared=True)
    user.record_profile(category="communication", key="explanation_style", value="plain_then_technical", source="creator", explicitly_shared=True)

    projection = TemporalKnowledgeProjection()
    projection.rebuild_user_model(user)

    current = projection.current(subject="creator", predicate="communication.explanation_style")
    history = projection.history(subject="creator", predicate="communication.explanation_style")
    assert len(current) == 1
    assert current[0]["value"] == "plain_then_technical"
    assert len(history) == 2
    assert history[0]["status"] == "historical"
    assert history[1]["supersedes"] == history[0]["fact_id"]
