"""
MaryV2 - Voice Package

Public interface for Mary's voice subsystem.

The voice layer provides:

    - speech-to-text abstractions
    - text-to-speech abstractions
    - provider-independent audio structures
    - voice configuration

This package does NOT:

    - automatically connect to a voice provider
    - make network requests on import
    - load API credentials
    - record from a microphone
    - play audio
    - control Mary's avatar

External providers must be explicitly selected and initialized by
the application.
"""

# ================================================================
# SPEECH-TO-TEXT
# ================================================================

from .speech_to_text import (
    AudioFormat,
    TranscriptionStatus,
    Transcription,
    SpeechToTextConfig,
    SpeechToTextError,
    AudioInputError,
    TranscriptionError,
    UnsupportedAudioFormatError,
    SpeechToTextProvider,
    SpeechToTextService,
    NullSpeechToTextProvider,
    create_stt_service,
)


# ================================================================
# TEXT-TO-SPEECH
# ================================================================

from .text_to_speech import (
    SpeechAudioFormat,
    SpeechStatus,
    VoiceSettings,
    SpeechAudio,
    TextToSpeechError,
    SpeechInputError,
    SynthesisError,
    UnsupportedVoiceError,
    UnsupportedAudioOutputError,
    TextToSpeechProvider,
    TextToSpeechService,
    NullTextToSpeechProvider,
    create_tts_service,
)


# ================================================================
# PUBLIC API
# ================================================================


__all__ = [
    # ------------------------------------------------------------
    # Speech-to-text
    # ------------------------------------------------------------

    "AudioFormat",
    "TranscriptionStatus",
    "Transcription",
    "SpeechToTextConfig",

    "SpeechToTextError",
    "AudioInputError",
    "TranscriptionError",
    "UnsupportedAudioFormatError",

    "SpeechToTextProvider",
    "SpeechToTextService",
    "NullSpeechToTextProvider",
    "create_stt_service",

    # ------------------------------------------------------------
    # Text-to-speech
    # ------------------------------------------------------------

    "SpeechAudioFormat",
    "SpeechStatus",
    "VoiceSettings",
    "SpeechAudio",

    "TextToSpeechError",
    "SpeechInputError",
    "SynthesisError",
    "UnsupportedVoiceError",
    "UnsupportedAudioOutputError",

    "TextToSpeechProvider",
    "TextToSpeechService",
    "NullTextToSpeechProvider",
    "create_tts_service",
]