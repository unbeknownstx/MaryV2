"""
MaryV2 - Audio Input

Provider-independent abstractions for receiving audio from an input source.

This module does NOT:

    - automatically open a microphone
    - automatically record audio
    - access an audio device on import
    - access the internet
    - call an external API
    - perform speech recognition

It represents captured audio and defines the interface that a future
microphone, file, stream, or other input source can implement.

Architecture:

    microphone / file / stream
              |
              v
       AudioInputProvider
              |
              v
        AudioInputService
              |
              v
          AudioBuffer
              |
              v
    voice/speech_to_text.py
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Mapping

from mary.voice.speech_to_text import AudioFormat


# ================================================================
# INPUT SOURCE
# ================================================================


class AudioInputSource(str, Enum):
    """Describes where captured audio originated."""

    MICROPHONE = "microphone"
    FILE = "file"
    STREAM = "stream"
    SYSTEM = "system"
    UNKNOWN = "unknown"


# ================================================================
# INPUT STATUS
# ================================================================


class AudioInputStatus(str, Enum):
    """State of an audio input provider or service."""

    IDLE = "idle"
    READY = "ready"
    CAPTURING = "capturing"
    COMPLETE = "complete"
    STOPPED = "stopped"
    FAILED = "failed"


# ================================================================
# AUDIO BUFFER
# ================================================================


@dataclass
class AudioBuffer:
    """Provider-independent representation of captured audio."""

    audio: bytes = b""

    source: AudioInputSource = AudioInputSource.UNKNOWN

    format: AudioFormat = AudioFormat.WAV

    sample_rate: int = 16_000

    channels: int = 1

    sample_width: int = 2

    duration: float | None = None

    captured_at: float = field(default_factory=time)

    provider: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.audio, bytes):
            raise TypeError("audio must be bytes.")

        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be greater than 0.")

        if self.channels <= 0:
            raise ValueError("channels must be greater than 0.")

        if self.sample_width <= 0:
            raise ValueError("sample_width must be greater than 0.")

        if self.duration is not None:
            self.duration = max(0.0, float(self.duration))

    @property
    def is_empty(self) -> bool:
        return not bool(self.audio)

    @property
    def size(self) -> int:
        return len(self.audio)

    def to_dict(self) -> dict[str, Any]:
        """Return serializable metadata without embedding raw bytes."""

        return {
            "source": self.source.value,
            "format": self.format.value,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "sample_width": self.sample_width,
            "duration": self.duration,
            "captured_at": self.captured_at,
            "provider": self.provider,
            "audio_size": self.size,
            "is_empty": self.is_empty,
            "metadata": dict(self.metadata),
        }


# ================================================================
# INPUT CONFIGURATION
# ================================================================


@dataclass
class AudioInputConfig:
    """
    Configuration describing an audio input source.

    These values do not activate an input device by themselves.
    """

    sample_rate: int = 16_000

    channels: int = 1

    sample_width: int = 2

    format: AudioFormat = AudioFormat.WAV

    device: str | int | None = None

    chunk_size: int = 1024

    duration: float | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be greater than 0.")

        if self.channels <= 0:
            raise ValueError("channels must be greater than 0.")

        if self.sample_width <= 0:
            raise ValueError("sample_width must be greater than 0.")

        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0.")

        if self.duration is not None and self.duration < 0:
            raise ValueError("duration cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "sample_width": self.sample_width,
            "format": self.format.value,
            "device": self.device,
            "chunk_size": self.chunk_size,
            "duration": self.duration,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AudioInputConfig":
        return cls(
            sample_rate=int(data.get("sample_rate", 16_000)),
            channels=int(data.get("channels", 1)),
            sample_width=int(data.get("sample_width", 2)),
            format=AudioFormat(data.get("format", AudioFormat.WAV.value)),
            device=data.get("device"),
            chunk_size=int(data.get("chunk_size", 1024)),
            duration=data.get("duration"),
            metadata=dict(data.get("metadata", {})),
        )


# ================================================================
# INPUT ERRORS
# ================================================================


class AudioInputError(RuntimeError):
    """Base exception for audio input failures."""

    def __init__(
        self,
        message: str,
        *,
        source: AudioInputSource = AudioInputSource.UNKNOWN,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.source = source
        self.retryable = retryable


class AudioDeviceError(AudioInputError):
    """Raised when an input device cannot be accessed."""


class AudioConfigurationError(AudioInputError):
    """Raised when input configuration is invalid."""


class AudioCaptureError(AudioInputError):
    """Raised when audio capture fails."""


# ================================================================
# INPUT PROVIDER
# ================================================================


class AudioInputProvider(ABC):
    """
    Abstract interface for audio input providers.

    A provider may represent a microphone, file, stream, or another
    explicitly configured source.
    """

    name: str = "unknown"

    source: AudioInputSource = AudioInputSource.UNKNOWN

    @abstractmethod
    def start(
        self,
        *,
        config: AudioInputConfig | None = None,
    ) -> None:
        """Prepare the input source."""

        raise NotImplementedError

    @abstractmethod
    def read(self) -> AudioBuffer:
        """Read one captured audio buffer."""

        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Stop input capture."""

        raise NotImplementedError

    @property
    @abstractmethod
    def status(self) -> AudioInputStatus:
        """Current provider status."""

        raise NotImplementedError

    def supports_format(self, audio_format: AudioFormat) -> bool:
        return audio_format in {
            AudioFormat.WAV,
            AudioFormat.MP3,
            AudioFormat.MP4,
            AudioFormat.M4A,
            AudioFormat.FLAC,
            AudioFormat.OGG,
            AudioFormat.WEBM,
            AudioFormat.PCM,
        }


