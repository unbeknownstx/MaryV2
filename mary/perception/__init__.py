"""
MaryV2 Perception Layer

The perception layer converts external input and events into standardized
objects that the cognition system can understand.
"""

from .events import Event, EventType
from .entities import Entity, EntityType
from .input import Input, InputSource, InputType
from .director import PerceptionDirector, PerceptionObservation
from .browser import BrowserContext, BrowserContextSensor
from .sensory import SensoryAttentionController, SensoryPolicy
from .assets import PerceptionAsset, PerceptionAssetRegistry, sha256_bytes
from .media_timeline import MediaObservation, MediaObservationTimeline, build_media_observation_timeline, context_window
from .media_sessions import MediaSessionRegistry
from .media_bridge import publish_media_context

__all__ = [
    "Event",
    "EventType",
    "Entity",
    "EntityType",
    "Input",
    "InputSource",
    "InputType",
    "PerceptionDirector",
    "PerceptionObservation",
    "BrowserContext",
    "BrowserContextSensor",
    "SensoryAttentionController",
    "SensoryPolicy",
    "PerceptionAsset",
    "PerceptionAssetRegistry",
    "sha256_bytes",
    "MediaObservation",
    "MediaObservationTimeline",
    "build_media_observation_timeline",
    "context_window",
    "MediaSessionRegistry",
    "publish_media_context",
]
