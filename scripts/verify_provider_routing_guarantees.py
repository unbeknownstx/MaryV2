"""Deterministically verify MaryV2 provider routing without network calls."""

from __future__ import annotations

from mary.core.config import Config
from mary.llm.interface import LLMInterface, LLMMessage, LLMRateLimitError, LLMResponse
from mary.llm.router import LLMRouter


class FakeProvider(LLMInterface):
    def __init__(self, name: str, *, error: Exception | None = None) -> None:
        self.name = name
        self.error = error
        self.calls = 0

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return LLMResponse(
            content=f"{self.name} ok",
            provider=self.name,
            model=f"fake-{self.name}",
        )

    def is_available(self):
        return True

    def provider_name(self):
        return self.name

    def model_name(self):
        return f"fake-{self.name}"


def make_router() -> tuple[LLMRouter, dict[str, FakeProvider]]:
    config = Config()
    config.llm.provider = "groq"
    config.llm.routing_strategy = "free_first"
    config.llm.free_provider_order = ["groq", "gemini", "openrouter", "ollama"]
    config.llm.fallback_providers = ["openai"]
    router = LLMRouter(config)
    providers = {
        name: FakeProvider(name)
        for name in ("groq", "gemini", "openrouter", "ollama", "openai")
    }
    for name, provider in providers.items():
        router.register_provider(name, provider)
    return router, providers


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    message = [LLMMessage(role="user", content="routing verification")]

    print("=" * 72)
    print("MARYV2 PROVIDER ROUTING GUARANTEES")
    print("=" * 72)

    router, providers = make_router()
    response = router.generate(message)
    require(response.provider == "groq", "Groq did not win the healthy free-first route.")
    require(sum(p.calls for p in providers.values()) == 1, "Lower providers were called after Groq success.")
    print("PASS  Groq success stops failover")

    router, providers = make_router()
    providers["groq"].error = RuntimeError("groq failed")
    response = router.generate(message)
    require(response.provider == "gemini", "Gemini was not used after Groq failure.")
    print("PASS  Groq failure reaches Gemini")

    router, providers = make_router()
    providers["groq"].error = RuntimeError("groq failed")
    providers["gemini"].error = RuntimeError("gemini failed")
    response = router.generate(message)
    require(response.provider == "openrouter", "OpenRouter was not used after Groq + Gemini failure.")
    print("PASS  Groq + Gemini failure reaches OpenRouter")

    router, providers = make_router()
    for name in ("groq", "gemini", "openrouter"):
        providers[name].error = RuntimeError(f"{name} failed")
    response = router.generate(message)
    require(response.provider == "ollama", "Ollama did not receive final free-first fallback.")
    require(providers["openai"].calls == 0, "Paid OpenAI silently entered free_first.")
    print("PASS  cloud failure reaches Ollama without paid OpenAI")

    router, providers = make_router()
    response = router.generate(message, provider="openai", route="private")
    require(response.provider == "ollama", "Private route did not force Ollama.")
    require(providers["openai"].calls == 0, "Private route leaked to OpenAI.")
    print("PASS  private/offline policy is Ollama-only")

    router, providers = make_router()
    providers["groq"].error = LLMRateLimitError("quota reached", provider="groq")
    router.generate(message)
    router.generate(message)
    require(providers["groq"].calls == 1, "Cooldown retried rate-limited Groq too early.")
    require(router.last_generation_attempts[0]["status"] == "cooldown", "Cooldown metadata missing.")
    print("PASS  rate-limit cooldown preserves routing")

    router, providers = make_router()
    router.config.llm.fallback_providers = ["ollama"]
    response = router.generate(message, provider="gemini")
    require(response.provider == "gemini", "Explicit provider override was ignored.")
    require(providers["groq"].calls == 0, "Free-first Groq ran before explicit Gemini override.")
    print("PASS  explicit provider override remains intentional")

    print("=" * 72)
    print("PROVIDER ROUTING GUARANTEES VERIFIED")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
