"""Verify the MaryV2 Relationship Development V2 installation."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.runtime.application import create_application


class NoLLMProvider(LLMInterface):
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        self.calls += 1
        raise RuntimeError("Relationship verifier should not need an LLM.")

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "verification"

    def model_name(self) -> str:
        return "relationship-local"


def _configure(mary: Mary) -> NoLLMProvider:
    provider = NoLLMProvider()
    mary.llm.register_provider("verification", provider)
    mary.config.llm.provider = "verification"
    return provider


def main() -> int:
    print("MARYV2 RELATIONSHIP-DEVELOPMENT INSTALL VERIFICATION")
    print("=" * 72)

    original_cwd = Path.cwd()
    app = None
    restarted_app = None
    with TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        try:
            os.chdir(temp)

            mary = Mary()
            provider = _configure(mary)
            app = create_application(
                mary=mary,
                memory_path=temp / "memory" / "memory.json",
            )

            app.run("you should be curious about me top priority")
            app.run("remember this: I love creating stories")
            app.run("remember this: my favorite color is blue")
            app.run("remember this: my favorite color is green")
            app.run("learn this about me: my goal is finish MaryV2")

            if provider.calls != 0:
                raise AssertionError("relationship-local operations called the LLM")
            print("PASS  explicit creator learning uses 0 LLM calls")

            if "creating stories" not in [item.lower() for item in mary.user_model.interests]:
                raise AssertionError("creator interest not structured")
            if mary.user_model.preferences.get("favorite_color") != "green":
                raise AssertionError("latest creator preference not current")
            if "finish MaryV2" not in mary.user_model.goals:
                raise AssertionError("creator goal not structured")
            print("PASS  interests, preferences, and goals enter the structured creator model")

            history = mary.user_model.get_profile_records(
                category="preference",
                current_only=False,
            )
            if [item.get("status") for item in history] != ["historical", "current"]:
                raise AssertionError("preference history was not preserved")
            print("PASS  current creator facts supersede without deleting history")

            query = app.run("What do you know about me?")
            if not query.success or "creating stories" not in str(query.output).lower():
                raise AssertionError("structured creator query failed")
            if provider.calls != 0:
                raise AssertionError("creator model query called the LLM")
            print("PASS  structured creator queries are local and deterministic")

            curiosity = mary.agency.curiosities.get_exploring_curiosities()
            if not curiosity or curiosity[0].get("progress_count", 0) < 1:
                raise AssertionError("creator curiosity did not record learning progress")
            print("PASS  relationship learning advances the creator curiosity")

            mary_values = [item["name"] for item in mary.values.get_priorities()]
            app.run("remember this: I value patience")
            if "patience" not in [item.lower() for item in mary.user_model.values]:
                raise AssertionError("creator value not recorded")
            if [item["name"] for item in mary.values.get_priorities()] != mary_values:
                raise AssertionError("creator values leaked into Mary's own values")
            print("PASS  Unbe's structured values remain separate from Mary's values")

            app.close()

            restarted = Mary()
            restarted_provider = _configure(restarted)
            restarted_app = create_application(
                mary=restarted,
                memory_path=temp / "memory" / "memory.json",
            )
            restarted_query = restarted_app.run("What do you know about me?")
            output = str(restarted_query.output).lower()
            if "creating stories" not in output or "favorite color: green" not in output:
                raise AssertionError("relationship model did not survive restart")
            if restarted_provider.calls != 0:
                raise AssertionError("restart query called the LLM")
            print("PASS  structured creator understanding survives restart")

        finally:
            # Disposable verification applications must release the derived
            # SQLite reservoir before Windows removes the TemporaryDirectory.
            if restarted_app is not None:
                restarted_app.close()
            if app is not None:
                try:
                    app.mary.mind.close()
                except Exception:
                    pass
            os.chdir(original_cwd)

    print("=" * 72)
    print("RELATIONSHIP-DEVELOPMENT UPDATE INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
