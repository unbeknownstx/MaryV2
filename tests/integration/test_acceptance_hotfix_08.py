from __future__ import annotations

import pytest

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import IntentType
from mary.cognition.reasoning import ReasoningResult
from mary.core.config import Config
from mary.core.mary import Mary
from mary.expression.emotion import Emotion
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.llm.router import LLMRouter
from mary.runtime.application import MaryApplication, create_application


_applications: list[MaryApplication] = []


def _run(app: MaryApplication, input_text: str):
    return app.run(input_text).metadata["pipeline_values"]["cognitive_cycle"]


def _application() -> MaryApplication:
    app = create_application(
        auto_save=False, load_memory=False, load_developed_self=False,
        load_preference_promotion=False, load_knowledge=False,
    )
    _applications.append(app)
    return app


@pytest.fixture(autouse=True)
def _close_applications():
    yield
    while _applications:
        _applications.pop().close()


class FakeProvider(LLMInterface):
    def __init__(self, name: str, content: str | None = None) -> None:
        self.name = name
        self.content = content or f"{name} response"
        self.calls = 0
        self.available = True

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        return LLMResponse(
            content=self.content,
            provider=self.name,
            model=f"fake-{self.name}",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

    def is_available(self):
        return self.available

    def provider_name(self):
        return self.name

    def model_name(self):
        return f"fake-{self.name}"


def _router() -> tuple[LLMRouter, dict[str, FakeProvider]]:
    config = Config()
    config.llm.provider = "groq"
    config.llm.routing_strategy = "free_first"
    config.llm.free_provider_order = ["groq", "gemini", "openrouter", "ollama"]
    router = LLMRouter(config)
    providers = {
        name: FakeProvider(name)
        for name in ("groq", "gemini", "openrouter", "ollama", "openai")
    }
    for name, provider in providers.items():
        router.register_provider(name, provider)
    return router, providers


def _message():
    return [LLMMessage(role="user", content="acceptance hotfix 08")]


def test_session_private_override_actually_routes_ordinary_generation_to_ollama():
    router, providers = _router()
    router.set_session_override(route="private")

    response = router.generate(_message())

    assert response.provider == "ollama"
    assert providers["ollama"].calls == 1
    assert providers["groq"].calls == 0
    assert router.session_override_status() == {"provider": None, "route": "private"}


def test_clearing_session_override_returns_to_free_first():
    router, providers = _router()
    router.set_session_override(route="private")
    assert router.generate(_message()).provider == "ollama"

    router.clear_session_override()
    assert router.generate(_message()).provider == "groq"
    assert providers["groq"].calls == 1


def test_normal_slash_free_first_wording_clears_local_only_and_restores_cloud(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    router, providers = _router()

    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.expert_consultant.router = router
    mary.task_orchestrator.router = router
    mary.task_executor.router = router

    enabled = _run(app, "go ahead and use ollama my local llm")
    local_answer = _run(app, "idk i just wanna talk for a bit")
    providers["ollama"].available = False
    cleared = _run(app, "Use the normal/free-first route.")
    cloud_answer = _run(app, "i still just wanna talk for a bit")

    assert "Local-only generation is active" in enabled.final_response
    assert local_answer.reasoning.metadata["provider"] == "ollama"
    assert cleared.reasoning.metadata["llm_skipped"] is True
    assert "normal routing policy is active again" in cleared.final_response
    assert router.session_override_status() == {"provider": None, "route": None}
    assert cloud_answer.reasoning.metadata["provider"] == "groq"
    assert providers["ollama"].calls >= 1
    assert providers["groq"].calls >= 1


def test_explicit_expert_route_beats_private_session_override():
    router, providers = _router()
    router.set_session_override(route="private")

    response = router.generate(_message(), route="expert")

    assert response.provider == "openai"
    assert providers["openai"].calls == 1
    assert providers["ollama"].calls == 0


def test_natural_local_model_command_routes_to_llm_control(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary

    intent = mary.cognition.detect_intent(
        "cheeky go ahead and use ollama my local llm i give you permission"
    )

    assert intent.intent_type == IntentType.TOOL_USE
    assert intent.parameters["action"] == "llm_control"
    assert intent.parameters["operation"] == "set_session"
    assert intent.parameters["route"] == "private"


def test_local_model_capability_question_does_not_change_route(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary

    intent = mary.cognition.detect_intent("can you use local llm?")

    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == "runtime_architecture"
    assert mary.llm.session_override_status() == {"provider": None, "route": None}


def test_explicit_openai_command_is_one_task_paid_expert_intent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary

    intent = mary.cognition.detect_intent(
        "no fr go ahead and call open ai and think bigger about this"
    )

    assert intent.intent_type == IntentType.TOOL_USE
    assert intent.parameters["action"] == "llm_control"
    assert intent.parameters["operation"] == "paid_expert_once"
    assert intent.parameters["paid_authorized"] is True


def test_process_local_route_control_changes_router_without_model_call(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary

    result = _run(app, "go ahead and use ollama my local llm")

    assert mary.llm.session_override_status()["route"] == "private"
    assert "Local-only generation is active" in result.final_response
    assert result.reasoning.metadata.get("llm_skipped") is True


def test_pronoun_followup_after_route_change_becomes_runtime_self_query(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    mary.llm.set_session_override(route="private")

    intent = mary._detect_intent("you are using it arent you")

    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == "runtime_architecture"


def test_false_current_ollama_claim_is_audited(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    context = CognitiveContext(input_text="are you using ollama?")
    reasoning = ReasoningResult(
        response="Yeah, I'm on the local LLM now—no cloud detour.",
        metadata={"provider": "groq"},
    )

    issues = mary.reflection._provider_action_truth_audit(context, reasoning)

    assert issues
    assert "Capability-truth boundary" in issues[0]


def test_recorded_openai_expert_evidence_allows_truthful_consultation_claim(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    context = CognitiveContext(
        input_text="go ahead and call openai",
        relevant_knowledge=[{
            "expert_consultation": True,
            "provider": "openai",
            "model": "fake-openai",
            "content": "expert analysis",
        }],
    )
    reasoning = ReasoningResult(
        response="I asked OpenAI for a second pass, and the useful part was its critique.",
        metadata={"provider": "groq"},
    )

    assert mary.reflection._provider_action_truth_audit(context, reasoning) == []


def test_simple_disagreement_cannot_be_reframed_as_hiding(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    context = CognitiveContext(input_text="hmm maybe but i dont agree")

    issues = mary.reflection._unsupported_creator_mindreading_audit(
        context,
        "You're sidestepping the real issue. That feels like hiding.",
    )

    assert issues
    assert "hidden motive" in issues[0]


def test_correction_selects_reflect_and_reanchor_instruction(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    snapshot = mary.continuity.build(
        input_text="thats not really what i meant",
        intent_type=IntentType.CONVERSATION,
        recent_conversation=[{"role": "assistant", "content": "Maybe it's interface lag."}],
    )

    assert snapshot.drive.value == "reflect"
    assert any("Drop the prior hypothesis" in item for item in snapshot.instructions)


def test_disagreement_or_correction_produces_attentive_curiosity(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    appraisal = mary.emotion_appraiser.appraise(
        input_text="hmm maybe but i dont agree",
        response_text="",
        intent=mary.cognition.detect_intent("hmm maybe but i dont agree"),
    )

    assert appraisal.emotion == Emotion.CURIOSITY
    assert appraisal.relationship_relevance >= 0.9


def test_relationship_feeling_fallback_is_not_blank_when_emotion_meter_is_neutral(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    evidence = mary.self_introspection.build("relationship_feelings", query="what do u feel when we talk")
    fallback = evidence["fallback_response"].lower()

    assert "steady" in fallback
    assert "care" in fallback
    assert "relationship context" in fallback


def test_explicit_openai_request_executes_exactly_one_paid_expert_call_then_mary_synthesizes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    router, providers = _router()
    providers["openai"].content = (
        "The deeper issue is capability truth: distinguish the feeling of continuity from verified runtime actions."
    )
    providers["groq"].content = (
        "Yeah. The deeper version is that continuity can feel personal, but I still need to stay honest about what my runtime actually did."
    )

    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.expert_consultant.router = router
    mary.task_orchestrator.router = router
    mary.task_executor.router = router

    result = _run(app,
        "no fr go ahead and call open ai and think bigger about what this interaction feels like"
    )

    assert providers["openai"].calls == 1
    assert router.resource_governor.paid_calls == 1
    assert result.reasoning.metadata["expert_consultation"]["provider"] == "openai"
    assert result.reasoning.metadata["provider"] == "groq"
    assert "deeper" in result.final_response.lower()


def test_mary_route_command_makes_next_real_generation_use_ollama(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
    router, providers = _router()
    providers["ollama"].content = "A fish is an aquatic vertebrate that typically breathes through gills."

    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.expert_consultant.router = router
    mary.task_orchestrator.router = router
    mary.task_executor.router = router

    control = _run(app, "go ahead and use ollama my local llm")
    answer = _run(app, "what is a fish?")

    assert "Local-only generation is active" in control.final_response
    assert answer.reasoning.metadata["provider"] == "ollama"
    assert providers["ollama"].calls >= 1
    assert providers["groq"].calls == 0
