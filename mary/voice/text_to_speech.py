"""
MaryV2 - Text-to-Speech

Defines the abstraction and data structures required for converting
Mary's text responses into speech audio.

This module does NOT:

    - access the internet
    - call an external API
    - automatically select a provider
    - load API credentials
    - play audio
    - control the avatar

Provider-specific implementations can be added later without
changing the rest of MaryV2.

Architecture:

    expression/response.py
              |
              v
        TTS Service
              |
              v
        TTS Provider
              |
              v
          AudioData
              |
              +----> audio output
              +----> avatar synchronization
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Mapping

from mary.expression.emotion import Emotion
from mary.expression.response import Response


# ================================================================
# AUDIO FORMAT
# ================================================================


class SpeechAudioFormat(str, Enum):
    """
    Audio formats that a TTS provider may produce.
    """

    WAV = "wav"
    MP3 = "mp3"
    OGG = "ogg"
    OPUS = "opus"
    FLAC = "flac"
    PCM = "pcm"


# ================================================================
# SPEECH STATUS
# ================================================================


class SpeechStatus(str, Enum):
    """
    Status of a speech synthesis operation.
    """

    SUCCESS = "success"
    EMPTY = "empty"
    FAILED = "failed"


# ================================================================
# VOICE SETTINGS
# ================================================================


@dataclass
class VoiceSettings:
    """
    Provider-independent voice configuration.

    Individual providers may support only some of these settings.
    """

    voice: str | None = None

    language: str | None = None

    speed: float = 1.0

    pitch: float = 0.0

    volume: float = 1.0

    style: str | None = None

    emotion: Emotion | None = None

    emotion_intensity: float = 0.0

    output_format: SpeechAudioFormat = (
        SpeechAudioFormat.WAV
    )

    sample_rate: int | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        if self.speed <= 0:
            raise ValueError(
                "Voice speed must be greater than 0."
            )

        if self.volume < 0:
            raise ValueError(
                "Voice volume cannot be negative."
            )

        self.volume = min(
            self.volume,
            1.0,
        )

        self.emotion_intensity = _clamp(
            self.emotion_intensity
        )

        if self.sample_rate is not None:
            if self.sample_rate <= 0:
                raise ValueError(
                    "Sample rate must be greater than 0."
                )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "voice": self.voice,
            "language": self.language,
            "speed": self.speed,
            "pitch": self.pitch,
            "volume": self.volume,
            "style": self.style,
            "emotion": (
                self.emotion.value
                if self.emotion is not None
                else None
            ),
            "emotion_intensity": (
                self.emotion_intensity
            ),
            "output_format": (
                self.output_format.value
            ),
            "sample_rate": self.sample_rate,
            "metadata": dict(
                self.metadata
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "VoiceSettings":
        emotion_value = data.get(
            "emotion"
        )

        emotion = None

        if emotion_value is not None:
            try:
                emotion = Emotion(
                    emotion_value
                )
            except ValueError:
                emotion = None

        return cls(
            voice=data.get(
                "voice"
            ),
            language=data.get(
                "language"
            ),
            speed=float(
                data.get(
                    "speed",
                    1.0,
                )
            ),
            pitch=float(
                data.get(
                    "pitch",
                    0.0,
                )
            ),
            volume=float(
                data.get(
                    "volume",
                    1.0,
                )
            ),
            style=data.get(
                "style"
            ),
            emotion=emotion,
            emotion_intensity=float(
                data.get(
                    "emotion_intensity",
                    0.0,
                )
            ),
            output_format=SpeechAudioFormat(
                data.get(
                    "output_format",
                    SpeechAudioFormat.WAV.value,
                )
            ),
            sample_rate=data.get(
                "sample_rate"
            ),
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )


# ================================================================
# SYNTHESIS RESULT
# ================================================================


@dataclass
class SpeechAudio:
    """
    Provider-independent representation of synthesized speech.
    """

    audio: bytes

    status: SpeechStatus = (
        SpeechStatus.SUCCESS
    )

    format: SpeechAudioFormat = (
        SpeechAudioFormat.WAV
    )

    sample_rate: int | None = None

    duration: float | None = None

    text: str = ""

    provider: str | None = None

    model: str | None = None

    voice: str | None = None

    emotion: Emotion | None = None

    timestamp: float = field(
        default_factory=time
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.audio,
            bytes,
        ):
            raise TypeError(
                "audio must be bytes."
            )

        self.text = str(
            self.text
        )

        if self.duration is not None:
            self.duration = max(
                0.0,
                float(
                    self.duration
                ),
            )

        if not self.audio:
            if (
                self.status
                == SpeechStatus.SUCCESS
            ):
                self.status = (
                    SpeechStatus.EMPTY
                )

    @property
    def is_successful(
        self,
    ) -> bool:
        """
        Whether usable audio was produced.
        """

        return (
            self.status
            == SpeechStatus.SUCCESS
            and bool(self.audio)
        )

    @property
    def is_empty(
        self,
    ) -> bool:
        return not bool(
            self.audio
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize metadata without embedding the binary audio.
        """

        return {
            "status": self.status.value,
            "format": self.format.value,
            "sample_rate": self.sample_rate,
            "duration": self.duration,
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "voice": self.voice,
            "emotion": (
                self.emotion.value
                if self.emotion is not None
                else None
            ),
            "timestamp": self.timestamp,
            "audio_size": len(
                self.audio
            ),
            "metadata": dict(
                self.metadata
            ),
        }




