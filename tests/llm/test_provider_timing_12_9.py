from __future__ import annotations

from mary.core.config import Config
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.llm.router import LLMRouter


class TimedFakeProvider(LLMInterface):
    def provider_name(self) -> str:
        return "groq"

    def is_available(self) -> bool:
        return True

    def model_name(self) -> str:
        return "timed-fake"

    def generate(self, messages, temperature=None, max_tokens=None):
        return LLMResponse(
            content="hello",
            provider="groq",
            model="timed-fake",
            finish_reason="stop",
            usage={},
        )


def test_router_records_attempt_and_provider_call_latency():
    config = Config()
    config.llm.provider = "groq"
    config.llm.free_provider_order = ["groq", "ollama"]
    router = LLMRouter(config)
    router.providers["groq"] = TimedFakeProvider()
    response = router.generate([LLMMessage(role="user", content="hello")])
    assert response.content == "hello"
    attempt = router.last_generation_attempts[-1]
    timing = router.last_generation_attempt_timings[-1]
    assert attempt["provider"] == "groq"
    assert attempt["status"] == "success"
    assert attempt["attempt"] == 1
    assert "error" not in attempt
    assert timing["status"] == "success"
    assert timing["call_ms"] >= 0
    assert timing["elapsed_ms"] >= timing["call_ms"]
