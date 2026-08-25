"""Compatibility-safe exports for the production deterministic dialogue path.

This facade keeps the benchmark-only source-isolation contract intact while
allowing CharacterMind to use the V2 bounded realization stack in production.
"""
from __future__ import annotations

from .local_composer_v2 import ProceduralLocalComposerV2
from .response_risk import ResponseRiskClass, classify_response_risk as classify_local_response

LOCAL_ENGINE = "local_composer_v2"
LOCAL_MODEL = "local-composer-v2"
THINKING_ESCALATION = "response_risk_thinking_required"
OPEN_ESCALATION = "response_risk_open_conversation"
COMPOSER_FAILURE = "local_composer_v2_failed"

__all__ = [
    "ProceduralLocalComposerV2",
    "ResponseRiskClass",
    "classify_local_response",
    "LOCAL_ENGINE",
    "LOCAL_MODEL",
    "THINKING_ESCALATION",
    "OPEN_ESCALATION",
    "COMPOSER_FAILURE",
]