@dataclass(frozen=True)
class SpeechAlignmentMark:
    """One provider-neutral text/audio alignment mark.

    Alignment is presentation timing only.  It never becomes conversation,
    memory, identity, or creator evidence.
    """

    text: str
    start_seconds: float
    end_seconds: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", str(self.text or ""))
        start = max(0.0, float(self.start_seconds))
        end = max(start, float(self.end_seconds))
        object.__setattr__(self, "start_seconds", start)
        object.__setattr__(self, "end_seconds", end)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
        }


@dataclass(frozen=True)
class SpeechAlignment:
    """Bounded timing information for avatar/caption synchronization."""

    characters: tuple[SpeechAlignmentMark, ...] = ()
    words: tuple[SpeechAlignmentMark, ...] = ()
    normalized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "characters": [item.to_dict() for item in self.characters],
            "words": [item.to_dict() for item in self.words],
            "normalized": bool(self.normalized),
        }


# ================================================================
# TTS ERRORS
# ================================================================


class TextToSpeechError(
    RuntimeError
):
    """
    Base exception for TTS failures.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        retryable: bool = False,
    ) -> None:

        super().__init__(
            message
        )

        self.provider = provider
        self.retryable = retryable


class SpeechInputError(
    TextToSpeechError
):
    """
    Raised when text input is invalid.
    """


class SynthesisError(
    TextToSpeechError
):
    """
    Raised when speech synthesis fails.
    """


class UnsupportedVoiceError(
    TextToSpeechError
):
    """
    Raised when a provider cannot use the requested voice.
    """


class UnsupportedAudioOutputError(
    TextToSpeechError
):
    """
    Raised when a provider cannot produce the requested format.
    """


# ================================================================
# PROVIDER INTERFACE
# ================================================================


class TextToSpeechProvider(
    ABC
):
    """
    Abstract interface for TTS providers.

    Provider implementations are responsible only for converting
    text into audio.
    """

    name: str = "unknown"

    @abstractmethod
    def synthesize(
        self,
        text: str,
        *,
        settings: VoiceSettings | None = None,
    ) -> SpeechAudio:
        """
        Convert text into speech audio.

        Implementations must not modify Mary's:

            - memory
            - personality
            - cognition
            - relationship
            - goals
            - emotional state

        Those systems remain outside the provider.
        """

        raise NotImplementedError

    def supports_format(
        self,
        audio_format: SpeechAudioFormat,
    ) -> bool:
        """
        Determine whether this provider supports an output format.
        """

        return audio_format in {
            SpeechAudioFormat.WAV,
            SpeechAudioFormat.MP3,
            SpeechAudioFormat.OGG,
            SpeechAudioFormat.OPUS,
            SpeechAudioFormat.FLAC,
            SpeechAudioFormat.PCM,
        }

    def supports_voice(
        self,
        voice: str,
    ) -> bool:
        """
        Determine whether a named voice is supported.

        Providers can override this method.
        """

        return True


# ================================================================
# TTS SERVICE
# ================================================================


class TextToSpeechService:
    """
    Provider-independent TTS service.

    A provider must be explicitly supplied.

    No provider is automatically discovered or activated.
    """

    def __init__(
        self,
        provider: TextToSpeechProvider,
        *,
        settings: VoiceSettings | None = None,
    ) -> None:

        if not isinstance(
            provider,
            TextToSpeechProvider,
        ):
            raise TypeError(
                "provider must implement "
                "TextToSpeechProvider."
            )

        self.provider = provider

        self.settings = (
            settings
            if settings is not None
            else VoiceSettings()
        )

    # ============================================================
    # SYNTHESIS
    # ============================================================

    def synthesize(
        self,
        text: str,
        *,
        settings: VoiceSettings | None = None,
    ) -> SpeechAudio:
        """
        Synthesize text through the explicitly supplied provider.
        """

        text = str(
            text
        ).strip()

        if not text:
            raise SpeechInputError(
                "Text input is empty.",
                provider=self.provider.name,
            )

        active_settings = (
            settings
            if settings is not None
            else self.settings
        )

        if not self.provider.supports_format(
            active_settings.output_format
        ):
            raise UnsupportedAudioOutputError(
                (
                    "Provider "
                    f"'{self.provider.name}' "
                    "does not support "
                    f"{active_settings.output_format.value}."
                ),
                provider=self.provider.name,
            )

        if (
            active_settings.voice
            and not self.provider.supports_voice(
                active_settings.voice
            )
        ):
            raise UnsupportedVoiceError(
                (
                    "Provider "
                    f"'{self.provider.name}' "
                    "does not support voice "
                    f"'{active_settings.voice}'."
                ),
                provider=self.provider.name,
            )

        started = time()

        try:
            result = (
                self.provider.synthesize(
                    text,
                    settings=active_settings,
                )
            )

        except TextToSpeechError:
            raise

        except Exception as exc:
            raise SynthesisError(
                str(exc),
                provider=self.provider.name,
                retryable=False,
            ) from exc

        if result.provider is None:
            result.provider = (
                self.provider.name
            )

        if not result.text:
            result.text = text

        result.metadata.setdefault(
            "processing_time",
            time() - started,
        )

        return result

    # ============================================================
    # RESPONSE SYNTHESIS
    # ============================================================

    def synthesize_response(
        self,
        response: Response,
        *,
        settings: VoiceSettings | None = None,
    ) -> SpeechAudio:
        """
        Synthesize an expression-layer Response.

        The response's emotional state can be passed into the
        voice settings without requiring the TTS provider to know
        anything about Mary's internal architecture.
        """

        active_settings = (
            settings
            if settings is not None
            else self.settings
        )

        if (
            active_settings.emotion is None
        ):
            active_settings = VoiceSettings(
                voice=active_settings.voice,
                language=active_settings.language,
                speed=active_settings.speed,
                pitch=active_settings.pitch,
                volume=active_settings.volume,
                style=active_settings.style,
                emotion=response.emotion,
                emotion_intensity=(
                    response.emotion_intensity
                ),
                output_format=(
                    active_settings.output_format
                ),
                sample_rate=(
                    active_settings.sample_rate
                ),
                metadata=dict(
                    active_settings.metadata
                ),
            )

        return self.synthesize(
            response.text,
            settings=active_settings,
        )


# ================================================================
# NULL PROVIDER
# ================================================================


class NullTextToSpeechProvider(
    TextToSpeechProvider
):
    """
    Explicit no-op TTS provider.

    Useful while developing MaryV2 before an actual TTS provider
    has been explicitly selected and approved.

    No network or external service is accessed.
    """

    name = "null"

    def synthesize(
        self,
        text: str,
        *,
        settings: VoiceSettings | None = None,
    ) -> SpeechAudio:
        """
        Return empty audio.

        The text is preserved for debugging.
        """

        active_settings = (
            settings
            if settings is not None
            else VoiceSettings()
        )

        return SpeechAudio(
            audio=b"",
            status=SpeechStatus.EMPTY,
            format=(
                active_settings.output_format
            ),
            sample_rate=(
                active_settings.sample_rate
            ),
            text=text,
            provider=self.name,
            voice=active_settings.voice,
            emotion=active_settings.emotion,
            metadata={
                "reason": (
                    "Null TTS provider."
                )
            },
        )


# ================================================================
# FACTORY
# ================================================================


def create_tts_service(
    provider: TextToSpeechProvider,
    *,
    settings: VoiceSettings | None = None,
) -> TextToSpeechService:
    """
    Create a TTS service using an explicitly supplied provider.
    """

    return TextToSpeechService(
        provider,
        settings=settings,
    )


# ================================================================
# HELPERS
# ================================================================


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    """
    Clamp a numeric value to a range.
    """

    return max(
        minimum,
        min(
            maximum,
            float(value),
        ),
    )