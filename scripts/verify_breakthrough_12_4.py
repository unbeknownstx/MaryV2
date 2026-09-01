from __future__ import annotations

import os
import tempfile
from pathlib import Path

from mary.cognition.intent import Intent, IntentType
from mary.runtime.application import create_application


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def _turn(app, text: str):
    return app.run(text).metadata["pipeline_values"]["cognitive_cycle"]


def main() -> None:
    print("=" * 72)
    print("MARY V2 BREAKTHROUGH 12.4 - MEMORY LIFECYCLE + SHARED HISTORY")
    print("=" * 72)

    original = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="maryv2_bt12_4_") as directory:
        os.chdir(directory)
        restarted_app = None
        try:
            app = create_application(
                memory_path=Path(directory) / "data" / "memory" / "memory.json",
                auto_save=True, load_memory=False, load_developed_self=False,
                load_preference_promotion=False, load_knowledge=False,
            )
            mary = app.mary
            query = mary.cognition.detect_intent(
                "what do you remember about what we've been working on together?"
            )
            check("shared-work query is durable relationship recall", query.intent_type == IntentType.RELATIONSHIP_QUERY)
            check("shared-work query subtype", query.parameters.get("relationship_query_type") == "shared_work")

            learned = mary._learn_shared_work_statement(
                "we've been building MaryV2 together on the MacBook",
                intent=Intent(intent_type=IntentType.CONVERSATION),
            )
            check("shared-work event recorded", bool(learned and learned.get("recorded")))

            app.close()
            restarted_app = create_application(
                memory_path=Path(directory) / "data" / "memory" / "memory.json",
                auto_save=False, load_memory=True, load_developed_self=False,
                load_preference_promotion=False, load_knowledge=False,
            )
            restarted = restarted_app.mary
            recalled = _turn(restarted_app, "what have we worked on together?")
            check("shared-work recall survives restart", "maryv2" in recalled.final_response.lower())
            check("shared-work recall remains local", recalled.reasoning.metadata.get("llm_skipped") is True)

            restarted.remember(
                "I like rainy nights when I'm working on creative projects",
                memory_type="episodic",
                importance=0.8,
                metadata={"owner": "creator", "event_type": "creator_natural_share"},
            )
            recalled_again = _turn(restarted_app, "what have we worked on together?")
            check("unrelated preference does not become project history", "rainy" not in recalled_again.final_response.lower())

            semantic = restarted.remember(
                "blue",
                memory_type="semantic",
                metadata={
                    "subject": "creator",
                    "predicate": "favorite_color",
                    "value": "blue",
                },
            )
            all_memory = restarted._all_available_memories()
            check("semantic remains visible beside episodic", semantic in all_memory and len(all_memory) >= 2)

            status = restarted.memory_lifecycle_status()
            check("normal conversation does not auto-consolidate", status["consolidation"]["automatic"] is False)
            check("memory lifecycle exposes eligible candidates", status["consolidation"]["eligible_candidates"] >= 1)
        finally:
            if restarted_app is not None:
                restarted_app.close()
            app.close()
            os.chdir(original)

    print("=" * 72)
    print("BREAKTHROUGH 12.4 VERIFIED")


if __name__ == "__main__":
    main()
