from types import SimpleNamespace

import mary.cognition.reasoning as reasoning_module
from mary.cognition.context import CognitiveContext
from mary.cognition.deliberation import DeliberationExecutor
from mary.cognition.reasoning import ReasoningEngine
from mary.llm.interface import LLMResponse


class _Router:
    last_generation_attempts = [{"provider": "groq", "status": "success"}]
    last_generation_attempt_timings = []

    def conversation_provider_order(self):
        return ["groq", "gemini", "openrouter", "ollama"]


def _context(*, strategy="branch_verify"):
    return CognitiveContext(
        input_text="Compare two architecture choices and recommend the safer design.",
        mind_state={
            "runtime_coordination": {
                "deliberation": {
                    "strategy": strategy,
                    "max_passes": 3,
                    "max_branches": 2,
                    "confidence_floor": 0.84,
                    "latency_budget_ms": 12000,
                },
            },
            "disposition": {"preferred_length": "natural"},
            "conversation_engagement": {"effective_mode": "adaptive"},
        },
    )


def test_live_deliberation_executes_bounded_verify_once_without_extra_good_call(monkeypatch):
    calls = []

    def _dispatch(router, request):
        calls.append(request)
        return LLMResponse(
            content="Use the simpler authority boundary and keep optional workers replaceable.",
            provider="groq",
            model="openai/gpt-oss-20b",
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        )

    monkeypatch.setattr(reasoning_module, "dispatch_generation", _dispatch)
    engine = ReasoningEngine(
        _Router(),
        deliberation_executor=DeliberationExecutor(),
    )

    result = engine.reason(_context())

    assert len(calls) == 1
    assert calls[0].cost_class == "free_cloud"
    execution = result.metadata["deliberation_execution"]
    assert execution["requested_strategy"] == "branch_verify"
    assert execution["executed_strategy"] == "verify_once"
    assert execution["passes"] == 1
    assert execution["verifier_calls"] == 1
    assert execution["private_reasoning_retained"] is False


def test_live_deliberation_revises_once_after_structural_quality_failure(monkeypatch):
    outputs = ["", "Use the canonical Core and keep model workers replaceable."]

    def _dispatch(router, request):
        content = outputs.pop(0)
        return LLMResponse(
            content=content,
            provider="groq",
            model="openai/gpt-oss-20b",
            finish_reason="stop",
            usage={"prompt_tokens": 80, "completion_tokens": 10, "total_tokens": 90},
        )

    monkeypatch.setattr(reasoning_module, "dispatch_generation", _dispatch)
    engine = ReasoningEngine(
        _Router(),
        deliberation_executor=DeliberationExecutor(),
    )

    result = engine.reason(_context(strategy="verify_once"))

    assert result.response.startswith("Use the canonical Core")
    execution = result.metadata["deliberation_execution"]
    assert execution["passes"] == 2
    assert execution["verifier_calls"] == 2
    assert execution["executed_strategy"] == "verify_once"
