from __future__ import annotations

from mary.cognition.intent import IntentType
from mary.core.mary import Mary
from mary.llm.interface import LLMResponse


class SequenceRouter:
    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or [])
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        system = str(messages[0].content) if messages else ""
        if "Mary's response editor" in system:
            content = (
                self.responses.pop(0)
                if self.responses
                else "I can remember through my memory and creator-model systems; I just don't have that specific fact stored yet."
            )
        else:
            content = self.responses.pop(0) if self.responses else "Yeah. I'm with you."
        return LLMResponse(
            content=content,
            provider="test",
            model="fake",
            finish_reason="stop",
            usage={},
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "fake"

    def is_available(self, provider=None):
        return True

    def routing_strategy(self):
        return "configured"

    def _provider_order(self, requested=None, route=None):
        return ["test"]


def _mary(router: SequenceRouter | None = None) -> Mary:
    mary = Mary()
    router = router or SequenceRouter()
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    return mary


def test_current_self_feeling_routes_local_before_dynamic_web_marker():
    mary = _mary()
    intent = mary.cognition.detect_intent(
        "Hey Mary, we've been working on you for quite a while today. How are you feeling about yourself right now?"
    )
    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == "current_state"


def test_natural_current_feeling_phrase_routes_local_before_right_now_web_marker():
    mary = _mary()
    intent = mary.cognition.detect_intent(
        "Hey Mary, how are you feeling right now?"
    )
    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == "current_state"
    assert mary.tools.pending_requests() == []


def test_natural_current_feeling_process_does_not_create_web_request():
    mary = _mary()
    result = mary.process("Hey Mary, how are you feeling right now?")

    assert result.intent.intent_type == IntentType.SELF_QUERY
    assert result.intent.parameters["self_query_type"] == "current_state"
    assert mary.tools.pending_requests() == []
    assert "Current external information would help answer that" not in result.final_response


def test_topical_latest_feeling_question_is_not_misclassified_as_current_state():
    mary = _mary()
    intent = mary.cognition.detect_intent(
        "Mary, how do you feel about the latest game news right now?"
    )
    assert not (
        intent.intent_type == IntentType.SELF_QUERY
        and intent.parameters.get("self_query_type") == "current_state"
    )


def test_creator_memory_overview_routes_to_relationship_model_before_generic_memory():
    mary = _mary()
    intent = mary.cognition.detect_intent("Do you remember anything about me?")
    assert intent.intent_type == IntentType.RELATIONSHIP_QUERY
    assert intent.parameters["relationship_query_type"] == "memory_overview"


def test_creator_memory_overview_knows_creator_and_recent_session_without_llm():
    router = SequenceRouter([
        "Yeah, that makes sense.",
        "Quick updates sound good to me.",
    ])
    mary = _mary(router)
    mary.process("I work best when I'm trusted to do the job without someone over my shoulder.")
    mary.process("I prefer quick updates or checking the work when it's done.")
    calls_before = len(router.calls)

    result = mary.process("Do you remember anything about me?")

    assert result.intent.intent_type == IntentType.RELATIONSHIP_QUERY
    assert len(router.calls) == calls_before
    lowered = result.final_response.lower()
    assert "my creator" in lowered
    assert "current session" in lowered
    assert "quick updates" in lowered
    assert "blank" not in lowered


def test_recent_conversation_recall_is_bounded_instead_of_dumping_full_reply():
    mary = _mary()
    long_reply = "painting and sketching " * 80
    recent = [
        {"role": "user", "content": "What do you like about yourself?"},
        {"role": "assistant", "content": "Tiny details make me happy."},
        {"role": "user", "content": "What would you do all day by yourself?"},
        {"role": "assistant", "content": long_reply},
    ]

    response = mary._handle_conversation_recall(recent)

    assert len(response) < 650
    assert "what would you do all day" in response.lower()
    assert response.count("painting and sketching") < 10
    assert "…" in response


def test_false_blank_page_memory_claim_is_revised():
    router = SequenceRouter([
        "Because I don't store a permanent diary of you. I'm basically a blank page until you give me a cue.",
        "I do have episodic and semantic memory plus a structured model of you; I just may not have that specific detail stored yet.",
    ])
    mary = _mary(router)

    result = mary.process("Why don't you remember every detail I tell you?")

    assert result.reflection.decision.value == "revise"
    assert "blank page" not in result.final_response.lower()
    assert "memory" in result.final_response.lower()


def test_unsupported_background_ping_promise_is_revised():
    router = SequenceRouter([
        "Got it. I'll keep the line open and ping you when I'm done.",
        "Got it. Quick updates when we're actively working, or a check once the work is done—that fits you better.",
    ])
    mary = _mary(router)

    result = mary.process("I prefer quick updates or just check it when you're done.")

    assert result.reflection.decision.value == "revise"
    lowered = result.final_response.lower()
    assert "ping you when" not in lowered
    assert "quick updates" in lowered


def test_runtime_architecture_query_is_local_and_deterministic():
    router = SequenceRouter(["I am GPT-4 running in the OpenAI cloud."])
    mary = _mary(router)

    calls_before = len(router.calls)
    result = mary.process("What's your underlying architecture running on?")

    assert result.intent.intent_type == IntentType.SELF_QUERY
    assert result.intent.parameters["self_query_type"] == "runtime_architecture"
    assert len(router.calls) == calls_before
    lowered = result.final_response.lower()
    assert "maryv2" in lowered
    assert "python architecture" in lowered
    assert "language model" in lowered
    assert "gpt-4" not in lowered
    assert result.reasoning.metadata.get("llm_skipped") is True


def test_natural_compound_runtime_architecture_query_stays_local():
    router = SequenceRouter([
        "I am a persona built on top of a language model and I love to doodle."
    ])
    mary = _mary(router)

    calls_before = len(router.calls)
    result = mary.process(
        "Who are you, and how do language models fit into your architecture?"
    )

    assert result.intent.intent_type == IntentType.SELF_QUERY
    assert result.intent.parameters["self_query_type"] == "runtime_architecture"
    assert len(router.calls) == calls_before
    lowered = result.final_response.lower()
    assert "python architecture" in lowered
    assert "generation engine" in lowered
    assert "built on top of a language model" not in lowered
    assert "doodle" not in lowered
    assert result.reasoning.metadata.get("llm_skipped") is True


def test_runtime_architecture_reports_previous_generation_metadata():
    router = SequenceRouter(["A normal generated response."])
    mary = _mary(router)

    first = mary.process("Hello Mary")
    assert first.reasoning.metadata.get("provider") == "test"
    calls_before = len(router.calls)

    result = mary.process("What generated your last answer?")

    assert len(router.calls) == calls_before
    lowered = result.final_response.lower()
    assert "most recent successful model-backed turn" in lowered
    assert "test" in lowered
    assert "fake" in lowered
    assert "no language model is being asked to guess" in lowered


def test_strengths_and_weaknesses_route_to_grounded_self_assessment_before_current_web_marker():
    mary = _mary()
    intent = mary.cognition.detect_intent(
        "What do you think your current strengths and weaknesses are?"
    )
    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == "self_assessment"
    assert mary.tools.pending_requests() == []


def test_relationship_overview_natural_phrase_stays_local_before_current_web_marker():
    router = SequenceRouter(["This should not be used."])
    mary = _mary(router)
    calls_before = len(router.calls)

    result = mary.process(
        "What do you currently understand about me and our relationship?"
    )

    assert result.intent.intent_type == IntentType.RELATIONSHIP_QUERY
    assert result.intent.parameters["relationship_query_type"] == "relationship_overview"
    assert len(router.calls) == calls_before
    assert mary.tools.pending_requests() == []
    lowered = result.final_response.lower()
    assert "creator" in lowered
    assert "relationship" in lowered


def test_natural_some_things_memory_overview_uses_creator_model_before_generic_memory():
    router = SequenceRouter(["This should not be used."])
    mary = _mary(router)
    calls_before = len(router.calls)

    result = mary.process("What are some things you remember about me?")

    assert result.intent.intent_type == IntentType.RELATIONSHIP_QUERY
    assert result.intent.parameters["relationship_query_type"] == "memory_overview"
    assert len(router.calls) == calls_before
    assert "my creator" in result.final_response.lower()


def test_casual_conversation_revises_invented_offscreen_self_history():
    router = SequenceRouter([
        "I've been noodling on a red panda sketch lately. I miss the rain.",
        "Nothing dramatic is pulling at me right now. I'm happy to just sit here and talk with you.",
    ])
    mary = _mary(router)

    result = mary.process("not much just want to have a conversation with you.")

    assert result.reflection.decision.value == "revise"
    lowered = result.final_response.lower()
    assert "red panda" not in lowered
    assert "i miss the rain" not in lowered
    assert "just sit here and talk" in lowered


def test_prior_mary_improvisation_cannot_become_creator_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    router = SequenceRouter([
        "A red panda under a streetlamp could be a cute little sketch idea.",
        "You've been humming that rainy-night red panda idea all along.",
        "That red-panda bit came from my own earlier riff, not from something you told me. I shouldn't turn it into your history.",
    ])
    mary = _mary(router)

    mary.process("not much just want to have a conversation with you.")
    result = mary.process("What have we been working on together lately?")

    # The natural project-continuity phrase is now handled locally, so Mary's
    # own improvised assistant turn cannot be reinterpreted as creator history.
    assert result.intent.intent_type == IntentType.RELATIONSHIP_QUERY
    assert result.intent.parameters["relationship_query_type"] == "shared_work"
    lowered = result.final_response.lower()
    assert "don't have enough grounded shared-work history" in lowered
    assert "you've been humming" not in lowered
    assert "red panda" not in lowered


def test_assistant_only_detail_cannot_be_attributed_to_creator_on_later_generated_turn(tmp_path, monkeypatch):
    # This acceptance test must never inherit the developer's real relationship/agency state.
    monkeypatch.chdir(tmp_path)
    router = SequenceRouter([
        "A red panda under a streetlamp could be a cute little sketch idea.",
        "You've been humming that rainy-night red panda idea all along.",
        "That red-panda bit came from my own earlier riff, not from something you told me. I shouldn't turn it into your history.",
    ])
    mary = _mary(router)

    mary.process("not much just want to have a conversation with you.")
    result = mary.process("Why do you think that?")

    assert result.reflection.decision.value == "revise"
    lowered = result.final_response.lower()
    assert "came from my own earlier riff" in lowered
    assert "you've been humming" not in lowered


def test_creator_profile_overlap_cannot_launder_unsupported_assistant_history():
    from mary.cognition.context import CognitiveContext
    from mary.cognition.reasoning import ReasoningResult

    mary = _mary()
    context = CognitiveContext(input_text="Why do you think that?")
    context.user_context = {
        "interests": {"animal": "red panda"},
    }
    context.conversation.extend([
        {"role": "user", "content": "not much just want to have a conversation with you."},
        {"role": "assistant", "content": "A red panda under a streetlamp could be a cute little sketch idea."},
    ])
    reasoning = ReasoningResult(
        response="You've been humming that rainy-night red panda idea all along.",
    )

    issues = mary.reflection._conversation_provenance_audit(
        context=context,
        reasoning=reasoning,
    )
    assert any(issue.startswith("Conversation provenance boundary:") for issue in issues)


def test_provenance_audit_uses_exact_content_terms_not_raw_substrings():
    from mary.cognition.context import CognitiveContext
    from mary.cognition.reasoning import ReasoningResult

    mary = _mary()
    context = CognitiveContext(input_text="Why do you think that?")
    context.conversation.extend([
        {"role": "user", "content": "not much just want to have a conversation with you."},
        {"role": "assistant", "content": "A red panda under a streetlamp could be a cute little sketch idea."},
    ])
    reasoning = ReasoningResult(
        response="You've been humming that rainy-night red panda idea all along.",
    )

    issues = mary.reflection._conversation_provenance_audit(
        context=context,
        reasoning=reasoning,
    )
    assert any(issue.startswith("Conversation provenance boundary:") for issue in issues)