"""Desktop voice synthesis adapter.

Voice is opt-in. MaryV2 Desktop remains completely local/no-op unless
``MARY_TTS_PROVIDER=elevenlabs`` is explicitly configured.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any

from mary.voice import (
    SpeechAudioFormat,
    SpeechRenderer,
    VoiceSettings,
    create_tts_service,
)
from mary.voice.providers import ElevenLabsTextToSpeechProvider


@dataclass(frozen=True)
class DesktopVoiceStatus:
    enabled: bool
    provider: str = "off"
    voice_id: str | None = None
    model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "voice_id": self.voice_id,
            "model": self.model,
        }


def _env_float(
    name: str,
    default: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    raw = os.getenv(name, "").strip()
    try:
        value = float(raw) if raw else float(default)
    except ValueError:
        value = float(default)
    return max(minimum, min(maximum, value))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return bool(default)
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(default)


class DesktopVoiceEngine:
    """Optional TTS engine used by the desktop presentation surface."""

    def __init__(
        self,
        *,
        service=None,
        status: DesktopVoiceStatus | None = None,
        renderer: SpeechRenderer | None = None,
    ) -> None:
        self.service = service
        self.status = status or DesktopVoiceStatus(enabled=False)
        self.renderer = renderer or SpeechRenderer()

    @classmethod
    def from_environment(cls) -> "DesktopVoiceEngine":
        provider_name = os.getenv("MARY_TTS_PROVIDER", "off").strip().lower()
        if provider_name in {"", "off", "none", "null", "disabled"}:
            return cls()

        if provider_name != "elevenlabs":
            return cls(
                status=DesktopVoiceStatus(
                    enabled=False,
                    provider=provider_name,
                )
            )

        api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        voice_id = os.getenv("MARY_ELEVENLABS_VOICE_ID", "").strip()
        model_id = os.getenv("MARY_ELEVENLABS_MODEL", "eleven_flash_v2_5").strip()

        if not api_key or not voice_id:
            return cls(
                status=DesktopVoiceStatus(
                    enabled=False,
                    provider="elevenlabs",
                    voice_id=voice_id or None,
                    model=model_id or None,
                )
            )

        stability = _env_float("MARY_TTS_STABILITY", 0.42, minimum=0.0, maximum=1.0)
        similarity = _env_float("MARY_TTS_SIMILARITY", 0.82, minimum=0.0, maximum=1.0)
        style = _env_float("MARY_TTS_STYLE", 0.11, minimum=0.0, maximum=1.0)
        speed = _env_float("MARY_TTS_SPEED", 0.97, minimum=0.7, maximum=1.2)
        speaker_boost = _env_bool("MARY_TTS_SPEAKER_BOOST", True)

        provider = ElevenLabsTextToSpeechProvider(
            api_key=api_key,
            voice_id=voice_id,
            model_id=model_id or "eleven_flash_v2_5",
            timeout=20.0,
        )
        settings = VoiceSettings(
            voice=voice_id,
            speed=speed,
            output_format=SpeechAudioFormat.MP3,
            metadata={
                "stability": stability,
                "similarity_boost": similarity,
                "style": style,
                "use_speaker_boost": speaker_boost,
            },
        )
        service = create_tts_service(provider, settings=settings)
        return cls(
            service=service,
            status=DesktopVoiceStatus(
                enabled=True,
                provider="elevenlabs",
                voice_id=voice_id,
                model=model_id,
            ),
        )

    def synthesize(self, text: str) -> dict[str, Any]:
        if self.service is None or not self.status.enabled:
            return {
                **self.status.to_dict(),
                "status": "disabled",
            }

        spoken_text = self.renderer.render(str(text))
        if not spoken_text:
            return {
                **self.status.to_dict(),
                "status": "empty",
                "spoken_text": "",
            }

        speech = self.service.synthesize(spoken_text)
        if not speech.is_successful:
            return {
                **self.status.to_dict(),
                "status": speech.status.value,
            }

        mime_type = "audio/mpeg" if speech.format == SpeechAudioFormat.MP3 else "application/octet-stream"
        return {
            **self.status.to_dict(),
            "status": speech.status.value,
            "format": speech.format.value,
            "mime_type": mime_type,
            "audio_base64": base64.b64encode(speech.audio).decode("ascii"),
            "audio_size": len(speech.audio),
            "spoken_text": spoken_text,
        }
