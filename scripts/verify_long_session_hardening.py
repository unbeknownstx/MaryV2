"""Verify MaryV2 fixes discovered during the first real long conversation."""

from __future__ import annotations

from mary.cognition.intent import IntentType
from mary.core.mary import Mary


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def main() -> None:
    print("=" * 72)
    print("MARY V2 LONG-SESSION HARDENING")
    print("=" * 72)

    mary = Mary()

    feeling = mary.cognition.detect_intent(
        "Hey Mary, we've been working on you for quite a while today. "
        "How are you feeling about yourself right now?"
    )
    check(
        "self-reflection stays local instead of becoming a web search",
        feeling.intent_type == IntentType.SELF_QUERY
        and feeling.parameters.get("self_query_type") == "current_state",
    )

    natural_feeling = mary.cognition.detect_intent(
        "Hey Mary, how are you feeling right now?"
    )
    check(
        "natural current-feeling phrasing stays local before right-now web routing",
        natural_feeling.intent_type == IntentType.SELF_QUERY
        and natural_feeling.parameters.get("self_query_type") == "current_state"
        and mary.tools.pending_requests() == [],
    )

    runtime_architecture = mary.cognition.detect_intent(
        "What's your underlying architecture running on?"
    )
    check(
        "runtime architecture question stays local instead of provider-improvised",
        runtime_architecture.intent_type == IntentType.SELF_QUERY
        and runtime_architecture.parameters.get("self_query_type") == "runtime_architecture",
    )

    natural_runtime_architecture = mary.cognition.detect_intent(
        "Who are you, and how do language models fit into your architecture?"
    )
    check(
        "natural compound architecture question stays deterministic/local",
        natural_runtime_architecture.intent_type == IntentType.SELF_QUERY
        and natural_runtime_architecture.parameters.get("self_query_type")
        == "runtime_architecture",
    )

    creator_memory = mary.cognition.detect_intent(
        "Do you remember anything about me?"
    )
    check(
        "broad creator-memory question uses relationship/creator state",
        creator_memory.intent_type == IntentType.RELATIONSHIP_QUERY
        and creator_memory.parameters.get("relationship_query_type") == "memory_overview",
    )

    social = mary.cognition.detect_intent(
        "What kinds of people do you get along with?"
    )
    check(
        "natural social self-question uses grounded character state",
        social.intent_type == IntentType.SELF_QUERY
        and social.parameters.get("self_query_type") == "social_behavior",
    )

    long_reply = "painting and sketching " * 80
    recall = mary._handle_conversation_recall([
        {"role": "user", "content": "What do you like about yourself?"},
        {"role": "assistant", "content": "Tiny details make me happy."},
        {"role": "user", "content": "What would you do all day by yourself?"},
        {"role": "assistant", "content": long_reply},
    ])
    check(
        "recent conversation recall is bounded rather than verbatim-dumped",
        len(recall) < 650 and recall.count("painting and sketching") < 10,
    )

    status = mary.status().get("cognition", {})
    check(
        "runtime status exposes routing strategy and provider order",
        "routing_strategy" in status and bool(status.get("provider_order")),
    )

    print("-" * 72)
    print("RESULT: PASS")
    print("The first long-session routing/memory/continuity regressions are guarded.")


if __name__ == "__main__":
    main()
