from mary.training import ResponseFeedbackStore


def test_feedback_store_requires_explicit_completed_turn_and_is_not_authority(tmp_path):
    store = ResponseFeedbackStore(tmp_path / "feedback.json")
    record = store.record(
        rating="positive",
        user_text="hey",
        assistant_text="Hey. What's up?",
        provider="groq",
        model="test",
        tags=["felt_like_mary", "not_allowed"],
    )
    assert record.rating == "positive"
    assert record.tags == ("felt_like_mary",)
    state = store.status()
    assert state["records"] == 1
    assert "never character-state authority" in state["policy"]
    loaded = ResponseFeedbackStore(tmp_path / "feedback.json")
    assert loaded.status()["records"] == 1


def test_feedback_store_rejects_invalid_rating(tmp_path):
    store = ResponseFeedbackStore(tmp_path / "feedback.json")
    try:
        store.record(rating="perfect", user_text="x", assistant_text="y")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid feedback rating should fail")
