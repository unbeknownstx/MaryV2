"""Concrete text-to-speech providers for MaryV2.

Provider modules are never activated merely by import. Applications must
explicitly select and configure one.
"""

from .elevenlabs import ElevenLabsTextToSpeechProvider

__all__ = ["ElevenLabsTextToSpeechProvider"]
