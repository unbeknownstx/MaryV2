"""Realtime interaction primitives for MaryV2."""
from .attention import AttentionBus, AttentionEvent, AttentionSource, AttentionDisposition, AttentionJudgment, PeripheralNote
from .interaction import InteractionPhase, InteractionTurn, RealtimeInteractionCoordinator
from .speech_arbiter import SpeechArbitration, SpeechDisposition, SpeechOutputArbiter, SpeechRequest
from .data_plane import RealtimeDataPlane, RealtimeDatum
from .decision_trace import DecisionTraceEntry, RealtimeDecisionTrace
from .speaker_scheduler import FloorDecision, FloorDisposition, SpeakerOpportunity, SpeakerScheduler
from .streaming import GenerationDelta, SentenceSegment, SentenceStreamAssembler, StreamCancelled, TurnCancellation, segment_deltas

__all__ = [
    "AttentionBus",
    "AttentionEvent",
    "AttentionSource",
    "AttentionDisposition",
    "AttentionJudgment",
    "PeripheralNote",
    "InteractionPhase",
    "InteractionTurn",
    "RealtimeInteractionCoordinator",
    "SpeechArbitration",
    "SpeechDisposition",
    "SpeechOutputArbiter",
    "SpeechRequest",
    "RealtimeDataPlane",
    "RealtimeDatum",
    "DecisionTraceEntry",
    "RealtimeDecisionTrace",
    "FloorDecision",
    "FloorDisposition",
    "SpeakerOpportunity",
    "SpeakerScheduler",
    "GenerationDelta",
    "SentenceSegment",
    "SentenceStreamAssembler",
    "StreamCancelled",
    "TurnCancellation",
    "segment_deltas",
]
