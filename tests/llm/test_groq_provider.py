import sys
from types import ModuleType, SimpleNamespace


if "groq" not in sys.modules:
    fake_groq = ModuleType("groq")

    class _ImportSafeGroq:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace(completions=None)

    fake_groq.Groq = _ImportSafeGroq
    sys.modules["groq"] = fake_groq

from mary.llm.interface import LLMMessage
from mary.llm.providers.groq import GroqProvider


class _FakeCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="A complete Mary reply."),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=3000,
                completion_tokens=420,
                total_tokens=3420,
                completion_tokens_details=SimpleNamespace(
                    reasoning_tokens=120,
                ),
            ),
        )


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def test_gpt_oss_uses_low_reasoning_and_completion_budget(monkeypatch):
    monkeypatch.delenv("MARY_GROQ_REASONING_EFFORT", raising=False)
    provider = GroqProvider(
        model="openai/gpt-oss-20b",
        api_key="test-key",
    )
    provider.client = _FakeClient()

    response = provider.generate(
        [LLMMessage(role="user", content="hello")],
        max_tokens=800,
    )

    request = provider.client.chat.completions.kwargs
    assert request["max_completion_tokens"] == 800
    assert request["reasoning_effort"] == "low"
    assert request["include_reasoning"] is False
    assert "max_tokens" not in request
    assert response.usage["reasoning_tokens"] == 120


def test_gpt_oss_reasoning_effort_can_be_overridden(monkeypatch):
    monkeypatch.setenv("MARY_GROQ_REASONING_EFFORT", "high")
    provider = GroqProvider(
        model="openai/gpt-oss-20b",
        api_key="test-key",
    )
    provider.client = _FakeClient()

    provider.generate(
        [LLMMessage(role="user", content="hard problem")],
        max_tokens=1200,
    )

    request = provider.client.chat.completions.kwargs
    assert request["reasoning_effort"] == "high"
    assert request["max_completion_tokens"] == 1200
