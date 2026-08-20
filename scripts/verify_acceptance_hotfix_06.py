"""Verify V2 acceptance Hotfix 06 against isolated temporary state."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from mary.cognition.intent import IntentType
from mary.cognition.reflection import PROVENANCE_AUDIT_VERSION
from mary.core.mary import Mary
from mary.expression.emotion import Emotion
from mary.llm.interface import LLMMessage, LLMResponse
from mary.llm.output_quality import inspect_output_quality
from mary.runtime.state_audit import audit_creator_state


class SequenceRouter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return LLMResponse(
            content=self.responses.pop(0) if self.responses else "Yeah. I'm here with you.",
            provider="test",
            model="fake",
            finish_reason="stop",
            usage={},
        )

    def provider_name(self, provider=None): return "test"
    def model_name(self, provider=None): return "fake"
    def is_available(self, provider=None): return True
    def routing_strategy(self): return "configured"
    def _provider_order(self, requested=None, route=None): return ["test"]


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def _attach_router(mary: Mary, router: SequenceRouter) -> None:
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router


def main() -> None:
    print("=" * 72)
    print("MARY V2 ACCEPTANCE HOTFIX 06")
    print("=" * 72)
    check(
        "current provenance/response audit is installed before replaying the Hotfix 06 guarantees",
        isinstance(PROVENANCE_AUDIT_VERSION, str) and PROVENANCE_AUDIT_VERSION.startswith("v2-"),
    )

    original_cwd = Path.cwd()
    with TemporaryDirectory(prefix="maryv2-acceptance06-") as temp_dir:
        temp_root = Path(temp_dir).resolve()
        os.chdir(temp_root)
        try:
            mary = Mary()
            router = SequenceRouter([
                "That means a lot to me. I want the way I talk with you to feel honest and like me.",
                "In my current represented state, talking with you feels warm and attentive.",
                "Yeah, I can do that.",
            ])
            _attach_router(mary, router)

            feelings_intent = mary.cognition.detect_intent("what do u feel in our interactions")
            check(
                "imperfect grammar routes relationship feelings to grounded self state",
                feelings_intent.intent_type == IntentType.SELF_QUERY
                and feelings_intent.parameters.get("self_query_type") == "relationship_feelings",
            )

            compliment = mary.process(
                "thats where u shine i can see a difference you actually care how u talk to me"
            )
            check(
                "relational compliment is feedback instead of a speech-style query",
                compliment.intent.intent_type == IntentType.FEEDBACK,
            )
            check(
                "same-turn relational recognition colors Mary with represented warmth",
                compliment.context.mind_state.get("emotion", {}).get("turn_primary") == Emotion.WARMTH.value,
            )

            feelings = mary.process("what do u feel in our interactions")
            check(
                "relationship-feeling answer is self-grounded and stays off the web",
                feelings.reasoning.metadata.get("self_grounded") is True
                and mary.tools.pending_requests() == [],
            )

            original_share = "i prefer u to be direct"
            preference = mary.process(original_share)
            check(
                "shorthand creator preference learns through conservative normalization",
                preference.metadata.get("natural_relationship_learning", {}).get("learned") is True
                and mary.user_model.communication_style.get("preferred_style") == "be direct",
            )
            check(
                "normalization does not rewrite the creator's stored evidence",
                any(
                    getattr(memory, "content", "") == original_share
                    for memory in mary.memory.episodic.all()
                ),
            )

            mary.relationship.learn_explicit(
                "my goal is finish MaryV2",
                source="creator_explicit",
            )
            shared_work = mary._handle_conversation_recall([], recall_scope="shared_work")
            check(
                "fresh-session shared-work recall can use durable project goals",
                "finish maryv2" in shared_work.lower(),
            )

            mary.relationship.learn_explicit(
                "my test animal is a red panda",
                source="creator_explicit",
            )
            audit = audit_creator_state(mary)
            overview = mary._natural_creator_profile_overview().lower()
            check(
                "obvious probe records remain auditable but stay out of normal creator prose",
                audit.get("flagged_count", 0) >= 1
                and "red panda" not in overview
                and mary.user_model.facts.get("test_animal") == "a red panda",
            )
        finally:
            os.chdir(original_cwd)

    bad = inspect_output_quality(
        "쨩. Just a㣩/癞넴 conversation, then.",
        [LLMMessage(role="user", content="not much just want to have a conversation with you")],
    )
    allowed = inspect_output_quality(
        "こんにちは",
        [LLMMessage(role="user", content="translate hello into japanese")],
    )
    check(
        "unrequested mixed-script provider corruption is rejected",
        bad is not None,
    )
    check(
        "legitimate multilingual/translation output remains allowed",
        allowed is None,
    )

    mary = Mary()
    repeated = mary.reflection._near_duplicate_response_audit(
        "I hear you. I still think you're doing a great job; leave a little room for more color, a stray thought, and a little wildness so it doesn't feel too sharp.",
        ["Earlier thought. I still think you're doing a great job; leave a little room for more color, a stray thought, and a little wildness so it doesn't feel too sharp."],
    )
    subjective = mary.reflection._subjective_experience_audit(
        "I don't feel like I'm performing, or pretending. I just see you."
    )
    check("near-duplicate recent prose is caught before delivery", bool(repeated))
    check("unsupported subjective-experience certainty is revised", bool(subjective))

    print("=" * 72)
    print("ACCEPTANCE HOTFIX 06 VERIFIED")


if __name__ == "__main__":
    main()
