"""
MaryV2 - Speech-to-Text

Defines the abstraction and data structures required for converting
audio input into text.

This module does NOT:

    - access the internet
    - call an external API
    - automatically select a provider
    - load API credentials
    - record from a microphone
    - play audio

Provider-specific implementations can be added later without
changing the rest of MaryV2.

Architecture:

    microphone / audio source
              |
              v
        STT Provider
              |
              v
        Transcription
              |
              v
       perception/input
              |
              v
          cognition
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Mapping


# ================================================================
# AUDIO FORMAT
# ================================================================


class AudioFormat(str, Enum):
    """
    Supported audio container/encoding identifiers.

    These describe the input expected by an STT provider.
    """

    WAV = "wav"
    MP3 = "mp3"
    MP4 = "mp4"
    M4A = "m4a"
    FLAC = "flac"
    OGG = "ogg"
    WEBM = "webm"
    PCM = "pcm"


# ================================================================
# TRANSCRIPTION STATUS
# ================================================================


class TranscriptionStatus(str, Enum):
    """
    Status of a transcription operation.
    """

    SUCCESS = "success"
    EMPTY = "empty"
    PARTIAL = "partial"
    FAILED = "failed"


# ================================================================
# TRANSCRIPTION
# ================================================================


@dataclass
class Transcription:
    """
    Result returned by an STT provider.

    This object gives the rest of MaryV2 a provider-independent
    representation of recognized speech.
    """

    text: str

    status: TranscriptionStatus = (
        TranscriptionStatus.SUCCESS
    )

    language: str | None = None

    confidence: float | None = None

    duration: float | None = None

    provider: str | None = None

    model: str | None = None

    timestamp: float = field(
        default_factory=time
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        self.text = str(
            self.text
        )

        if self.confidence is not None:
            self.confidence = _clamp(
                self.confidence
            )

        if self.duration is not None:
            self.duration = max(
                0.0,
                float(
                    self.duration
                ),
            )

        if not self.text.strip():
            if (
                self.status
                == TranscriptionStatus.SUCCESS
            ):
                self.status = (
                    TranscriptionStatus.EMPTY
                )

    @property
    def is_successful(
        self,
    ) -> bool:
        """
        Whether usable speech was successfully recognized.
        """

        return (
            self.status
            in {
                TranscriptionStatus.SUCCESS,
                TranscriptionStatus.PARTIAL,
            }
            and bool(
                self.text.strip()
            )
        )

    @property
    def is_empty(
        self,
    ) -> bool:
        return not bool(
            self.text.strip()
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize the transcription.
        """

        return {
            "text": self.text,
            "status": self.status.value,
            "language": self.language,
            "confidence": self.confidence,
            "duration": self.duration,
            "provider": self.provider,
            "model": self.model,
            "timestamp": self.timestamp,
            "metadata": dict(
                self.metadata
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "Transcription":
        """
        Restore a transcription from serialized data.
        """

        return cls(
            text=str(
                data.get(
                    "text",
                    "",
                )
            ),
            status=TranscriptionStatus(
                data.get(
                    "status",
                    TranscriptionStatus.SUCCESS.value,
                )
            ),
            language=data.get(
                "language"
            ),
            confidence=data.get(
                "confidence"
            ),
            duration=data.get(
                "duration"
            ),
            provider=data.get(
                "provider"
            ),
            model=data.get(
                "model"
            ),
            timestamp=float(
                data.get(
                    "timestamp",
                    time(),
                )
            ),
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )


# ================================================================
# STT CONFIGURATION
# ================================================================


@dataclass
class SpeechToTextConfig:
    """
    Provider-independent STT configuration.

    Provider adapters may support only a subset of these options.
    """

    language: str | None = None

    model: str | None = None

    audio_format: AudioFormat = (
        AudioFormat.WAV
    )

    temperature: float | None = None

    prompt: str | None = None

    timestamps: bool = False

    speaker_detection: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "language": self.language,
            "model": self.model,
            "audio_format": (
                self.audio_format.value
            ),
            "temperature": self.temperature,
            "prompt": self.prompt,
            "timestamps": self.timestamps,
            "speaker_detection": (
                self.speaker_detection
            ),
            "metadata": dict(
                self.metadata
            ),
        }


# ================================================================
# STT ERROR
# ================================================================


class SpeechToTextError(
    RuntimeError
):
    """
    Base exception for STT failures.
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


class AudioInputError(
    SpeechToTextError
):
    """
    Raised when audio input is invalid or unavailable.
    """


class TranscriptionError(
    SpeechToTextError
):
    """
    Raised when transcription fails.
    """


class UnsupportedAudioFormatError(
    SpeechToTextError
):
    """
    Raised when a provider cannot process the requested format.
    """


# ================================================================
# PROVIDER INTERFACE
# ================================================================


class SpeechToTextProvider(
    ABC
):
    """
    Abstract interface for STT providers.

    Implementations must provide transcription behavior while the
    rest of MaryV2 remains independent of the provider.
    """

    name: str = "unknown"

    @abstractmethod
    def transcribe(
        self,
        audio: bytes,
        *,
        config: SpeechToTextConfig | None = None,
    ) -> Transcription:
        """
        Transcribe raw audio bytes.

        Implementations should:

            1. Validate the audio.
            2. Send/process it using the selected provider.
            3. Return a Transcription.

        Implementations must not modify Mary's memory,
        personality, cognition, or relationship state.
        """

        raise NotImplementedError

    def supports_format(
        self,
        audio_format: AudioFormat,
    ) -> bool:
        """
        Determine whether the provider supports an audio format.

        Providers can override this when necessary.
        """

        return audio_format in {
            AudioFormat.WAV,
            AudioFormat.MP3,
            AudioFormat.FLAC,
            AudioFormat.M4A,
            AudioFormat.OGG,
            AudioFormat.WEBM,
        }


# ================================================================
# STT SERVICE
# ================================================================


class SpeechToTextService:
    """
    Provider-independent STT service.

    A provider must be explicitly supplied.

    This class does not discover or automatically activate
    providers.
    """

    def __init__(
        self,
        provider: SpeechToTextProvider,
        *,
        config: SpeechToTextConfig | None = None,
    ) -> None:

        if not isinstance(
            provider,
            SpeechToTextProvider,
        ):
            raise TypeError(
                "provider must implement "
                "SpeechToTextProvider."
            )

        self.provider = provider

        self.config = (
            config
            if config is not None
            else SpeechToTextConfig()
        )

    # ============================================================
    # TRANSCRIBE
    # ============================================================

    def transcribe(
        self,
        audio: bytes,
        *,
        config: SpeechToTextConfig | None = None,
    ) -> Transcription:
        """
        Transcribe audio through the explicitly supplied provider.
        """

        if not isinstance(
            audio,
            bytes,
        ):
            raise TypeError(
                "audio must be bytes."
            )

        if not audio:
            raise AudioInputError(
                "Audio input is empty.",
                provider=self.provider.name,
            )

        active_config = (
            config
            if config is not None
            else self.config
        )

        if not self.provider.supports_format(
            active_config.audio_format
        ):
            raise UnsupportedAudioFormatError(
                (
                    "Provider "
                    f"'{self.provider.name}' "
                    "does not support "
                    f"{active_config.audio_format.value}."
                ),
                provider=self.provider.name,
            )

        started = time()

        try:
            result = (
                self.provider.transcribe(
                    audio,
                    config=active_config,
                )
            )

        except SpeechToTextError:
            raise

        except Exception as exc:
            raise TranscriptionError(
                str(exc),
                provider=self.provider.name,
                retryable=False,
            ) from exc

        if result.provider is None:
            result.provider = (
                self.provider.name
            )

        if (
            result.duration is None
        ):
            result.metadata.setdefault(
                "processing_time",
                time() - started,
            )

        return result


# ================================================================
# NULL PROVIDER
# ================================================================


class NullSpeechToTextProvider(
    SpeechToTextProvider
):
    """
    Explicit no-op STT provider.

    Useful during development when Mary should have an STT
    interface but no actual STT service has been approved/configured.
    """

    name = "null"

    def transcribe(
        self,
        audio: bytes,
        *,
        config: SpeechToTextConfig | None = None,
    ) -> Transcription:
        """
        Return an empty transcription.

        No network or external service is accessed.
        """

        return Transcription(
            text="",
            status=(
                TranscriptionStatus.EMPTY
            ),
            provider=self.name,
            model=None,
            metadata={
                "reason": (
                    "Null STT provider."
                )
            },
        )


# ================================================================
# FACTORY
# ================================================================


def create_stt_service(
    provider: SpeechToTextProvider,
    *,
    config: SpeechToTextConfig | None = None,
) -> SpeechToTextService:
    """
    Create an STT service using an explicitly supplied provider.
    """

    return SpeechToTextService(
        provider,
        config=config,
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