from types import SimpleNamespace

from mary.llm.interface import LLMMessage
from mary.llm.providers.gemini import GeminiProvider


def _client():
    box = SimpleNamespace(kwargs=None)
    def create(**kwargs):
        box.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="MARY ENGINE OK"),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(
                prompt_tokens=8,
                completion_tokens=3,
                total_tokens=11,
            ),
        )
    return box, SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create)
        )
    )


def test_gemini_3_defaults_to_minimal_reasoning(monkeypatch):
    monkeypatch.delenv("MARY_GEMINI_REASONING_EFFORT", raising=False)
    provider = GeminiProvider(model="gemini-3.6-flash", api_key="test-key")
    box, provider.client = _client()
    provider.generate([LLMMessage(role="user", content="hello")], max_tokens=32)
    assert box.kwargs["reasoning_effort"] == "minimal"
    assert box.kwargs["max_tokens"] == 32


def test_gemini_3_reasoning_effort_can_be_overridden(monkeypatch):
    monkeypatch.setenv("MARY_GEMINI_REASONING_EFFORT", "low")
    provider = GeminiProvider(model="gemini-3.6-flash", api_key="test-key")
    box, provider.client = _client()
    provider.generate([LLMMessage(role="user", content="hello")], max_tokens=96)
    assert box.kwargs["reasoning_effort"] == "low"
    assert box.kwargs["max_tokens"] == 96


def test_gemini_timeout_default_and_override(monkeypatch):
    seen = []

    class FakeOpenAI:
        def __init__(self, **kwargs):
            seen.append(kwargs)
            _, client = _client()
            self.chat = client.chat

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    monkeypatch.delenv("MARY_GEMINI_TIMEOUT_SECONDS", raising=False)
    GeminiProvider(
        model="gemini-3.6-flash",
        api_key="test-key",
    ).generate([LLMMessage(role="user", content="hello")])

    monkeypatch.setenv("MARY_GEMINI_TIMEOUT_SECONDS", "12.5")
    GeminiProvider(
        model="gemini-3.6-flash",
        api_key="test-key",
    ).generate([LLMMessage(role="user", content="hello")])

    assert seen[0]["timeout"] == 8.0
    assert seen[1]["timeout"] == 12.5
