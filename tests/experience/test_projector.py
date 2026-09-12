from mary.experience import build_experience_snapshot


def test_experience_snapshot_keeps_mary_core_as_identity_owner():
    snapshot = build_experience_snapshot(
        {"core": {"architecture": "13.2"}},
        {"provider": "groq", "model": "openai/gpt-oss-20b"},
    )
    assert snapshot["authority"] == "presentation_projection_only"
    assert snapshot["identity_owner"] == "mary_core"
    assert snapshot["provider"] == "groq"
    assert snapshot["provider"] != snapshot["identity_owner"]


def test_experience_snapshot_whitelists_frontend_safe_fields():
    snapshot = build_experience_snapshot(
        {
            "core": {"architecture": "13.2", "ok": True},
            "secret": "DO-NOT-LEAK",
            "provider_api_key": "sk-private",
            "mobile": {"authority": "remote_mary_core"},
        },
        {"provider": "openai", "private_prompt": "hidden"},
    )
    rendered = repr(snapshot)
    assert "DO-NOT-LEAK" not in rendered
    assert "sk-private" not in rendered
    assert "private_prompt" not in rendered


def test_thinking_state_selects_focused_theme():
    snapshot = build_experience_snapshot(
        {"live": {"character": {"runtime_status": "thinking", "mood": "Neutral"}}},
        {},
    )
    assert snapshot["interaction_state"] == "thinking"
    assert snapshot["theme"]["name"] == "focused"


def test_relationship_strength_normalizes_percent_values():
    snapshot = build_experience_snapshot(
        {"relationship": {"label": "Established", "strength": 73}},
        {},
    )
    assert snapshot["relationship_label"] == "Established"
    assert snapshot["relationship_strength"] == 0.73


def test_explicit_relational_mode_projects_to_surface_without_becoming_authority():
    snapshot = build_experience_snapshot(
        {
            "relationship": {"label": "Established", "strength": 73},
            "performance_hardening": {
                "relational_presence": {"relationship_mode": "partner"}
            },
        },
        {},
    )
    assert snapshot["relationship_label"] == "Partner"
    assert snapshot["metadata"]["relationship_mode"] == "partner"
    assert snapshot["authority"] == "presentation_projection_only"
    relationship_cue = next(cue for cue in snapshot["cues"] if cue["channel"] == "relationship")
    assert relationship_cue["detail"] == "partner"


def test_friend_mode_preserves_existing_familiarity_label():
    snapshot = build_experience_snapshot(
        {
            "relationship": {"label": "Established", "strength": .6},
            "performance_hardening": {
                "relational_presence": {"relationship_mode": "friend"}
            },
        },
        {},
    )
    assert snapshot["relationship_label"] == "Established"
    assert snapshot["metadata"]["relationship_mode"] == "friend"


def test_memory_count_sums_existing_counts_without_writing_memory():
    dashboard = {"memory": {"counts": {"episodic": 11, "semantic": 7, "working": 2}}}
    snapshot = build_experience_snapshot(dashboard, {})
    assert snapshot["memory_count"] == 20
    assert dashboard["memory"]["counts"]["episodic"] == 11


def test_projector_accepts_current_live_dashboard_shape():
    snapshot = build_experience_snapshot(
        {
            "live": {
                "character": {
                    "status": "speaking",
                    "mood": "amused",
                    "energy": "engaged",
                    "memory_count": 14,
                    "current_task": "Character pass",
                },
                "memory": {"episodic": 9, "semantic": 5, "working": 0},
            },
            "relationship": {"score": 64, "label": "Established"},
        },
        {},
    )
    assert snapshot["interaction_state"] == "speaking"
    assert snapshot["mood"] == "amused"
    assert snapshot["memory_count"] == 14
    assert snapshot["active_task"] == "Character pass"
    assert snapshot["relationship_strength"] == 0.64
    assert snapshot["theme"]["name"] == "bright"


def test_projector_reads_canonical_sourcebook_count_without_evidence():
    dashboard = {
        "character": {
            "sourcebook": {
                "records": 189,
                "source_names": ["PRIVATE_AUTHORED_SOURCE"],
                "records_preview": ["PRIVATE_AUTHORED_EVIDENCE"],
            },
        },
    }

    snapshot = build_experience_snapshot(dashboard, {})

    assert snapshot["metadata"]["character_records"] == 189
    assert "PRIVATE_AUTHORED_SOURCE" not in repr(snapshot)
    assert "PRIVATE_AUTHORED_EVIDENCE" not in repr(snapshot)
