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
from .reservoir import CognitiveReservoir, ReservoirHit, ReservoirRecord

__all__ = [
    "CharacterBehaviorAction", "CharacterBehaviorDecision", "CharacterBehaviorEngine",
    "CharacterMind",
    "LocalMindResult",
    "DialogueAct",
    "DialoguePlan",
    "HotMindState",
    "CognitiveReservoir",
    "ReservoirHit",
    "ReservoirRecord",
]
