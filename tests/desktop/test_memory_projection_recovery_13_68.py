from mary.desktop.dashboard import build_desktop_dashboard_state
from mary.runtime.application import create_application


def _app(tmp_path):
    return create_application(
        memory_path=tmp_path / "memory" / "memory.json",
        developed_self_path=tmp_path / "personality" / "developed_self.json",
        preference_promotion_path=tmp_path / "personality" / "preference_promotion.json",
        knowledge_path=tmp_path / "knowledge" / "knowledge.json",
        auto_save=False,
        load_memory=False,
        load_developed_self=False,
        load_preference_promotion=False,
        load_knowledge=False,
        name="memory-projection-13-68",
    )


def test_memory_archive_reports_canonical_totals_not_only_visible_window(tmp_path):
    app = _app(tmp_path)
    try:
        mary = app.mary

        for index in range(15):
            mary.relationship_history.record_shared_experience(
                description=f"Shared work continuity {index}",
                importance=0.6,
                metadata={"kind": "shared_work", "owner": "creator"},
            )

        state = build_desktop_dashboard_state(mary)
        archive = state["memory_archive"]

        assert archive["counts"]["shared_history_total"] == 15
        assert archive["counts"]["shared_history_visible"] == 12
        assert len(archive["shared_history"]) == 12
    finally:
        app.close()


def test_memory_archive_reports_profile_and_relationship_observation_totals(tmp_path):
    app = _app(tmp_path)
    try:
        mary = app.mary

        mary.user_model.record_profile(
            category="interest",
            key="interest",
            value="local AI",
            source="creator_natural",
            explicitly_shared=True,
        )
        mary.relationship_understanding.observations.append(
            {
                "id": "observation_projection_test",
                "content": "Creator enjoys local AI work.",
                "source": "creator",
            }
        )

        state = build_desktop_dashboard_state(mary)
        counts = state["memory_archive"]["counts"]

        assert counts["creator_profile_total"] == 1
        assert counts["relationship_observation_total"] == 1
    finally:
        app.close()


def test_broad_creator_recall_includes_relationship_history(tmp_path):
    app = _app(tmp_path)
    try:
        mary = app.mary
        mary.relationship_history.record_shared_experience(
            description="We spent time rebuilding Mary's desktop and local compute path.",
            importance=0.9,
            metadata={"kind": "shared_work", "owner": "creator"},
        )

        response = mary._creator_memory_overview(recent_conversation=[]).lower()

        assert "relationship history" in response
        assert "desktop and local compute" in response
    finally:
        app.close()
