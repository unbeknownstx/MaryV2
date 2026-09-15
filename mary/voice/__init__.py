"""
MaryV2 - Voice Package

Public interface for Mary's voice subsystem.

The voice layer provides provider-independent STT/TTS abstractions and does not
connect providers, load credentials, record microphones, play audio, or control
avatars on import.
"""
from .speech_to_text import (
    AudioFormat, TranscriptionStatus, Transcription, SpeechToTextConfig,
    SpeechToTextError, AudioInputError, TranscriptionError,
    UnsupportedAudioFormatError, SpeechToTextProvider, SpeechToTextService,
    NullSpeechToTextProvider, create_stt_service,
)
from .text_to_speech import (
    SpeechAudioFormat, SpeechStatus, SpeechAlignmentMark, SpeechAlignment,
    VoiceSettings, SpeechAudio, TextToSpeechError, SpeechInputError,
    SynthesisError, UnsupportedVoiceError, UnsupportedAudioOutputError,
    TextToSpeechProvider, TextToSpeechService, NullTextToSpeechProvider,
    create_tts_service,
)
from .speech_renderer import SpeechRenderer, render_spoken_text
from .emotion_profile import EmotionVoiceAdjustment, resolve_emotion_voice_settings, emotion_voice_profile_name
from .streaming_tts import SentenceSpeechScheduler, SynthesizedSegment

__all__ = [
    "AudioFormat", "TranscriptionStatus", "Transcription", "SpeechToTextConfig",
    "SpeechToTextError", "AudioInputError", "TranscriptionError", "UnsupportedAudioFormatError",
    "SpeechToTextProvider", "SpeechToTextService", "NullSpeechToTextProvider", "create_stt_service",
    "SpeechAudioFormat", "SpeechStatus", "SpeechAlignmentMark", "SpeechAlignment", "VoiceSettings", "SpeechAudio",
    "TextToSpeechError", "SpeechInputError", "SynthesisError", "UnsupportedVoiceError", "UnsupportedAudioOutputError",
    "TextToSpeechProvider", "TextToSpeechService", "NullTextToSpeechProvider", "create_tts_service",
    "SpeechRenderer", "render_spoken_text",
    "EmotionVoiceAdjustment", "resolve_emotion_voice_settings", "emotion_voice_profile_name",
    "SentenceSpeechScheduler", "SynthesizedSegment",
]
