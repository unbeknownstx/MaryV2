"""Verify MaryV2 creator-directive integration without external services."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.runtime.application import create_application


class _Fake429(Exception):
    status_code = 429


class _RateLimitedProvider(LLMInterface):
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        self.calls += 1
        raise _Fake429("simulated 429 rate limit")

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "creator-directive-verifier"

    def model_name(self) -> str:
        return "simulated-rate-limit"


def main() -> int:
    print("MARYV2 CREATOR-DIRECTIVE INSTALL VERIFICATION")
    print("=" * 72)

    original_cwd = Path.cwd()
    failures: list[str] = []
    app = None

    with TemporaryDirectory() as temp_dir:
        try:
            os.chdir(temp_dir)
            app = create_application(
                memory_path=Path(temp_dir) / "memory" / "memory.json",
                auto_save=True,
            )
            mary = app.mary
            provider = _RateLimitedProvider()
            mary.llm.register_provider("fake", provider)
            mary.config.llm.provider = "fake"
            mary.config.llm.fallback_providers = []

            directive = app.run("you should be curious about me top priority")
            ok = (
                directive.success is True
                and "creator-directed curiosity" in str(directive.output).lower()
                and provider.calls == 0
                and len(mary.creator_directives.get_active()) == 1
                and len([
                    item
                    for item in mary.agency.curiosities.get_open_curiosities()
                    if str(item.get("description", "")).lower() == "learn more about unbe"
                ]) == 1
                and any(
                    item.get("relationship_gap")
                    for item in mary.agency.curiosities.get_open_curiosities()
                )
            )
            print(("PASS" if ok else "FAIL") + "  explicit directive uses local state with 0 LLM calls")
            if not ok:
                failures.append("directive")

            curiosity = app.run("What are you curious about right now?")
            ok = (
                curiosity.success is True
                and "learn more about unbe" in str(curiosity.output).lower()
                and not mary.tools.pending_requests()
            )
            print(("PASS" if ok else "FAIL") + "  curiosity self-query reflects creator directive")
            if not ok:
                failures.append("curiosity")

            priority = app.run("What is your top priority?")
            ok = (
                priority.success is True
                and "learn more about unbe" in str(priority.output).lower()
                and not mary.tools.pending_requests()
            )
            print(("PASS" if ok else "FAIL") + "  priority self-query reflects creator directive")
            if not ok:
                failures.append("priority")

            restarted_app = create_application(
                memory_path=Path(temp_dir) / "memory" / "memory.json",
                auto_save=False,
            )
            restarted = restarted_app.mary
            ok = (
                len(restarted.creator_directives.get_active()) == 1
                and any(
                    str(item.get("description", "")).lower() == "learn more about unbe"
                    for item in restarted.agency.curiosities.get_open_curiosities()
                )
            )
            print(("PASS" if ok else "FAIL") + "  directive and curiosity survive restart")
            if not ok:
                failures.append("restart")

            memory_intent = mary.cognition.detect_intent(
                "remember this: unbe is your top priority"
            )
            ok = memory_intent.intent_type.value == "memory_store"
            print(("PASS" if ok else "FAIL") + "  remember-this remains ordinary memory")
            if not ok:
                failures.append("memory-separation")
        finally:
            if app is not None:
                app.close()
            if 'restarted_app' in locals():
                restarted_app.close()
            os.chdir(original_cwd)

    print("=" * 72)
    if failures:
        print("FAILED:", ", ".join(failures))
        return 1

    print("CREATOR-DIRECTIVE UPDATE INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
