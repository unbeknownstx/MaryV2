"""MaryV2 local character-mind layer.

The mind layer is deliberately *not* another identity or memory authority.
It is a fast, rebuildable projection over Mary's existing authoritative
systems plus local dialogue/behavior policy.  Language models remain optional
capabilities used when the local mind cannot answer well enough on its own.
"""

from .character_mind import CharacterMind, LocalMindResult
from .behavior import CharacterBehaviorAction, CharacterBehaviorDecision, CharacterBehaviorEngine
from .dialogue_acts import DialogueAct, DialoguePlan
from .hot_state import HotMindState
from .local_authority_confirmation import (
    AuthorityConfirmationBundle,
    ConfirmedAuthorityScalar,
    confirm_dialogue_plan_authority,
)
from .local_composer_v2 import ProceduralLocalComposerV2
from .local_response_audit import LocalResponseAudit, audit_local_response
from .local_response_projector import (
    LocalResponseProjection,
    project_canonical_response_plan,
    project_response_authority,
)
from .reservoir import CognitiveReservoir, ReservoirHit, ReservoirRecord
from .response_risk import (
    ResponseAuthorityContext,
    ResponseRiskClass,
    ResponseRiskDecision,
    classify_response_risk,
)
from .verbalization_plan import CanonicalResponsePlan

__all__ = [
    "CharacterBehaviorAction", "CharacterBehaviorDecision", "CharacterBehaviorEngine",
    "CharacterMind",
    "LocalMindResult",
    "DialogueAct",
    "DialoguePlan",
    "HotMindState",
    "AuthorityConfirmationBundle",
    "ConfirmedAuthorityScalar",
    "confirm_dialogue_plan_authority",
    "CanonicalResponsePlan",
    "ProceduralLocalComposerV2",
    "LocalResponseAudit",
    "audit_local_response",
    "LocalResponseProjection",
    "project_canonical_response_plan",
    "project_response_authority",
    "ResponseAuthorityContext",
    "ResponseRiskClass",
    "ResponseRiskDecision",
    "classify_response_risk",
    "CognitiveReservoir",
    "ReservoirHit",
    "ReservoirRecord",
]
