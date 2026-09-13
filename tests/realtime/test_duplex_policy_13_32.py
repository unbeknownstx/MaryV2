from mary.realtime.duplex_policy import DuplexInteractionPolicy


def test_relational_turn_allows_one_bounded_backchannel():
    plan = DuplexInteractionPolicy().plan(
        cognitive_mode="relational",
        knowledge_recommended=False,
    )
    assert plan.mode == "conversational_duplex"
    assert plan.allow_backchannel is True
    assert plan.max_backchannels == 1
    assert plan.allow_barge_in is True


def test_research_turn_can_overlap_retrieval_but_not_publish_partial_facts():
    plan = DuplexInteractionPolicy().plan(
        cognitive_mode="deliberate",
        knowledge_recommended=True,
    )
    assert plan.mode == "retrieval_overlap"
    assert plan.overlap_retrieval is True
    assert plan.partial_answer_allowed is False


def test_speaking_state_remains_yieldable():
    plan = DuplexInteractionPolicy().plan(
        cognitive_mode="relational",
        knowledge_recommended=True,
        mary_speaking=True,
    )
    assert plan.mode == "yieldable_speech"
    assert plan.allow_barge_in is True
    assert plan.overlap_retrieval is False
