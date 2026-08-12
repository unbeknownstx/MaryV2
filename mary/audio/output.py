"""
MaryV2 - Audio Output

Provider-independent abstractions for sending audio to an output.

This module does NOT:

    - automatically open speakers
    - automatically play audio
    - access an audio device on import
    - access the internet
    - call an external API
    - synthesize speech

It represents audio output and defines the interface that a future
speaker, file, stream, or other output destination can implement.

Architecture:

    voice/text_to_speech.py
              |
              v
          SpeechAudio
              |
              v
        AudioOutputService
              |
              v
        AudioOutputProvider
              |
              v
       speaker / file / stream
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Mapping

from mary.voice.text_to_speech import (
    SpeechAudio,
    SpeechAudioFormat,
)


# ================================================================
# OUTPUT DESTINATION
# ================================================================


class AudioOutputDestination(str, Enum):
    """
    Describes where audio will be sent.
    """

    SPEAKER = "speaker"
    FILE = "file"
    STREAM = "stream"
    SYSTEM = "system"
    UNKNOWN = "unknown"


# ================================================================
# OUTPUT STATUS
# ================================================================


class AudioOutputStatus(str, Enum):
    """
    State of an audio output operation.
    """

    IDLE = "idle"
    READY = "ready"
    PLAYING = "playing"
    PAUSED = "paused"
    COMPLETE = "complete"
    STOPPED = "stopped"
    FAILED = "failed"


# ================================================================
# AUDIO OUTPUT CONFIGURATION
# ================================================================


@dataclass
class AudioOutputConfig:
    """
    Configuration describing an audio output destination.

    These values do not activate an output device by themselves.
    """

    sample_rate: int = 16_000

    channels: int = 1

    sample_width: int = 2

    format: SpeechAudioFormat = (
        SpeechAudioFormat.WAV
    )

    device: str | int | None = None

    volume: float = 1.0

    latency_mode: str = "balanced"

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        if self.sample_rate <= 0:
            raise ValueError(
                "sample_rate must be greater than 0."
            )

        if self.channels <= 0:
            raise ValueError(
                "channels must be greater than 0."
            )

        if self.sample_width <= 0:
            raise ValueError(
                "sample_width must be greater than 0."
            )

        if self.volume < 0:
            raise ValueError(
                "volume cannot be negative."
            )

        self.volume = min(
            self.volume,
            1.0,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "sample_width": self.sample_width,
            "format": self.format.value,
            "device": self.device,
            "volume": self.volume,
            "latency_mode": self.latency_mode,
            "metadata": dict(
                self.metadata
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "AudioOutputConfig":
        return cls(
            sample_rate=int(
                data.get(
                    "sample_rate",
                    16_000,
                )
            ),
            channels=int(
                data.get(
                    "channels",
                    1,
                )
            ),
            sample_width=int(
                data.get(
                    "sample_width",
                    2,
                )
            ),
            format=SpeechAudioFormat(
                data.get(
                    "format",
                    SpeechAudioFormat.WAV.value,
                )
            ),
            device=data.get(
                "device"
            ),
            volume=float(
                data.get(
                    "volume",
                    1.0,
                )
            ),
            latency_mode=str(
                data.get(
                    "latency_mode",
                    "balanced",
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
# PLAYBACK RESULT
# ================================================================


@dataclass
class PlaybackResult:
    """
    Provider-independent result of an audio output operation.
    """

    status: AudioOutputStatus

    destination: AudioOutputDestination = (
        AudioOutputDestination.UNKNOWN
    )

    audio_size: int = 0

    duration: float | None = None

    started_at: float = field(
        default_factory=time
    )

    completed_at: float | None = None

    provider: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def elapsed(
        self,
    ) -> float | None:
        """
        Amount of time represented by the playback operation.
        """

        if self.completed_at is None:
            return None

        return max(
            0.0,
            self.completed_at
            - self.started_at,
        )

    @property
    def successful(
        self,
    ) -> bool:
        return (
            self.status
            == AudioOutputStatus.COMPLETE
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "destination": (
                self.destination.value
            ),
            "audio_size": self.audio_size,
            "duration": self.duration,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "provider": self.provider,
            "elapsed": self.elapsed,
            "metadata": dict(
                self.metadata
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "PlaybackResult":

        return cls(
            status=AudioOutputStatus(
                data.get(
                    "status",
                    AudioOutputStatus.COMPLETE.value,
                )
            ),
            destination=AudioOutputDestination(
                data.get(
                    "destination",
                    AudioOutputDestination.UNKNOWN.value,
                )
            ),
            audio_size=int(
                data.get(
                    "audio_size",
                    0,
                )
            ),
            duration=data.get(
                "duration"
            ),
            started_at=float(
                data.get(
                    "started_at",
                    time(),
                )
            ),
            completed_at=data.get(
                "completed_at"
            ),
            provider=data.get(
                "provider"
            ),
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )


# ================================================================
# AUDIO OUTPUT ERRORS
# ================================================================


class AudioOutputError(
    RuntimeError
):
    """
    Base exception for audio output failures.
    """

    def __init__(
        self,
        message: str,
        *,
        destination: AudioOutputDestination = (
            AudioOutputDestination.UNKNOWN
        ),
        retryable: bool = False,
    ) -> None:

        super().__init__(
            message
        )

        self.destination = destination
        self.retryable = retryable


class AudioPlaybackError(
    AudioOutputError
):
    """
    Raised when audio playback fails.
    """


class AudioOutputDeviceError(
    AudioOutputError
):
    """
    Raised when an output device cannot be accessed.
    """


class AudioOutputConfigurationError(
    AudioOutputError
):
    """
    Raised when output configuration is invalid.
    """


class UnsupportedOutputFormatError(
    AudioOutputError
):
    """
    Raised when the output provider cannot handle the audio format.
    """


# ================================================================
# OUTPUT PROVIDER
# ================================================================


class AudioOutputProvider(
    ABC
):
    """
    Abstract interface for audio output providers.

    A provider may represent:

        - speakers
        - an audio file
        - a stream
        - another output destination

    The provider is responsible only for outputting audio.
    """

    name: str = "unknown"

    destination: AudioOutputDestination = (
        AudioOutputDestination.UNKNOWN
    )

    # ============================================================
    # LIFECYCLE
    # ============================================================

    @abstractmethod
    def start(
        self,
        *,
        config: AudioOutputConfig | None = None,
    ) -> None:
        """
        Prepare the output destination.
        """

        raise NotImplementedError

    @abstractmethod
    def play(
        self,
        audio: SpeechAudio,
    ) -> PlaybackResult:
        """
        Output a SpeechAudio object.
        """

        raise NotImplementedError

    @abstractmethod
    def stop(
        self,
    ) -> None:
        """
        Stop output.
        """

        raise NotImplementedError

    # ============================================================
    # OPTIONAL CONTROLS
    # ============================================================

    def pause(
        self,
    ) -> None:
        """
        Pause playback.

        Providers that support pausing can override this method.
        """

        raise NotImplementedError(
            "This provider does not implement pause()."
        )

    def resume(
        self,
    ) -> None:
        """
        Resume playback.

        Providers that support resuming can override this method.
        """

        raise NotImplementedError(
            "This provider does not implement resume()."
        )

    @property
    @abstractmethod
    def status(
        self,
    ) -> AudioOutputStatus:
        """
        Current output status.
        """

        raise NotImplementedError

    def supports_format(
        self,
        audio_format: SpeechAudioFormat,
    ) -> bool:
        """
        Determine whether the provider supports an audio format.
        """

        return audio_format in {
            SpeechAudioFormat.WAV,
            SpeechAudioFormat.MP3,
            SpeechAudioFormat.OGG,
            SpeechAudioFormat.OPUS,
            SpeechAudioFormat.FLAC,
            SpeechAudioFormat.PCM,
        }


# ================================================================
# AUDIO OUTPUT SERVICE
# ================================================================


class AudioOutputService:
    """
    Coordinates an explicitly supplied audio output provider.

    No output device is automatically discovered or activated.
    """

    def __init__(
        self,
        provider: AudioOutputProvider,
        *,
        config: AudioOutputConfig | None = None,
    ) -> None:

        if not isinstance(
            provider,
            AudioOutputProvider,
        ):
            raise TypeError(
                "provider must implement "
                "AudioOutputProvider."
            )

        self.provider = provider

        self.config = (
            config
            if config is not None
            else AudioOutputConfig()
        )

        self._started = False

    # ============================================================
    # START
    # ============================================================

    def start(
        self,
        *,
        config: AudioOutputConfig | None = None,
    ) -> None:
        """
        Explicitly initialize the output provider.
        """

        active_config = (
            config
            if config is not None
            else self.config
        )

        try:
            self.provider.start(
                config=active_config
            )

        except AudioOutputError:
            raise

        except Exception as exc:
            raise AudioOutputDeviceError(
                str(exc),
                destination=(
                    self.provider.destination
                ),
                retryable=False,
            ) from exc

        self._started = True

    # ============================================================
    # PLAY
    # ============================================================

    def play(
        self,
        audio: SpeechAudio,
    ) -> PlaybackResult:
        """
        Send synthesized audio to the output provider.
        """

        if not self._started:
            raise AudioOutputError(
                "Audio output has not been started.",
                destination=(
                    self.provider.destination
                ),
            )

        if not isinstance(
            audio,
            SpeechAudio,
        ):
            raise TypeError(
                "audio must be a SpeechAudio instance."
            )

        if audio.is_empty:
            raise AudioPlaybackError(
                "Cannot play empty audio.",
                destination=(
                    self.provider.destination
                ),
            )

        if not self.provider.supports_format(
            audio.format
        ):
            raise UnsupportedOutputFormatError(
                (
                    "Provider "
                    f"'{self.provider.name}' "
                    "does not support "
                    f"{audio.format.value}."
                ),
                destination=(
                    self.provider.destination
                ),
            )

        try:
            result = self.provider.play(
                audio
            )

        except AudioOutputError:
            raise

        except Exception as exc:
            raise AudioPlaybackError(
                str(exc),
                destination=(
                    self.provider.destination
                ),
                retryable=False,
            ) from exc

        if not isinstance(
            result,
            PlaybackResult,
        ):
            raise AudioPlaybackError(
                "Audio provider returned an invalid playback result.",
                destination=(
                    self.provider.destination
                ),
            )

        if result.provider is None:
            result.provider = (
                self.provider.name
            )

        return result

    # ============================================================
    # STOP
    # ============================================================

    def stop(
        self,
    ) -> None:
        """
        Stop the output provider.
        """

        if not self._started:
            return

        try:
            self.provider.stop()

        except AudioOutputError:
            raise

        except Exception as exc:
            raise AudioPlaybackError(
                str(exc),
                destination=(
                    self.provider.destination
                ),
                retryable=False,
            ) from exc

        finally:
            self._started = False

    # ============================================================
    # PAUSE
    # ============================================================

    def pause(
        self,
    ) -> None:
        """
        Pause playback if supported.
        """

        if not self._started:
            raise AudioOutputError(
                "Audio output has not been started.",
                destination=(
                    self.provider.destination
                ),
            )

        self.provider.pause()

    # ============================================================
    # RESUME
    # ============================================================

    def resume(
        self,
    ) -> None:
        """
        Resume playback if supported.
        """

        if not self._started:
            raise AudioOutputError(
                "Audio output has not been started.",
                destination=(
                    self.provider.destination
                ),
            )

        self.provider.resume()

    # ============================================================
    # STATE
    # ============================================================

    @property
    def is_active(
        self,
    ) -> bool:
        return self._started

    @property
    def status(
        self,
    ) -> AudioOutputStatus:
        if not self._started:
            return AudioOutputStatus.IDLE

        return self.provider.status


# ================================================================
# NULL PROVIDER
# ================================================================


class NullAudioOutputProvider(
    AudioOutputProvider
):
    """
    Explicit no-op audio output provider.

    It never touches speakers, files, streams, or hardware.

    Useful while developing MaryV2 before an actual output provider
    has been explicitly selected.
    """

    name = "null"

    destination = (
        AudioOutputDestination.UNKNOWN
    )

    def __init__(
        self,
    ) -> None:

        self._status = (
            AudioOutputStatus.IDLE
        )

    def start(
        self,
        *,
        config: AudioOutputConfig | None = None,
    ) -> None:

        self._status = (
            AudioOutputStatus.READY
        )

    def play(
        self,
        audio: SpeechAudio,
    ) -> PlaybackResult:

        if (
            self._status
            != AudioOutputStatus.READY
        ):
            raise AudioOutputError(
                "Null audio output is not active.",
                destination=self.destination,
            )

        if audio.is_empty:
            raise AudioPlaybackError(
                "Cannot play empty audio.",
                destination=self.destination,
            )

        self._status = (
            AudioOutputStatus.PLAYING
        )

        started = time()

        self._status = (
            AudioOutputStatus.COMPLETE
        )

        completed = time()

        return PlaybackResult(
            status=AudioOutputStatus.COMPLETE,
            destination=self.destination,
            audio_size=len(
                audio.audio
            ),
            duration=audio.duration,
            started_at=started,
            completed_at=completed,
            provider=self.name,
            metadata={
                "reason": (
                    "Null audio output provider."
                )
            },
        )

    def stop(
        self,
    ) -> None:

        self._status = (
            AudioOutputStatus.STOPPED
        )

    @property
    def status(
        self,
    ) -> AudioOutputStatus:

        return self._status


# ================================================================
# FACTORY
# ================================================================


def create_audio_output_service(
    provider: AudioOutputProvider,
    *,
    config: AudioOutputConfig | None = None,
) -> AudioOutputService:
    """
    Create an audio output service using an explicitly supplied
    provider.
    """

    return AudioOutputService(
        provider,
        config=config,
    )