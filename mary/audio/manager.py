"""
MaryV2 - Audio Manager

Coordinates Mary's audio input and output services.

This module does NOT:

    - automatically access a microphone
    - automatically access speakers
    - access the internet
    - call an external API
    - perform speech recognition
    - perform speech synthesis
    - modify cognition, memory, personality, or goals

The manager coordinates already-created audio services.

Architecture:

    AudioInputService
            |
            v
      AudioManager
            |
            v
    AudioOutputService

Voice processing remains in:

    voice/speech_to_text.py
    voice/text_to_speech.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any

from .input import (
    AudioBuffer,
    AudioInputConfig,
    AudioInputService,
    AudioInputStatus,
)

from .output import (
    AudioOutputConfig,
    AudioOutputService,
    AudioOutputStatus,
    PlaybackResult,
)

from mary.voice.text_to_speech import SpeechAudio


# ================================================================
# MANAGER STATUS
# ================================================================


class AudioManagerStatus(str, Enum):
    """
    Overall state of the audio subsystem.
    """

    INACTIVE = "inactive"
    READY = "ready"
    INPUT_ACTIVE = "input_active"
    OUTPUT_ACTIVE = "output_active"
    ACTIVE = "active"
    STOPPING = "stopping"
    ERROR = "error"


# ================================================================
# AUDIO MANAGER STATE
# ================================================================


@dataclass
class AudioManagerState:
    """
    Snapshot of the current audio subsystem state.
    """

    status: AudioManagerStatus = (
        AudioManagerStatus.INACTIVE
    )

    input_status: AudioInputStatus = (
        AudioInputStatus.IDLE
    )

    output_status: AudioOutputStatus = (
        AudioOutputStatus.IDLE
    )

    input_active: bool = False

    output_active: bool = False

    last_input_at: float | None = None

    last_output_at: float | None = None

    last_error: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "input_status": (
                self.input_status.value
            ),
            "output_status": (
                self.output_status.value
            ),
            "input_active": self.input_active,
            "output_active": self.output_active,
            "last_input_at": self.last_input_at,
            "last_output_at": self.last_output_at,
            "last_error": self.last_error,
            "metadata": dict(
                self.metadata
            ),
        }


# ================================================================
# AUDIO MANAGER ERRORS
# ================================================================


class AudioManagerError(
    RuntimeError
):
    """
    Base exception for audio manager failures.
    """


class AudioManagerNotStartedError(
    AudioManagerError
):
    """
    Raised when an operation requires an active audio subsystem.
    """


class AudioManagerShutdownError(
    AudioManagerError
):
    """
    Raised when an operation is attempted after shutdown.
    """


# ================================================================
# AUDIO MANAGER
# ================================================================


class AudioManager:
    """
    Coordinates Mary's input and output audio services.

    The manager receives already-constructed services. It does not
    discover devices or providers on its own.

    This keeps the architecture dependency-injected and makes the
    system easy to test.
    """

    def __init__(
        self,
        *,
        input_service: AudioInputService | None = None,
        output_service: AudioOutputService | None = None,
        input_config: AudioInputConfig | None = None,
        output_config: AudioOutputConfig | None = None,
    ) -> None:

        self.input_service = input_service

        self.output_service = output_service

        self.input_config = (
            input_config
            if input_config is not None
            else AudioInputConfig()
        )

        self.output_config = (
            output_config
            if output_config is not None
            else AudioOutputConfig()
        )

        self._started = False

        self._shutdown = False

        self._state = AudioManagerState()

    # ============================================================
    # START
    # ============================================================

    def start(
        self,
        *,
        start_input: bool = False,
        start_output: bool = False,
    ) -> AudioManagerState:
        """
        Explicitly start requested audio services.

        Nothing is activated unless start() is explicitly called.

        By default neither input nor output is started.
        """

        if self._shutdown:
            raise AudioManagerShutdownError(
                "Audio manager has already been shut down."
            )

        try:
            if (
                start_input
                and self.input_service is not None
            ):
                self.input_service.start(
                    config=self.input_config
                )

            if (
                start_output
                and self.output_service is not None
            ):
                self.output_service.start(
                    config=self.output_config
                )

        except Exception as exc:
            self._state.status = (
                AudioManagerStatus.ERROR
            )

            self._state.last_error = str(
                exc
            )

            raise

        self._started = True

        self._refresh_state()

        if (
            not self._state.input_active
            and not self._state.output_active
        ):
            self._state.status = (
                AudioManagerStatus.READY
            )

        return self.state

    # ============================================================
    # START INPUT
    # ============================================================

    def start_input(
        self,
    ) -> AudioManagerState:
        """
        Explicitly activate the configured input service.
        """

        self._ensure_available()

        if self.input_service is None:
            raise AudioManagerError(
                "No audio input service is configured."
            )

        try:
            self.input_service.start(
                config=self.input_config
            )

        except Exception as exc:
            self._state.status = (
                AudioManagerStatus.ERROR
            )

            self._state.last_error = str(
                exc
            )

            raise

        self._started = True

        self._refresh_state()

        return self.state

    # ============================================================
    # START OUTPUT
    # ============================================================

    def start_output(
        self,
    ) -> AudioManagerState:
        """
        Explicitly activate the configured output service.
        """

        self._ensure_available()

        if self.output_service is None:
            raise AudioManagerError(
                "No audio output service is configured."
            )

        try:
            self.output_service.start(
                config=self.output_config
            )

        except Exception as exc:
            self._state.status = (
                AudioManagerStatus.ERROR
            )

            self._state.last_error = str(
                exc
            )

            raise

        self._started = True

        self._refresh_state()

        return self.state

    # ============================================================
    # READ INPUT
    # ============================================================

    def read_input(
        self,
    ) -> AudioBuffer:
        """
        Read one audio buffer from the configured input service.
        """

        self._ensure_available()

        if self.input_service is None:
            raise AudioManagerError(
                "No audio input service is configured."
            )

        if not self.input_service.is_active:
            raise AudioManagerNotStartedError(
                "Audio input has not been started."
            )

        try:
            result = (
                self.input_service.read()
            )

        except Exception as exc:
            self._state.status = (
                AudioManagerStatus.ERROR
            )

            self._state.last_error = str(
                exc
            )

            raise

        self._state.last_input_at = time()

        self._refresh_state()

        return result

    # ============================================================
    # PLAY OUTPUT
    # ============================================================

    def play_output(
        self,
        audio: SpeechAudio,
    ) -> PlaybackResult:
        """
        Send synthesized speech audio to the configured output.
        """

        self._ensure_available()

        if self.output_service is None:
            raise AudioManagerError(
                "No audio output service is configured."
            )

        if not self.output_service.is_active:
            raise AudioManagerNotStartedError(
                "Audio output has not been started."
            )

        try:
            result = (
                self.output_service.play(
                    audio
                )
            )

        except Exception as exc:
            self._state.status = (
                AudioManagerStatus.ERROR
            )

            self._state.last_error = str(
                exc
            )

            raise

        self._state.last_output_at = time()

        self._refresh_state()

        return result

    # ============================================================
    # STOP INPUT
    # ============================================================

    def stop_input(
        self,
    ) -> AudioManagerState:
        """
        Explicitly stop audio input.
        """

        if self.input_service is not None:
            self.input_service.stop()

        self._refresh_state()

        return self.state

    # ============================================================
    # STOP OUTPUT
    # ============================================================

    def stop_output(
        self,
    ) -> AudioManagerState:
        """
        Explicitly stop audio output.
        """

        if self.output_service is not None:
            self.output_service.stop()

        self._refresh_state()

        return self.state

    # ============================================================
    # STOP
    # ============================================================

    def stop(
        self,
    ) -> AudioManagerState:
        """
        Stop active audio services without permanently shutting
        down the manager.
        """

        if self._shutdown:
            return self.state

        self._state.status = (
            AudioManagerStatus.STOPPING
        )

        errors: list[Exception] = []

        if self.input_service is not None:
            try:
                self.input_service.stop()
            except Exception as exc:
                errors.append(exc)

        if self.output_service is not None:
            try:
                self.output_service.stop()
            except Exception as exc:
                errors.append(exc)

        self._started = False

        if errors:
            self._state.status = (
                AudioManagerStatus.ERROR
            )

            self._state.last_error = str(
                errors[0]
            )

            raise errors[0]

        self._refresh_state()

        return self.state

    # ============================================================
    # SHUTDOWN
    # ============================================================

    def shutdown(
        self,
    ) -> AudioManagerState:
        """
        Permanently shut down the manager instance.

        A new AudioManager should be created if the subsystem needs
        to be initialized again.
        """

        if self._shutdown:
            return self.state

        try:
            self.stop()

        finally:
            self._shutdown = True
            self._started = False

            self._state.status = (
                AudioManagerStatus.INACTIVE
            )

            self._refresh_state()

        return self.state

    # ============================================================
    # STATE
    # ============================================================

    @property
    def state(
        self,
    ) -> AudioManagerState:
        """
        Return a snapshot of manager state.

        A copy is returned so callers cannot directly mutate the
        manager's internal state.
        """

        self._refresh_state()

        return AudioManagerState(
            status=self._state.status,
            input_status=self._state.input_status,
            output_status=self._state.output_status,
            input_active=self._state.input_active,
            output_active=self._state.output_active,
            last_input_at=self._state.last_input_at,
            last_output_at=self._state.last_output_at,
            last_error=self._state.last_error,
            metadata=dict(
                self._state.metadata
            ),
        )

    @property
    def is_active(
        self,
    ) -> bool:
        return (
            self._state.input_active
            or self._state.output_active
        )

    @property
    def is_shutdown(
        self,
    ) -> bool:
        return self._shutdown

    # ============================================================
    # INTERNAL STATE MANAGEMENT
    # ============================================================

    def _refresh_state(
        self,
    ) -> None:
        """
        Synchronize manager state with child services.
        """

        if self.input_service is not None:
            self._state.input_active = (
                self.input_service.is_active
            )

            self._state.input_status = (
                self.input_service.status
            )
        else:
            self._state.input_active = False

            self._state.input_status = (
                AudioInputStatus.IDLE
            )

        if self.output_service is not None:
            self._state.output_active = (
                self.output_service.is_active
            )

            self._state.output_status = (
                self.output_service.status
            )
        else:
            self._state.output_active = False

            self._state.output_status = (
                AudioOutputStatus.IDLE
            )

        if self._shutdown:
            self._state.status = (
                AudioManagerStatus.INACTIVE
            )

            return

        if (
            self._state.input_active
            and self._state.output_active
        ):
            self._state.status = (
                AudioManagerStatus.ACTIVE
            )

        elif self._state.input_active:
            self._state.status = (
                AudioManagerStatus.INPUT_ACTIVE
            )

        elif self._state.output_active:
            self._state.status = (
                AudioManagerStatus.OUTPUT_ACTIVE
            )

        elif self._started:
            self._state.status = (
                AudioManagerStatus.READY
            )

        else:
            self._state.status = (
                AudioManagerStatus.INACTIVE
            )

    def _ensure_available(
        self,
    ) -> None:
        """
        Ensure the manager can perform an operation.
        """

        if self._shutdown:
            raise AudioManagerShutdownError(
                "Audio manager has been shut down."
            )