"""Verify MaryV2's intentional paid OpenAI expert bridge without network use."""

from __future__ import annotations

from mary.core.config import Config
from mary.core.mary import Mary
from mary.llm.router import LLMRouter


def _pass(message: str) -> None:
    print(f"PASS  {message}")


def main() -> int:
    print("=" * 72)
    print("MARYV2 OPENAI EXPERT BRIDGE VERIFICATION")
    print("=" * 72)

    config = Config()
    config.llm.routing_strategy = "free_first"
    router = LLMRouter(config)

    assert router._provider_order(None) == [
        "groq", "gemini", "openrouter", "ollama"
    ]
    _pass("paid OpenAI remains excluded from free_first")

    assert router._provider_order(None, route="expert") == ["openai"]
    _pass("expert route intentionally selects OpenAI only")

    assert router._provider_order(None, route="private") == ["ollama"]
    _pass("private/offline policy still forces Ollama")

    assert router.model_name("openai") == "gpt-5.6-luna"
    _pass("low-cost GPT-5.6 Luna is the default paid expert model")

    mary = Mary()
    assert mary.expert_consultant.workspace is mary.task_workspace
    assert mary.expert_consultant.router is mary.llm
    _pass("Mary's expert consultant shares her router and ephemeral task workspace")

    status = mary.status()["orchestration"]["expert_consultant"]
    assert status["authority"] == "advisory_only"
    assert status["persistence"] == "task_workspace_only"
    _pass("expert output is advisory and task-local, not durable self-state")

    print("=" * 72)
    print("OPENAI EXPERT BRIDGE INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
