"""Verify the current MaryV2 multi-provider routing contract."""

from mary.core.config import Config
from mary.llm.router import LLMRouter


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS  {label}")


def main() -> int:
    print("MARYV2 MULTI-PROVIDER ROUTER V2 VERIFICATION")
    print("=" * 72)

    router = LLMRouter(Config())
    for name in ("gemini", "openrouter", "ollama"):
        provider = router._create_provider(name)
        check(f"{name} provider adapter installed", provider.provider_name() == name)

    configured = Config()
    configured.llm.routing_strategy = "configured"
    configured.llm.provider = "groq"
    configured.llm.fallback_providers = ["gemini", "openrouter", "ollama", "openai"]
    check(
        "configured strategy preserves the legacy provider pool",
        LLMRouter(configured)._provider_order(None)
        == ["groq", "gemini", "openrouter", "ollama", "openai"],
    )

    free_first = Config()
    free_first.llm.routing_strategy = "free_first"
    free_first.llm.provider = "groq"
    free_first.llm.fallback_providers = ["gemini", "openrouter", "ollama", "openai"]
    order = LLMRouter(free_first)._provider_order(None)
    check("free_first excludes paid OpenAI", order == ["groq", "gemini", "openrouter", "ollama"])

    lazy = LLMRouter(Config())
    starts_empty = not lazy.providers
    lazy.get_provider("gemini")
    check(
        "providers remain lazy and configuration-driven",
        starts_empty and set(lazy.providers) == {"gemini"},
    )

    print("=" * 72)
    print("MULTI-PROVIDER ROUTER V2 INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
