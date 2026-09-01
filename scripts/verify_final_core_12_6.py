"""Verify MaryV2 12.6 final-core hardening invariants."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import IntentType
from mary.cognition.reasoning import ReasoningResult
from mary.runtime.application import create_application


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS  {label}")


def main() -> int:
    print("=" * 72)
    print("MARYV2 12.6 FINAL CORE HARDENING")
    print("=" * 72)

    original_data = os.environ.get("MARY_DATA_DIR")
    with tempfile.TemporaryDirectory(prefix="maryv2_final_core_12_6_") as directory:
        root = Path(directory)
        os.environ["MARY_DATA_DIR"] = str(root / "data")
        try:
            app = create_application()
            mary = app.mary

            check(
                "relationship state follows configured private data root",
                mary.relationship.path == root / "data" / "relationship" / "relationship.json",
            )
            check(
                "agency curiosity state follows configured private data root",
                mary.agency.curiosities.path == root / "data" / "goals" / "curiosities.json",
            )

            shared = mary.cognition.detect_intent(
                "what do you remember weve been working on together?"
            )
            check(
                "natural shared-work wording stays on grounded relationship recall",
                shared.intent_type == IntentType.RELATIONSHIP_QUERY
                and shared.parameters.get("relationship_query_type") == "shared_work",
            )

            curiosity = mary.cognition.detect_intent(
                "what are you currently curious about?"
            )
            check(
                "natural current-curiosity wording stays on grounded agency state",
                curiosity.intent_type == IntentType.SELF_QUERY
                and curiosity.parameters.get("self_query_type") == "curiosity",
            )

            architecture_opinion = mary.cognition.detect_intent(
                "i think we may have overcomplicated parts of your architecture. what do you think?"
            )
            check(
                "architecture critique remains character conversation rather than runtime dump",
                not (
                    architecture_opinion.intent_type == IntentType.SELF_QUERY
                    and architecture_opinion.parameters.get("self_query_type") == "runtime_architecture"
                ),
            )

            opinion = mary.turn_mind.build(
                input_text="What do you actually think about where we are with V2?",
                intent=mary.cognition.detect_intent(
                    "What do you actually think about where we are with V2?"
                ),
                recent_conversation=[],
                relevant_memories=[],
            ).prompt_view()["continuity"]
            check(
                "independent-opinion prompt selects opine drive",
                opinion.get("drive") == "opine" and opinion.get("allow_follow_up_question") is False,
            )

            pushback = mary.turn_mind.build(
                input_text="What would you push back on in the way I'm building you?",
                intent=mary.cognition.detect_intent(
                    "What would you push back on in the way I'm building you?"
                ),
                recent_conversation=[],
                relevant_memories=[],
            ).prompt_view()["continuity"]
            check(
                "natural pushback prompt selects disagree drive",
                pushback.get("drive") == "disagree" and pushback.get("allow_follow_up_question") is False,
            )

            live_bad_reply = (
                "Hey! I'm vibing pretty good-think of me as that bright spark that's just found a new set "
                "of colors to paint with. The project's pacing feels like a fresh rain on a windowpane, "
                "then a steady drip. Anything that feels off or that you think we could jazz up?"
            )
            audit_context = CognitiveContext(
                input_text="hey mary! how are you feeling about where we are with the project?",
                mind_state={
                    "disposition": {"mode": "relational_conversation", "follow_up_urge": 0.5},
                    "continuity": {
                        "drive": "answer",
                        "allow_follow_up_question": True,
                        "recent_mary_responses": [],
                        "recent_openings": [],
                    },
                },
            )
            issues = mary.reflection._character_audit(
                context=audit_context,
                reasoning=ReasoningResult(response=live_bad_reply),
                intent=None,
            )
            check(
                "live overdecorated/canned response is caught locally",
                any("texture boundary" in issue.lower() for issue in issues)
                and any("handoff boundary" in issue.lower() for issue in issues),
            )
        finally:
            app.close()
            if original_data is None:
                os.environ.pop("MARY_DATA_DIR", None)
            else:
                os.environ["MARY_DATA_DIR"] = original_data

    print("=" * 72)
    print("MARYV2 12.6 FINAL CORE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
