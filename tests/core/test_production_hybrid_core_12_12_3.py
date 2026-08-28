from __future__ import annotations

from types import SimpleNamespace


class _CountingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def provider_name(self) -> str:
        return "production-route-fixture"

    def model_name(self) -> str:
        return "production-route-fixture-model"

    def is_available(self) -> bool:
        return True

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        del messages, temperature, max_tokens
        from mary.llm.interface import LLMResponse

        self.calls += 1
        return LLMResponse(
            content=(
                "I don't have a represented preference about that yet, so I "
                "won't invent one."
            ),
            provider=self.provider_name(),
            model=self.model_name(),
            finish_reason="stop",
            usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )


def _isolate_mary(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MARY_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.setenv("MARY_DATA_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("MARY_LOCAL_MIND_ENABLED", "true")
    monkeypatch.setenv("MARY_LOCAL_DIALOGUE_ENABLED", "true")


def test_production_local_response_reports_v2_route_without_cognition(
    monkeypatch,
    tmp_path,
):
    _isolate_mary(monkeypatch, tmp_path)
    from mary.core.mary import Mary

    mary = Mary()
    try:
        def forbidden_cognition(**_kwargs):
            raise AssertionError("eligible local dialogue must not enter cognition")

        monkeypatch.setattr(mary.cognition, "process", forbidden_cognition)
        result = mary.process("hey mary")
    finally:
        mary.mind.close()

    reasoning = result.reasoning.metadata
    local_mind = result.metadata["local_mind"]
    assert reasoning["provider"] == "local/mind"
    assert reasoning["model"] == "local-composer-v2"
    assert reasoning["response_class"] == "social_low_risk"
    assert reasoning["response_engine"] == "local_composer_v2"
    assert reasoning["provider_attempts"] == []
    assert reasoning["provider_attempt_timings"] == []
    assert reasoning["conversation_lane"]["allow_model_revision"] is False
    assert result.reflection.metadata["mode"] == "local_mind_no_model"
    assert local_mind["response_engine"] == "local_composer_v2"
    assert set(("classification_ms", "local_composer_ms", "local_audit_ms")) <= set(
        result.metadata["timings"]
    )
    assert "delivery_plan" in result.metadata


def test_production_escalation_keeps_provider_route_and_redacts_local_semantics(
    monkeypatch,
    tmp_path,
):
    _isolate_mary(monkeypatch, tmp_path)
    from mary.cognition.context import CognitiveContext
    from mary.cognition.orchestrator import CognitiveCycleResult
    from mary.cognition.reasoning import ReasoningResult
    from mary.cognition.reflection import (
        ReflectionDecision,
        ReflectionResult,
    )
    from mary.core.mary import Mary

    mary = Mary()
    try:
        monkeypatch.setattr(
            mary.mind,
            "try_respond",
            lambda *_args, **_kwargs: SimpleNamespace(
                handled=False,
                response="",
                metadata={
                    "response_class": "open_conversation",
                    "response_engine": None,
                    "classification_ms": 0.19,
                    "local_composer_ms": 0.0,
                    "local_audit_ms": 0.0,
                    "escalation_reason": "response_risk_open_conversation",
                    "shadow_enabled": False,
                    "conversation_lane": {
                        "lane": "conversation",
                        "latency_target_ms": 3_500,
                        "allow_model_revision": False,
                    },
                    "canonical_plan": {"fact": "CANONICAL_SECRET"},
                    "plan": {
                        "act": "escalate",
                        "local": False,
                        "target_length": "brief",
                        "slots": {"fact": "SLOT_SECRET"},
                    },
                },
            ),
        )

        def provider_cycle(**kwargs):
            context = CognitiveContext(input_text=kwargs["input_text"])
            context.mind_state.update(kwargs.get("mind_state", {}))
            return CognitiveCycleResult(
                context=context,
                intent=kwargs.get("intent"),
                reasoning=ReasoningResult(
                    response="A model-backed conversational response.",
                    intent=kwargs.get("intent"),
                    metadata={
                        "provider": "groq",
                        "model": "fast-conversation-model",
                        "generation_purpose": "conversation",
                        "routing_purpose": "conversation_fast",
                        "conversation_lane": {"lane": "conversation"},
                        "provider_attempts": [
                            {"provider": "groq", "status": "success"}
                        ],
                        "provider_attempt_timings": [
                            {"elapsed_ms": 15.0, "call_ms": 14.0}
                        ],
                    },
                ),
                reflection=ReflectionResult(
                    decision=ReflectionDecision.ACCEPT,
                    confidence=1.0,
                    assessment="accepted",
                    metadata={"mode": "local_deterministic_audit"},
                ),
                final_response="A model-backed conversational response.",
                metadata={"timings": {"reasoning_ms": 15.5}},
            )

        monkeypatch.setattr(mary.cognition, "process", provider_cycle)
        result = mary.process("let's just talk about something new")
    finally:
        mary.mind.close()

    reasoning = result.reasoning.metadata
    local_mind = result.metadata["local_mind"]
    assert reasoning["provider"] == "groq"
    assert reasoning["model"] == "fast-conversation-model"
    assert reasoning["response_class"] == "open_conversation"
    assert reasoning["response_engine"] == "conversation_generation"
    assert reasoning["escalation_reason"] == "response_risk_open_conversation"
    assert reasoning["provider_attempts"][0]["provider"] == "groq"
    assert result.metadata["timings"]["reasoning_ms"] == 15.5
    assert result.metadata["timings"]["classification_ms"] == 0.19
    assert local_mind["plan"] == {
        "act": "escalate",
        "local": False,
        "target_length": "brief",
    }
    assert "canonical_plan" not in local_mind
    assert "slots" not in local_mind["plan"]
    assert "delivery_plan" in result.metadata


def test_response_risk_class_controls_existing_open_and_thinking_routes(
    monkeypatch,
    tmp_path,
):
    _isolate_mary(monkeypatch, tmp_path)
    from mary.core.mary import Mary

    mary = Mary()
    provider = _CountingProvider()
    mary.config.llm.provider = provider.provider_name()
    mary.config.llm.model = provider.model_name()
    mary.config.llm.routing_strategy = "configured"
    mary.config.llm.fallback_providers = []
    mary.llm.register_provider(provider.provider_name(), provider)

    try:
        thinking = mary.process("How do you feel about fog?")
        opened = mary.process(
            "Do constraints make conversation feel more natural or less alive?"
        )
    finally:
        mary.mind.close()

    thinking_meta = thinking.reasoning.metadata
    assert thinking_meta["response_class"] == "precision_local"
    assert thinking_meta["response_engine"] is None
    assert thinking_meta["turn_policy"]["category"] == "personal_conversation"
    assert thinking_meta["routing_purpose"] == "conversation_fast"
    assert thinking_meta["conversation_lane"]["lane"] == "conversation"
    assert thinking_meta["escalation_reason"] == "mary_preference_confirmation_missing"
    assert thinking_meta["response_risk_route_applied"] is False

    open_meta = opened.reasoning.metadata
    assert open_meta["response_class"] == "open_conversation"
    assert open_meta["response_engine"] == "conversation_generation"
    assert open_meta["turn_policy"]["category"] == "response_risk_conversation"
    assert open_meta["routing_purpose"] == "conversation_fast"
    assert open_meta["conversation_lane"]["lane"] == "conversation"
    assert open_meta["response_risk_route_applied"] is False
    assert provider.calls >= 2
