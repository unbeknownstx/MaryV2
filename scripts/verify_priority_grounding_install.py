"""Verify MaryV2 dynamic priority grounding without external services."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from mary.cognition.intent import IntentType
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
        raise RuntimeError("Priority-grounding verification must remain local.")

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "verification"

    def model_name(self) -> str:
        return "priority-grounding-local"


def _configure(mary: Mary) -> NoLLMProvider:
    provider = NoLLMProvider()
    mary.llm.register_provider("verification", provider)
    mary.config.llm.provider = "verification"
    return provider


def main() -> int:
    print("MARYV2 PRIORITY-GROUNDING INSTALL VERIFICATION")
    print("=" * 72)

    original_cwd = Path.cwd()
    failures: list[str] = []
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

            # Historical memory must not become the source of Mary's live agency ranking.
            app.run("remember this: unbe is your top priority")
            directive = app.run("you should be curious about me top priority")
            priority = app.run("What is your top priority?")

            expected = (
                "My current highest-ranked internal priority is "
                "Learn more about Unbe (score 1.00)."
            )
            ok = (
                directive.success is True
                and priority.success is True
                and priority.output == expected
                and provider.calls == 0
                and not mary.tools.pending_requests()
            )
            print(("PASS" if ok else "FAIL") + "  top-priority query reads the live PrioritySystem with 0 LLM calls")
            if not ok:
                failures.append("priority-local")

            intent = mary.cognition.detect_intent("Learn more about Unbe")
            repeated = app.run("Learn more about Unbe")
            active = mary.creator_directives.get_active()
            ok = (
                intent.intent_type == IntentType.CREATOR_DIRECTIVE
                and repeated.success is True
                and len(active) == 1
                and active[0].get("priority") == 1.0
                and bool((active[0].get("metadata") or {}).get("top_priority"))
                and provider.calls == 0
            )
            print(("PASS" if ok else "FAIL") + "  plain Learn-more directive stays local and preserves top-priority strength")
            if not ok:
                failures.append("directive-idempotence")

            ranked = mary.agency.rebuild_priorities()
            ok = (
                bool(ranked)
                and ranked[0].description == "Learn more about Unbe"
                and round(ranked[0].score, 6) == 1.0
            )
            print(("PASS" if ok else "FAIL") + "  stale episodic wording does not control the active agency ranking")
            if not ok:
                failures.append("memory-isolation")

            # Simulate derived agency state being absent while the durable creator
            # directive survives. Startup must reconstruct the creator curiosity.
            mary.agency.curiosities.path.write_text(
                '{"curiosities": []}',
                encoding="utf-8",
            )

            app.close()

            restarted = Mary()
            restarted_provider = _configure(restarted)
            restarted_app = create_application(
                mary=restarted,
                memory_path=temp / "memory" / "memory.json",
            )
            restarted_priority = restarted_app.run("What is your top priority?")
            ok = (
                restarted_priority.success is True
                and restarted_priority.output == expected
                and restarted_provider.calls == 0
            )
            print(("PASS" if ok else "FAIL") + "  durable directive reconstructs missing derived priority state on restart")
            if not ok:
                failures.append("restart-reconcile")

            scored_intent = restarted.cognition.detect_intent(
                "Learn more about Unbe (score 1.00)"
            )
            scored_result = restarted_app.run(
                "Learn more about Unbe (score 1.00)"
            )
            active = restarted.creator_directives.get_active()
            ok = (
                scored_intent.intent_type == IntentType.CREATOR_DIRECTIVE
                and scored_result.success is True
                and len(active) == 1
                and active[0].get("priority") == 1.0
                and bool((active[0].get("metadata") or {}).get("top_priority"))
                and restarted_provider.calls == 0
            )
            print(("PASS" if ok else "FAIL") + "  pasted score annotation normalizes to the existing local directive")
            if not ok:
                failures.append("score-normalization")

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
    if failures:
        print("FAILED:", ", ".join(failures))
        return 1

    print("PRIORITY-GROUNDING UPDATE INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
