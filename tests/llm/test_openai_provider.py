from __future__ import annotations

from types import SimpleNamespace

from mary.llm.interface import LLMMessage
from mary.llm.providers.openai import OpenAIProvider


class FakeResponses:
    def __init__(self, response):
        self.response = response
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return self.response


class FakeClient:
    def __init__(self, response):
        self.responses = FakeResponses(response)


def _response(*, status="completed", reason=None):
    return SimpleNamespace(
        status=status,
        incomplete_details=(
            SimpleNamespace(reason=reason)
            if reason is not None
            else None
        ),
        output_text="expert answer",
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=40,
            total_tokens=140,
            input_tokens_details=SimpleNamespace(cached_tokens=20),
            output_tokens_details=SimpleNamespace(reasoning_tokens=10),
        ),
    )


def _provider(response):
    provider = OpenAIProvider(model="gpt-5.6-luna")
    provider.api_key = "test-key"
    provider.client = FakeClient(response)
    return provider


def test_openai_provider_uses_responses_api_shape_and_does_not_store():
    provider = _provider(_response())

    result = provider.generate(
        [
            LLMMessage(role="system", content="External expert only."),
            LLMMessage(role="user", content="Review this design."),
        ],
        max_tokens=500,
    )

    request = provider.client.responses.request
    assert request["model"] == "gpt-5.6-luna"
    assert request["instructions"] == "External expert only."
    assert request["input"] == [
        {"role": "user", "content": "Review this design."},
    ]
    assert request["max_output_tokens"] == 500
    assert request["store"] is False
    assert request["reasoning"] == {"effort": "low"}
    assert result.content == "expert answer"
    assert result.finish_reason == "stop"
    assert result.usage == {
        "prompt_tokens": 100,
        "completion_tokens": 40,
        "total_tokens": 140,
        "cached_tokens": 20,
        "reasoning_tokens": 10,
    }


def test_openai_provider_maps_incomplete_output_limit_for_router_failover():
    provider = _provider(
        _response(status="incomplete", reason="max_output_tokens")
    )

    result = provider.generate(
        [LLMMessage(role="user", content="Review this design.")],
    )

    assert result.finish_reason == "max_output_tokens"


def test_openai_provider_defaults_to_low_cost_luna_and_low_reasoning():
    provider = OpenAIProvider()

    assert provider.model_name() == "gpt-5.6-luna"
    assert provider.reasoning_effort == "low"
