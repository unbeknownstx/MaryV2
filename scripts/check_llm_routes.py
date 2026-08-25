"""Inspect Mary's LLM routes without revealing API keys.

Default mode is configuration-only and makes no provider requests.
Use ``--live`` to make one tiny request to each configured free cloud provider
and print a sanitized failure reason when a provider cannot generate.
"""

from __future__ import annotations

import argparse
import os
import re
import time

from dotenv import load_dotenv

from mary.core.config import Config
from mary.llm.interface import LLMMessage
from mary.llm.output_quality import inspect_output_quality
from mary.llm.router import LLMRouter


_SECRET_ENV_NAMES = (
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
)

_SECRET_SHAPES = (
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{20,}"),
)


def _sanitize(value: object, *, limit: int = 700) -> str:
    """Return diagnostic text with known credential material removed."""

    text = str(value or "").replace("\n", " ").replace("\r", " ")
    for name in _SECRET_ENV_NAMES:
        secret = os.getenv(name, "")
        if secret:
            text = text.replace(secret, "<redacted>")
    for pattern in _SECRET_SHAPES:
        text = pattern.sub("<redacted>", text)
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text


def _exception_status(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    return str(status) if status is not None else "n/a"


def _provider_for_live_probe(
    router: LLMRouter,
    name: str,
):
    # Match Mary's real short-conversation Groq lane. Other providers do not
    # currently have a purpose-specific model instance.
    if name == "groq":
        return router._get_provider_for_purpose(
            "groq",
            "social_instant",
        )
    return router.get_provider(name)


def _live_probe(router: LLMRouter, name: str) -> None:
    try:
        provider = _provider_for_live_probe(router, name)
    except Exception as exc:
        print(
            f"{name:10} LIVE FAIL       create "
            f"{type(exc).__name__} status={_exception_status(exc)} "
            f"{_sanitize(exc)}"
        )
        return

    try:
        available = bool(provider.is_available())
    except Exception as exc:
        print(
            f"{name:10} LIVE FAIL       availability "
            f"{type(exc).__name__} status={_exception_status(exc)} "
            f"{_sanitize(exc)}"
        )
        return

    if not available:
        print(f"{name:10} LIVE SKIP       not configured")
        return

    messages = [
        LLMMessage(
            role="user",
            content=(
                "Reply with one short natural sentence confirming that this "
                "language-model route is working."
            ),
        )
    ]
    started = time.perf_counter()
    try:
        response = provider.generate(
            messages,
            temperature=0.2,
            max_tokens=48,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        print(
            f"{name:10} LIVE FAIL       {elapsed_ms:8.0f} ms  "
            f"{provider.model_name()}  {type(exc).__name__} "
            f"status={_exception_status(exc)}  {_sanitize(exc)}"
        )
        return

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    issue = inspect_output_quality(response.content, messages)
    if issue is not None:
        print(
            f"{name:10} LIVE INVALID    {elapsed_ms:8.0f} ms  "
            f"{response.model}  {issue.code}: {issue.description}"
        )
        return

    print(
        f"{name:10} LIVE OK         {elapsed_ms:8.0f} ms  "
        f"{response.model}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show MaryV2 LLM route configuration and optional live health.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "make one small request to each configured free cloud provider; "
            "this can consume provider quota"
        ),
    )
    args = parser.parse_args()

    load_dotenv()

    config = Config.from_environment()
    router = LLMRouter(config)

    task_order = router._provider_order(None)
    conversation_order = router.conversation_provider_order()

    print("MARY V2 LLM ROUTES")
    print("=" * 72)
    print(f"Strategy: {router.routing_strategy()}")
    print("Task:     " + " -> ".join(task_order))
    print("Chat:     " + " -> ".join(conversation_order))
    print()

    names: list[str] = []
    for name in task_order + conversation_order:
        if name not in names:
            names.append(name)

    for name in names:
        try:
            provider = router.get_provider(name)
            available = bool(provider.is_available())
            model = provider.model_name()
        except Exception as exc:
            available = False
            model = f"unavailable ({type(exc).__name__})"

        status = "READY" if available else "NOT CONFIGURED"
        print(f"{name:10} {status:15} {model}")

        if name == "groq":
            try:
                chat_provider = router._get_provider_for_purpose(
                    "groq",
                    "social_instant",
                )
                chat_model = chat_provider.model_name()
            except Exception as exc:
                chat_model = f"unavailable ({type(exc).__name__})"
            if chat_model != model:
                print(f"{'':10} {'CHAT MODEL':15} {chat_model}")

    print()
    print("Private/offline route: ollama only")
    expert_order = router._provider_order(None, route="expert")
    expert_name = expert_order[0] if expert_order else "unknown"
    try:
        expert = router.get_provider(expert_name)
        expert_ready = bool(expert.is_available())
        expert_model = expert.model_name()
    except Exception:
        expert_ready = False
        expert_model = router.model_name(expert_name)
    expert_status = "READY" if expert_ready else "NOT CONFIGURED"
    print(
        f"Paid expert route: {expert_name} / {expert_model} "
        f"({expert_status})"
    )
    print("Paid OpenAI route: excluded from free_first")

    if not args.live:
        print()
        print("Configuration check only; no LLM requests were made.")
        print("Use --live for sanitized provider-by-provider network diagnostics.")
        return

    print()
    print("LIVE FREE-PROVIDER CHECK")
    print("=" * 72)
    print("One small generation request is made per configured free cloud provider.")
    for name in ("groq", "gemini", "openrouter"):
        _live_probe(router, name)


if __name__ == "__main__":
    main()
