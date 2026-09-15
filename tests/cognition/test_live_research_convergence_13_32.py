from mary.core.mary import Mary
from mary.runtime.root_authority import MaryRootAuthority


def test_live_mary_context_contains_bounded_runtime_coordination():
    mary = Mary()
    text = "Research and compare architectures for persistent agent memory."
    intent = mary.cognition.detect_intent(text)
    context = mary._build_context(
        text,
        intent=intent,
        recent_conversation=[],
    )

    runtime = context["mind_state"]["runtime_coordination"]
    assert runtime["authority"] == "coordination_projection_only"
    assert runtime["cognition"]["cognitive_mode"] == "deliberate"
    assert runtime["deliberation"]["strategy"] in {"verify_once", "branch_verify"}
    assert runtime["deliberation"]["expose_private_reasoning"] is False
    assert runtime["realtime"]["allow_barge_in"] is True
    assert mary.character_runtime.VERSION == "13.32"


def test_root_authority_forbids_private_reasoning_persistence_and_self_modification():
    joined = " ".join(MaryRootAuthority.INVARIANTS).lower()
    assert "private chain-of-thought" in joined
    assert "automatically self-modify production mary" in joined
