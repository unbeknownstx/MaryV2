"""Print Mary's configured LLM routes without revealing API keys."""

from __future__ import annotations

from dotenv import load_dotenv

from mary.core.config import Config
from mary.llm.router import LLMRouter


def main() -> None:
    load_dotenv()

    config = Config.from_environment()
    router = LLMRouter(config)

    print("MARY V2 LLM ROUTES")
    print("=" * 72)
    print(f"Strategy: {router.routing_strategy()}")
    print(
        "Order:    "
        + " -> ".join(
            router._provider_order(None)
        )
    )
    print()

    for name in router._provider_order(None):
        try:
            provider = router.get_provider(name)
            available = bool(provider.is_available())
            model = provider.model_name()
        except Exception as exc:
            available = False
            model = f"unavailable ({type(exc).__name__})"

        status = "READY" if available else "NOT CONFIGURED"
        print(f"{name:10} {status:15} {model}")

    print()
    print("Private/offline route: ollama only")
    print("Paid OpenAI route: excluded from free_first")


if __name__ == "__main__":
    main()
