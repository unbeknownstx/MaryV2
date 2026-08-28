from __future__ import annotations

from mary.cognition.continuity import ConversationContinuity
from mary.cognition.intent import IntentType
from mary.expression.performance_packet import build_performance_packet
from mary.presence import PresenceEventType, PresenceManager
from mary.realtime import AttentionBus


def test_observable_conversation_rhythm_creates_ephemeral_momentum_without_claiming_hidden_emotion():
    continuity = ConversationContinuity()
    quiet = continuity.build(
        input_text="okay",
        intent_type=IntentType.CONVERSATION,
        recent_conversation=[
            {"role": "user", "content": "I looked at it."},
            {"role": "assistant", "content": "Yeah. I see what you mean."},
        ],
    )
    lively = continuity.build(
        input_text="LMAO hell yeah!!",
        intent_type=IntentType.CONVERSATION,
        recent_conversation=[
            {"role": "user", "content": "wait it worked??"},
            {"role": "assistant", "content": "No way. It actually did."},
            {"role": "user", "content": "LOL FINALLY"},
            {"role": "assistant", "content": "Okay, that's a W."},
            {"role": "user", "content": "hell yeah!!"},
            {"role": "assistant", "content": "We got it."},
        ],
    )

    assert lively.interaction_momentum > quiet.interaction_momentum
    assert lively.cadence_mode in {"engaged", "lively"}
    instruction = " ".join(lively.instructions).lower()
    assert "observable conversational rhythm" in instruction
    assert "not unbe's hidden emotion" in instruction
    assert "serious emotion or moral stakes always override" in instruction


def test_presence_claim_consumes_the_same_event_from_attention_bus(tmp_path, monkeypatch):
    monkeypatch.setenv("MARY_PRESENCE_MIN_SPEAK_INTERVAL", "5")
    monkeypatch.setenv("MARY_PRESENCE_THRESHOLD", "0.5")
    attention = AttentionBus()
    presence = PresenceManager(tmp_path, attention=attention)

    published = presence.publish(
        PresenceEventType.PROJECT_CHANGED,
        "The MaryV2 verification suite just became green.",
        source="test",
        importance=0.98,
    )
    attention_id = published["event"]["metadata"]["attention_event_id"]
    assert any(item.id == attention_id for item in attention.pending())

    claimed = presence.claim_initiative(
        focus_active=False,
        realtime_phase="idle",
        surface_visible=True,
    )

    assert claimed["speak"] is True
    assert claimed["authority"] == "environment_context_only"
    assert claimed["candidate"]["metadata"]["attention_event_id"] == attention_id
    assert all(item.id != attention_id for item in attention.pending())


def test_performance_packet_is_presentation_only_and_leads_speech_with_a_bounded_microreaction():
    packet = build_performance_packet(
        "Oh, fantastic. You deleted it again.",
        {
            "profile": "teasing",
            "energy": 0.72,
            "warmth": 0.68,
            "pace": 1.06,
            "avatar_expression": "happy",
            "gesture_style": "tease",
            "gaze_style": "direct",
            "head_style": "tilt",
            "reaction_style": "laugh",
            "interruptible": True,
        },
        social_context="casual",
    ).to_dict()

    assert packet["social_context"] == "casual"
    assert packet["source_authority"] == "creator_turn"
    assert packet["initiative"] is False
    assert 120 <= packet["pre_reaction"]["duration_ms"] <= 420
    assert packet["pre_reaction"]["expression"] == "happy"
    assert 1 <= len(packet["segments"]) <= 5
    assert packet["segments"][0]["start"] == 0.0
    assert packet["segments"][-1]["end"] == 1.0
    assert "presentation-only" in packet["policy"]
    assert "memory" in packet["policy"]


def test_presence_ingestion_keeps_salient_event_queued_during_speak_cooldown(tmp_path, monkeypatch):
    monkeypatch.setenv("MARY_PRESENCE_MIN_SPEAK_INTERVAL", "5")
    monkeypatch.setenv("MARY_PRESENCE_THRESHOLD", "0.5")
    presence = PresenceManager(tmp_path)
    presence.mark_spoken()

    published = presence.publish(
        PresenceEventType.PROJECT_CHANGED,
        "The verification suite became green.",
        source="test",
        importance=0.95,
    )

    assert published["decision"]["speak"] is True
    assert presence.snapshot()["initiative_candidates"] == 1
    blocked = presence.claim_initiative(
        focus_active=False,
        realtime_phase="idle",
        surface_visible=True,
    )
    assert blocked["speak"] is False
    assert blocked["reason"] == "speak_cooldown"
    assert presence.snapshot()["initiative_candidates"] == 1

    # Once timing arbitration permits speech, the original event is still there.
    presence.initiative._last_spoke_at = 0.0
    claimed = presence.claim_initiative(
        focus_active=False,
        realtime_phase="idle",
        surface_visible=True,
    )
    assert claimed["speak"] is True
    assert "verification suite" in claimed["candidate"]["summary"].lower()


def test_presence_coalesces_duplicate_salient_events_before_attention_spam(tmp_path, monkeypatch):
    monkeypatch.setenv("MARY_PRESENCE_THRESHOLD", "0.5")
    attention = AttentionBus()
    presence = PresenceManager(tmp_path, attention=attention)

    first = presence.publish(
        PresenceEventType.PROJECT_CHANGED,
        "Build finished successfully.",
        source="watcher",
        importance=0.9,
    )
    second = presence.publish(
        PresenceEventType.PROJECT_CHANGED,
        "Build finished successfully.",
        source="watcher",
        importance=0.9,
    )

    assert first["coalesced"] is False
    assert second["coalesced"] is True
    assert presence.snapshot()["initiative_candidates"] == 1
    assert attention.snapshot()["pending"] == 1
