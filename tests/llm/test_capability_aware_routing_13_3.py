from __future__ import annotations

import json
import time

import pytest

from mary.core.config import Config
from mary.llm.interface import (
    GenerationCost,
    GenerationOperation,
    GenerationPrivacy,
    GenerationRequest,
    LLMInterface,
    LLMMessage,
    LLMProviderError,
    LLMResponse,
    ProviderRoute,
)
from mary.llm.router import LLMRouter
from mary.llm.providers.ollama import OllamaProvider


class Provider(LLMInterface):
    def __init__(
        self,
        name: str,
        *,
        failure: Exception | None = None,
        delay: float = 0,
        content: str = "ok",
    ):
        self.name = name
        self.failure = failure
        self.delay = delay
        self.content = content
        self.availability_calls = 0
        self.generation_calls = 0

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.generation_calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.failure is not None:
            raise self.failure
        return LLMResponse(content=self.content, provider=self.name, model="fake")

    def generate_constrained(self, request, *, timeout_seconds=None):
        if (
            timeout_seconds is not None
            and self.delay > timeout_seconds
        ):
            raise TimeoutError("provider deadline elapsed")
        return self.generate(
            list(request.messages),
            temperature=0.7 if request.temperature is None else request.temperature,
            max_tokens=2048 if request.max_tokens is None else request.max_tokens,
        )

    def is_available(self):
        self.availability_calls += 1
        return True

    def provider_name(self):
        return self.name

    def model_name(self):
        return "fake"


def _request(
    operation: str,
    *,
    structured_output: bool = False,
    deadline_seconds: float | None = None,
) -> GenerationRequest:
    return GenerationRequest(
        messages=(LLMMessage(role="user", content="bounded request"),),
        operation=operation,
        privacy=GenerationPrivacy.CLOUD_OK.value,
        cost_class=GenerationCost.FREE_CLOUD.value,
        structured_output=structured_output,
        deadline_seconds=deadline_seconds,
        correlation_id="task:test-1",
    )


def _router() -> LLMRouter:
    config = Config()
    config.llm.provider = "primary"
    config.llm.fallback_providers = ["secondary"]
    return LLMRouter(config)


def test_route_api_skips_provider_that_does_not_support_operation():
    router = _router()
    primary = Provider("primary")
    secondary = Provider("secondary", content='{"ok": true}')
    router.register_provider(
        "primary",
        primary,
        route_capabilities=ProviderRoute(
            operations=frozenset({GenerationOperation.CONVERSATION.value}),
        ),
    )
    router.register_provider(
        "secondary",
        secondary,
        route_capabilities=ProviderRoute(
            operations=frozenset({GenerationOperation.TOOL_PLANNING.value}),
        ),
    )
    request = _request(GenerationOperation.TOOL_PLANNING.value)

    assert router.route_order(request) == ["secondary"]
    response = router.generate_request(request)

    assert response.provider == "secondary"
    assert primary.availability_calls == 0
    assert primary.generation_calls == 0


def test_provider_that_opts_out_is_never_entered_as_fallback():
    router = _router()
    primary = Provider("primary", failure=ConnectionError("private endpoint detail"))
    secondary = Provider("secondary")
    router.register_provider("primary", primary)
    router.register_provider(
        "secondary",
        secondary,
        route_capabilities=ProviderRoute(fallback_eligible=False),
    )
    request = _request(GenerationOperation.CONVERSATION.value)

    assert router.route_order(request) == ["primary"]
    with pytest.raises(LLMProviderError) as raised:
        router.generate_request(request)

    assert raised.value.category == "unavailable"
    assert raised.value.retryable is True
    assert secondary.availability_calls == 0
    assert "private endpoint detail" not in str(raised.value)


def test_structured_output_constraint_filters_unqualified_provider():
    router = _router()
    primary = Provider("primary")
    secondary = Provider("secondary", content='{"ok": true}')
    router.register_provider("primary", primary)
    router.register_provider(
        "secondary",
        secondary,
        route_capabilities=ProviderRoute(structured_output=True),
    )

    response = router.generate_request(_request(
        GenerationOperation.TASK_GENERATION.value,
        structured_output=True,
    ))

    assert response.provider == "secondary"
    assert primary.availability_calls == 0


