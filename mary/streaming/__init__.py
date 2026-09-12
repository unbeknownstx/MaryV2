"""MaryV2 streaming and performer contracts.

The existing chat/presence/social/output interfaces remain the canonical stream
model. 13.6 adds a bounded performer permission bridge around optional Twitch
and OBS host integrations without replacing those contracts.
"""
from .chat import ChatAggregator, ChatMessage, ChatSelection
from .presence import StreamingPresenceCoordinator
from .social import AudienceRoster, AudienceMember
from .output import StreamOutputMode, StreamResponsePlan, plan_stream_response
from .bridge import PerformerBridge, StreamEvent, StreamPermissionError
from .config import PerformerConfig

__all__ = [
    "ChatAggregator", "ChatMessage", "ChatSelection", "StreamingPresenceCoordinator",
    "AudienceRoster", "AudienceMember", "StreamOutputMode", "StreamResponsePlan",
    "plan_stream_response", "PerformerBridge", "PerformerConfig", "StreamEvent",
    "StreamPermissionError",
]
