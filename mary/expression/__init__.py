"""
MaryV2 - Expression Package

Public interface for Mary's expressive communication system.

The expression layer is responsible for representing and
coordinating:

    - emotional state
    - structured responses
    - dialogue state

It does NOT:

    - perform reasoning
    - call an LLM
    - access the internet
    - retrieve long-term memories
    - execute tools
    - synthesize speech
    - control the avatar

Those responsibilities belong to their respective subsystems.
"""

from .emotion import (
    Emotion,
    EmotionIntensity,
    EmotionalSignal,
    EmotionalState,
    EmotionManager,
    create_emotion_manager,
)


from .appraisal import (
    ConversationEmotionAppraisal,
    ConversationEmotionAppraiser,
)

from .response import (
    ResponseType,
    ResponsePriority,
    DeliveryMode,
    ResponseMetadata,
    Response,
    ResponseBuilder,
    create_response_builder,
)


from .delivery_plan import DeliveryPlan
from .director import ExpressionDirector

from .dialogue import (
    DialogueMode,
    SpeakerRole,
    DialogueMessage,
    DialogueTurn,
    DialogueState,
    DialogueManager,
    create_dialogue_manager,
    messages_to_text,
)


__all__ = [
    # Emotion
    "Emotion",
    "EmotionIntensity",
    "EmotionalSignal",
    "EmotionalState",
    "EmotionManager",
    "create_emotion_manager",
    "ConversationEmotionAppraisal",
    "ConversationEmotionAppraiser",

    # Response
    "ResponseType",
    "ResponsePriority",
    "DeliveryMode",
    "ResponseMetadata",
    "Response",
    "ResponseBuilder",
    "create_response_builder",

    # Performance direction
    "DeliveryPlan",
    "ExpressionDirector",

    # Dialogue
    "DialogueMode",
    "SpeakerRole",
    "DialogueMessage",
    "DialogueTurn",
    "DialogueState",
    "DialogueManager",
    "create_dialogue_manager",
    "messages_to_text",
]