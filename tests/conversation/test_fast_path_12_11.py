from __future__ import annotations

from mary.conversation import ConversationLane, classify_conversation_lane, choose_reflection_action, local_conversation_repair
from mary.core.config import Config
from mary.llm.router import LLMRouter


def test_short_social_turn_uses_social_instant_lane():
    decision = classify_conversation_lane("hey mary", preferred_length="micro")
    assert decision.lane is ConversationLane.SOCIAL_INSTANT
    assert decision.allow_model_revision is False


def test_technical_turn_uses_thinking_lane():
    decision = classify_conversation_lane("debug this Python architecture and find the root cause")
    assert decision.lane is ConversationLane.THINKING
    assert decision.allow_model_revision is True


def test_style_only_fast_turn_repairs_locally():
    decision = choose_reflection_action(
        ConversationLane.SOCIAL_INSTANT,
        ["Uses canned generic-assistant/helpdesk phrasing."],
    )
    assert decision.action == "local_repair"
    repaired = local_conversation_repair("Good to see you. What about you?", micro=True)
    assert repaired == "Good to see you."


def test_provenance_issue_keeps_strong_revision_boundary():
    decision = choose_reflection_action(
        ConversationLane.SOCIAL_INSTANT,
        ["Conversation provenance boundary: treats Mary's prior dialogue as creator evidence."],
    )
    assert decision.action == "model_revision"


def test_fast_groq_model_is_purpose_specific(monkeypatch):
    import sys, types
    monkeypatch.setenv("MARY_GROQ_CONVERSATION_MODEL", "llama-3.1-8b-instant")
    monkeypatch.setenv("MARY_GROQ_MODEL", "openai/gpt-oss-20b")
    module = types.ModuleType("mary.llm.providers.groq")
    class FakeGroqProvider:
        def __init__(self, model): self.model = model
        def model_name(self): return self.model
    module.GroqProvider = FakeGroqProvider
    monkeypatch.setitem(sys.modules, "mary.llm.providers.groq", module)
    config = Config()
    config.llm.provider = "ollama"  # force MARY_GROQ_MODEL for normal Groq construction
    router = LLMRouter(config)
    fast = router._create_provider("groq", purpose="conversation_fast")
    normal = router._create_provider("groq")
    assert fast.model_name() == "llama-3.1-8b-instant"
    assert normal.model_name() == "openai/gpt-oss-20b"
