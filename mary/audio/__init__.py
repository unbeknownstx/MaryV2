"""
MaryV2 - Audio Package

Public interface for Mary's audio subsystem.

The audio layer provides:

    - audio input abstractions
    - audio output abstractions
    - audio buffers
    - playback results
    - audio lifecycle management

This package does NOT:

    - automatically access a microphone
    - automatically access speakers
    - discover hardware
    - access the internet
    - call external APIs
    - perform speech recognition
    - perform speech synthesis

Hardware and provider implementations must be explicitly selected
and initialized by the application.
"""

# ================================================================
# AUDIO INPUT
# ================================================================

from .input import (
    AudioInputSource,
    AudioInputStatus,
    AudioBuffer,
    AudioInputConfig,
    AudioInputError,
    AudioDeviceError,
    AudioConfigurationError,
    AudioCaptureError,
    AudioInputProvider,
    AudioInputService,
    NullAudioInputProvider,
    create_audio_input_service,
)


# ================================================================
# AUDIO OUTPUT
# ================================================================

from .output import (
    AudioOutputDestination,
    AudioOutputStatus,
    AudioOutputConfig,
    PlaybackResult,
    AudioOutputError,
    AudioPlaybackError,
    AudioOutputDeviceError,
    AudioOutputConfigurationError,
    UnsupportedOutputFormatError,
    AudioOutputProvider,
    AudioOutputService,
    NullAudioOutputProvider,
    create_audio_output_service,
)


# ================================================================
# AUDIO MANAGER
# ================================================================

from .manager import (
    AudioManagerStatus,
    AudioManagerState,
    AudioManagerError,
    AudioManagerNotStartedError,
    AudioManagerShutdownError,
    AudioManager,
)


# ================================================================
# PUBLIC API
# ================================================================

__all__ = [
    # ------------------------------------------------------------
    # Audio input
    # ------------------------------------------------------------

    "AudioInputSource",
    "AudioInputStatus",
    "AudioBuffer",
    "AudioInputConfig",

    "AudioInputError",
    "AudioDeviceError",
    "AudioConfigurationError",
    "AudioCaptureError",

    "AudioInputProvider",
    "AudioInputService",
    "NullAudioInputProvider",
    "create_audio_input_service",

    # ------------------------------------------------------------
    # Audio output
    # ------------------------------------------------------------

    "AudioOutputDestination",
    "AudioOutputStatus",
    "AudioOutputConfig",
    "PlaybackResult",

    "AudioOutputError",
    "AudioPlaybackError",
    "AudioOutputDeviceError",
    "AudioOutputConfigurationError",
    "UnsupportedOutputFormatError",

    "AudioOutputProvider",
    "AudioOutputService",
    "NullAudioOutputProvider",
    "create_audio_output_service",

    # ------------------------------------------------------------
    # Audio manager
    # ------------------------------------------------------------

    "AudioManagerStatus",
    "AudioManagerState",

    "AudioManagerError",
    "AudioManagerNotStartedError",
    "AudioManagerShutdownError",

    "AudioManager",
]