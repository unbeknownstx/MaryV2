"""MaryV2 streaming and performer contracts.

The existing chat/presence/social/output interfaces remain the canonical stream
model. 13.10 adds a bounded cohost planner and loopback OBS presentation relay
without creating another Mary, provider router, memory store, or permission path.
"""
from .chat import ChatAggregator, ChatMessage, ChatSelection
from .presence import StreamingPresenceCoordinator
from .social import AudienceRoster, AudienceMember
from .output import StreamOutputMode, StreamResponsePlan, plan_stream_response
from .bridge import PerformerBridge, StreamEvent, StreamPermissionError
from .config import PerformerConfig
from .cohost import CohostRenderedResponse, CohostTurn, StreamCohostPlanner, summarize_stream_context
from .relay import LocalOBSRelay, RelaySnapshot, StreamRelayState

__all__ = [
    "ChatAggregator", "ChatMessage", "ChatSelection", "StreamingPresenceCoordinator",
    "AudienceRoster", "AudienceMember", "StreamOutputMode", "StreamResponsePlan",
    "plan_stream_response", "PerformerBridge", "PerformerConfig", "StreamEvent",
    "StreamPermissionError", "CohostRenderedResponse", "CohostTurn",
    "StreamCohostPlanner", "summarize_stream_context", "LocalOBSRelay",
    "RelaySnapshot", "StreamRelayState",
]
