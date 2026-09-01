"""Verify MaryV2 Curiosity Development V2 without external services."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

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
        raise RuntimeError("Curiosity-development verification must remain local.")

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "verification"

    def model_name(self) -> str:
        return "curiosity-development-local"


def _configure(mary) -> NoLLMProvider:
    provider = NoLLMProvider()
    mary.llm.register_provider("verification", provider)
    mary.config.llm.provider = "verification"
    return provider


def _children(mary) -> list[dict]:
    return [
        item
        for item in mary.agency.curiosities.get_curiosities()
        if item.get("relationship_gap")
        or bool((item.get("metadata") or {}).get("relationship_gap"))
    ]


def main() -> int:
    print("MARYV2 CURIOSITY-DEVELOPMENT INSTALL VERIFICATION")
    print("=" * 72)

    original_cwd = Path.cwd()
    failures: list[str] = []
    app = None
    restarted_app = None

    with TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        try:
            os.chdir(temp)
            app = create_application(
                memory_path=temp / "memory" / "memory.json",
                auto_save=True,
            )
            mary = app.mary
            provider = _configure(mary)

            app.run("remember this: my favorite color is green")
            app.run("remember this: I love creating stories")
            directive = app.run("you should be curious about me top priority")

            children = _children(mary)
            unresolved = {
                item.get("gap_category")
                for item in children
                if item.get("status") in {"open", "exploring"}
            }
            ok = (
                directive.success is True
                and unresolved == {"goals", "values", "communication"}
                and provider.calls == 0
            )
            print(("PASS" if ok else "FAIL") + "  broad creator curiosity develops only missing relationship gaps")
            if not ok:
                failures.append("gap-development")

            query = app.run("What are you still curious about regarding me?")
            output = str(query.output).lower()
            ok = (
                query.success is True
                and "goals" in output
                and "values" in output
                and "communicate" in output
                and "not permission" in output
                and provider.calls == 0
                and not mary.tools.pending_requests()
            )
            print(("PASS" if ok else "FAIL") + "  creator-gap query is local and non-autonomous")
            if not ok:
                failures.append("local-query")

            app.run("learn this about me: my main goal is finish MaryV2")
            goal_child = next(
                item for item in _children(mary)
                if item.get("gap_category") == "goals"
            )
            updated = app.run("What are you still curious about regarding me?")
            updated_output = str(updated.output).lower()
            ok = (
                goal_child.get("status") == "resolved"
                and "what goals matter most to unbe" not in updated_output
                and "finish MaryV2" in mary.user_model.goals
                and provider.calls == 0
            )
            print(("PASS" if ok else "FAIL") + "  explicit creator learning resolves the matching curiosity gap")
            if not ok:
                failures.append("gap-resolution")

            app.run("learn this about me: I prefer you to be direct and concise")
            communication_child = next(
                item for item in _children(mary)
                if item.get("gap_category") == "communication"
            )
            ok = (
                communication_child.get("status") == "resolved"
                and mary.user_model.communication_style.get("preferred_style") == "be direct and concise"
                and provider.calls == 0
            )
            print(("PASS" if ok else "FAIL") + "  communication learning resolves its own tracked gap")
            if not ok:
                failures.append("communication")

            ranked = mary.agency.rebuild_priorities()
            ok = (
                bool(ranked)
                and ranked[0].description.lower() == "learn more about unbe"
                and round(ranked[0].score, 6) == 1.0
            )
            print(("PASS" if ok else "FAIL") + "  exploring umbrella curiosity remains the highest internal priority")
            if not ok:
                failures.append("priority")

            app.close()

            restarted_app = create_application(
                memory_path=temp / "memory" / "memory.json",
                auto_save=False,
            )
            restarted = restarted_app.mary
            restarted_provider = _configure(restarted)
            restarted_output = str(
                restarted_app.run("What are you still curious about regarding me?").output
            ).lower()
            restarted_children = _children(restarted)
            categories = [item.get("gap_category") for item in restarted_children]
            ok = (
                len(categories) == len(set(categories))
                and "what goals matter most to unbe" not in restarted_output
                and "how unbe prefers mary to communicate" not in restarted_output
                and restarted_provider.calls == 0
            )
            print(("PASS" if ok else "FAIL") + "  curiosity progress survives restart without duplicate gaps")
            if not ok:
                failures.append("restart")

        finally:
            # Disposable verification applications must release the derived
            # SQLite reservoir before Windows removes the TemporaryDirectory.
            if restarted_app is not None:
                restarted_app.close()
            if app is not None:
                app.close()
            os.chdir(original_cwd)

    print("=" * 72)
    if failures:
        print("FAILED:", ", ".join(failures))
        return 1

    print("CURIOSITY-DEVELOPMENT UPDATE INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