def test_deadline_rejects_late_provider_output_without_starting_fallback():
    router = _router()
    primary = Provider("primary", delay=0.01)
    secondary = Provider("secondary")
    router.register_provider(
        "primary",
        primary,
        route_capabilities=ProviderRoute(deadline_enforced=True),
    )
    router.register_provider("secondary", secondary)

    with pytest.raises(LLMProviderError) as raised:
        router.generate_request(_request(
            GenerationOperation.TASK_GENERATION.value,
            deadline_seconds=0.001,
        ))

    assert raised.value.category == "timeout"
    assert raised.value.retryable is True
    assert secondary.generation_calls == 0
    assert router.last_generation_attempts[-1]["status"] == "failed"
    assert router.last_generation_attempts[-1]["failure_category"] == "timeout"


def test_redact_first_cannot_route_without_trusted_message_receipt():
    with pytest.raises(ValueError, match="trusted receipt"):
        GenerationRequest(
            messages=(LLMMessage(role="user", content="private context"),),
            operation=GenerationOperation.TASK_GENERATION.value,
            privacy=GenerationPrivacy.REDACT_FIRST.value,
            cost_class=GenerationCost.FREE_CLOUD.value,
        )


def test_schema_invalid_json_falls_through_to_valid_provider():
    router = _router()
    primary = Provider("primary", content='{"wrong": true}')
    secondary = Provider("secondary", content='{"answer": "ok"}')
    capabilities = ProviderRoute(structured_output=True)
    router.register_provider(
        "primary",
        primary,
        route_capabilities=capabilities,
    )
    router.register_provider(
        "secondary",
        secondary,
        route_capabilities=capabilities,
    )
    schema = json.dumps({
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    })

    response = router.generate_request(GenerationRequest(
        messages=(LLMMessage(role="user", content="return JSON"),),
        operation=GenerationOperation.TASK_GENERATION.value,
        privacy=GenerationPrivacy.CLOUD_OK.value,
        cost_class=GenerationCost.FREE_CLOUD.value,
        structured_output=True,
        structured_schema_json=schema,
        correlation_id="schema:fallback",
    ))

    assert response.provider == "secondary"
    assert router.last_generation_attempts[0]["status"] == "invalid_output"


def test_ollama_enforces_deadline_and_schema_at_transport_boundary(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"message":{"content":"{\\"answer\\":\\"ok\\"}"},"done_reason":"stop"}'

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OllamaProvider(model="test", base_url="http://ollama.test")
    provider.timeout = 30.0
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
    }
    request = GenerationRequest(
        messages=(LLMMessage(role="user", content="return JSON"),),
        operation=GenerationOperation.TASK_GENERATION.value,
        privacy=GenerationPrivacy.LOCAL_ONLY.value,
        cost_class=GenerationCost.ZERO_LOCAL.value,
        structured_output=True,
        structured_schema_json=json.dumps(schema),
        deadline_seconds=0.25,
        correlation_id="ollama:transport-test",
    )

    response = provider.generate_constrained(request, timeout_seconds=0.2)

    assert response.content == '{"answer":"ok"}'
    assert captured["timeout"] == 0.2
    assert captured["payload"]["format"] == schema


@pytest.mark.parametrize(
    ("status_code", "category", "retryable"),
    [
        (401, "authentication", False),
        (403, "permission", False),
        (422, "invalid_request", False),
        (503, "unavailable", True),
        (504, "timeout", True),
    ],
)
def test_provider_errors_are_normalized_by_retryability(
    status_code: int,
    category: str,
    retryable: bool,
):
    router = _router()
    failure = RuntimeError("sensitive provider response body")
    failure.status_code = status_code
    router.register_provider("primary", Provider("primary", failure=failure))
    router.config.llm.fallback_providers = []

    with pytest.raises(LLMProviderError) as raised:
        router.generate_request(_request(GenerationOperation.CONVERSATION.value))

    assert raised.value.category == category
    assert raised.value.retryable is retryable
    assert raised.value.status_code == status_code
    assert "sensitive provider response body" not in str(raised.value)


def test_provider_originated_error_cannot_hide_http_authentication_failure():
    router = _router()
    failure = LLMProviderError(
        "provider response with sensitive details",
        provider="primary",
        retryable=True,
        status_code=401,
    )
    router.register_provider("primary", Provider("primary", failure=failure))
    router.config.llm.fallback_providers = []

    with pytest.raises(LLMProviderError) as raised:
        router.generate_request(_request(GenerationOperation.CONVERSATION.value))

    assert raised.value.category == "authentication"
    assert raised.value.retryable is False
    assert str(raised.value) == "provider_authentication_failed"