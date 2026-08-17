"""Verify MaryV2's local self-introspection routing without external services."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.runtime.application import create_application


class _Fake429(Exception):
    status_code = 429


class _RateLimitedProvider(LLMInterface):
    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        raise _Fake429("simulated 429 rate limit")

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "self-introspection-verifier"

    def model_name(self) -> str:
        return "simulated-rate-limit"


CHECKS = (
    ("Who are you, and what makes you different from a generic AI assistant?", "persistent identity"),
    ("Who is Unbe to you?", "creator"),
    ("What parts of yourself do you currently understand?", "structured systems"),
    ("What are your values?", "honesty"),
    ("If Unbe tells you something you believe is a bad idea, would you disagree with him?", "challenge assumptions"),
    ("What do you think your relationship with Unbe should be?", "independence"),
    ("Do you have your own personality, or are you just copying mine?", "own explicit personality"),
    ("What are you curious about right now?", "don't currently have any open"),
    ("What do you think you should become?", "coherent as mary"),
)


def main() -> int:
    print("MARYV2 SELF-INTROSPECTION INSTALL VERIFICATION")
    print("=" * 72)

    original_cwd = Path.cwd()
    failures: list[str] = []

    with TemporaryDirectory() as temp_dir:
        try:
            os.chdir(temp_dir)
            mary = Mary()
            mary.llm.register_provider("fake", _RateLimitedProvider())
            mary.config.llm.provider = "fake"
            app = create_application(
                mary=mary,
                memory_path=Path(temp_dir) / "memory.json",
            )

            for query, expected in CHECKS:
                result = app.run(query)
                output = str(result.output or "")
                ok = (
                    result.success is True
                    and expected in output.lower()
                    and not mary.tools.pending_requests()
                )
                print(("PASS" if ok else "FAIL") + f"  {query}")
                if not ok:
                    failures.append(query)
        finally:
            # Windows cannot remove the process's current working directory.
            # Leave the temporary workspace before TemporaryDirectory cleanup.
            os.chdir(original_cwd)

    print("=" * 72)
    if failures:
        print(f"FAILED: {len(failures)} self-introspection checks")
        return 1

    print("SELF-INTROSPECTION UPDATE INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