# ================================================================
# AUDIO INPUT SERVICE
# ================================================================


class AudioInputService:
    """
    Coordinates an explicitly supplied audio input provider.

    No microphone or other source is automatically discovered or
    activated.
    """

    def __init__(
        self,
        provider: AudioInputProvider,
        *,
        config: AudioInputConfig | None = None,
    ) -> None:
        if not isinstance(provider, AudioInputProvider):
            raise TypeError(
                "provider must implement AudioInputProvider."
            )

        self.provider = provider
        self.config = config if config is not None else AudioInputConfig()
        self._started = False

    def start(
        self,
        *,
        config: AudioInputConfig | None = None,
    ) -> None:
        """Explicitly initialize the input provider."""

        active_config = config if config is not None else self.config

        if not self.provider.supports_format(active_config.format):
            raise AudioConfigurationError(
                (
                    f"Provider '{self.provider.name}' does not support "
                    f"{active_config.format.value}."
                ),
                source=self.provider.source,
            )

        try:
            self.provider.start(config=active_config)
        except AudioInputError:
            raise
        except Exception as exc:
            raise AudioDeviceError(
                str(exc),
                source=self.provider.source,
                retryable=False,
            ) from exc

        self._started = True

    def read(self) -> AudioBuffer:
        """Read one buffer from the active provider."""

        if not self._started:
            raise AudioInputError(
                "Audio input has not been started.",
                source=self.provider.source,
            )

        try:
            result = self.provider.read()
        except AudioInputError:
            raise
        except Exception as exc:
            raise AudioCaptureError(
                str(exc),
                source=self.provider.source,
                retryable=False,
            ) from exc

        if not isinstance(result, AudioBuffer):
            raise AudioCaptureError(
                "Audio input provider returned an invalid buffer.",
                source=self.provider.source,
            )

        if result.provider is None:
            result.provider = self.provider.name

        return result

    def stop(self) -> None:
        """Stop the provider if it has been started."""

        if not self._started:
            return

        try:
            self.provider.stop()
        except AudioInputError:
            raise
        except Exception as exc:
            raise AudioDeviceError(
                str(exc),
                source=self.provider.source,
                retryable=False,
            ) from exc
        finally:
            self._started = False

    @property
    def is_active(self) -> bool:
        return self._started

    @property
    def status(self) -> AudioInputStatus:
        if not self._started:
            return AudioInputStatus.IDLE

        return self.provider.status


# ================================================================
# NULL PROVIDER
# ================================================================


class NullAudioInputProvider(AudioInputProvider):
    """
    Explicit no-op audio input provider.

    It never touches a microphone, file, stream, or hardware. It is
    useful while MaryV2 has an audio interface but no real input
    provider has been explicitly configured.
    """

    name = "null"
    source = AudioInputSource.UNKNOWN

    def __init__(self) -> None:
        self._status = AudioInputStatus.IDLE
        self._config = AudioInputConfig()

    def start(
        self,
        *,
        config: AudioInputConfig | None = None,
    ) -> None:
        if config is not None:
            self._config = config

        self._status = AudioInputStatus.READY

    def read(self) -> AudioBuffer:
        if self._status not in {
            AudioInputStatus.READY,
            AudioInputStatus.COMPLETE,
        }:
            raise AudioInputError(
                "Null audio input is not active.",
                source=self.source,
            )

        self._status = AudioInputStatus.CAPTURING
        self._status = AudioInputStatus.COMPLETE

        return AudioBuffer(
            audio=b"",
            source=self.source,
            format=self._config.format,
            sample_rate=self._config.sample_rate,
            channels=self._config.channels,
            sample_width=self._config.sample_width,
            duration=0.0,
            provider=self.name,
            metadata={
                "reason": "Null audio input provider."
            },
        )

    def stop(self) -> None:
        self._status = AudioInputStatus.STOPPED

    @property
    def status(self) -> AudioInputStatus:
        return self._status


# ================================================================
# FACTORY
# ================================================================


def create_audio_input_service(
    provider: AudioInputProvider,
    *,
    config: AudioInputConfig | None = None,
) -> AudioInputService:
    """Create an audio input service using an explicit provider."""

    return AudioInputService(
        provider,
        config=config,
    )
