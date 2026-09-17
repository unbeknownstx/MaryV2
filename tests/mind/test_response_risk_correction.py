from mary.cognition.intent import IntentType
from mary.conversation.lanes import ConversationLane
from mary.mind.dialogue_acts import DialogueAct
from mary.mind.response_risk import (
    ResponseAuthorityContext,
    ResponseRiskClass,
    classify_response_risk,
)


def test_evidence_backed_correction_forces_precision_on_social_lane():
    decision = classify_response_risk(
        dialogue=DialogueAct.REACT,
        intent=IntentType.CONVERSATION,
        lane=ConversationLane.SOCIAL_INSTANT,
        authority=ResponseAuthorityContext(
            user_correction_with_evidence=True,
        ),
    )

    assert decision.response_class == ResponseRiskClass.PRECISION_LOCAL
    assert any("correction" in reason for reason in decision.rationale)


def test_evidence_backed_correction_stays_precision_when_open_ended():
    decision = classify_response_risk(
        dialogue=DialogueAct.REACT,
        intent=IntentType.CONVERSATION,
        lane=ConversationLane.CONVERSATION,
        authority=ResponseAuthorityContext(
            user_correction_with_evidence=True,
            open_ended=True,
        ),
    )

    assert decision.response_class == ResponseRiskClass.PRECISION_LOCAL


def test_hard_tool_requirement_still_outranks_correction_precision():
    decision = classify_response_risk(
        dialogue=DialogueAct.REACT,
        intent=IntentType.TOOL_USE,
        lane=ConversationLane.SOCIAL_INSTANT,
        authority=ResponseAuthorityContext(
            user_correction_with_evidence=True,
            requires_tool=True,
        ),
    )

    assert decision.response_class == ResponseRiskClass.THINKING_REQUIRED


def test_correction_signal_is_exposed_in_authority_diagnostics():
    context = ResponseAuthorityContext(user_correction_with_evidence=True)

    assert context.carries_precision_semantics is True
    assert context.to_dict()["user_correction_with_evidence"] is True
