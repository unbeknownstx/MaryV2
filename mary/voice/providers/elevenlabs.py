"""ElevenLabs text-to-speech provider for MaryV2.

The provider is deliberately small and uses ElevenLabs' documented REST
endpoint directly so the core does not depend on a vendor SDK. Nothing in this
module makes a network request until ``synthesize`` is explicitly called.
"""

from __future__ import annotations

import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from mary.voice.text_to_speech import (
    SpeechAudio,
    SpeechAudioFormat,
    SpeechStatus,
    SynthesisError,
    TextToSpeechProvider,
    VoiceSettings,
)


def _setting_float(
    metadata: dict,
    key: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        value = float(metadata.get(key, default))
    except (TypeError, ValueError):
        value = float(default)
    return max(minimum, min(maximum, value))


class ElevenLabsTextToSpeechProvider(TextToSpeechProvider):
    """Synthesize Mary's speech through an explicitly configured voice."""

    name = "elevenlabs"

    def __init__(
        self,
        *,
        api_key: str,
        voice_id: str,
        model_id: str = "eleven_flash_v2_5",
        output_format: str = "mp3_44100_128",
        timeout: float = 20.0,
        base_url: str = "https://api.elevenlabs.io/v1",
    ) -> None:
        api_key = str(api_key or "").strip()
        voice_id = str(voice_id or "").strip()
        model_id = str(model_id or "").strip()

        if not api_key:
            raise ValueError("ElevenLabs api_key is required.")
        if not voice_id:
            raise ValueError("ElevenLabs voice_id is required.")
        if not model_id:
            raise ValueError("ElevenLabs model_id is required.")

        self.api_key = api_key
        self.voice_id = voice_id
        self.model_id = model_id
        self.output_format = str(output_format or "mp3_44100_128").strip()
        self.timeout = max(1.0, float(timeout))
        self.base_url = str(base_url).rstrip("/")


    def _open_audio(self, request: Request) -> bytes:
        """Open an ElevenLabs request with a verified TLS 1.2 retry.

        Some Windows/OpenSSL/network-filter combinations fail the initial TLS
        negotiation with ``SSLV3_ALERT_HANDSHAKE_FAILURE`` even though the
        endpoint is reachable.  Retrying with TLS 1.2 keeps certificate and
        hostname verification enabled while avoiding the broken negotiation
        path.  No insecure SSL mode is ever used.
        """
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except URLError as exc:
            reason = exc.reason
            if not self._should_retry_tls12(reason):
                raise

        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_2
        with urlopen(request, timeout=self.timeout, context=context) as response:
            return response.read()

    @staticmethod
    def _should_retry_tls12(reason: object) -> bool:
        if isinstance(reason, ssl.SSLCertVerificationError):
            return False
        if isinstance(reason, ssl.SSLError):
            return True
        text = str(reason or "").upper()
        return (
            "SSLV3_ALERT_HANDSHAKE_FAILURE" in text
            or "TLSV1_ALERT_PROTOCOL_VERSION" in text
            or "SSL_HANDSHAKE_FAILURE" in text
        )

    def supports_format(self, audio_format: SpeechAudioFormat) -> bool:
        return audio_format == SpeechAudioFormat.MP3

    def synthesize(
        self,
        text: str,
        *,
        settings: VoiceSettings | None = None,
    ) -> SpeechAudio:
        active = settings if settings is not None else VoiceSettings(
            voice=self.voice_id,
            output_format=SpeechAudioFormat.MP3,
        )

        voice_id = str(active.voice or self.voice_id).strip()
        if not voice_id:
            raise SynthesisError("No ElevenLabs voice ID is configured.", provider=self.name)

        if active.output_format != SpeechAudioFormat.MP3:
            raise SynthesisError(
                "MaryV2 Desktop Voice Alpha currently requests ElevenLabs MP3 output.",
                provider=self.name,
            )

        url = (
            f"{self.base_url}/text-to-speech/{quote(voice_id, safe='')}"
            f"?output_format={quote(self.output_format, safe='')}"
        )
        voice_settings = {
            "stability": _setting_float(active.metadata, "stability", 0.42, 0.0, 1.0),
            "similarity_boost": _setting_float(
                active.metadata,
                "similarity_boost",
                0.82,
                0.0,
                1.0,
            ),
            "style": _setting_float(active.metadata, "style", 0.11, 0.0, 1.0),
            "speed": max(0.7, min(1.2, float(active.speed))),
            "use_speaker_boost": bool(
                active.metadata.get("use_speaker_boost", True)
            ),
        }

        body = json.dumps(
            {
                "text": str(text),
                "model_id": self.model_id,
                "voice_settings": voice_settings,
            }
        ).encode("utf-8")
        request = Request(
            url,
            data=body,
            method="POST",
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
        )

        try:
            audio = self._open_audio(request)
        except HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = ""
            message = f"ElevenLabs returned HTTP {exc.code}."
            if detail:
                message += f" {detail}"
            raise SynthesisError(message, provider=self.name, retryable=500 <= exc.code < 600) from exc
        except URLError as exc:
            raise SynthesisError(
                f"ElevenLabs request failed: {exc.reason}",
                provider=self.name,
                retryable=True,
            ) from exc
        except TimeoutError as exc:
            raise SynthesisError(
                "ElevenLabs request timed out.",
                provider=self.name,
                retryable=True,
            ) from exc

        return SpeechAudio(
            audio=audio,
            status=SpeechStatus.SUCCESS if audio else SpeechStatus.EMPTY,
            format=SpeechAudioFormat.MP3,
            text=str(text),
            provider=self.name,
            model=self.model_id,
            voice=voice_id,
            emotion=active.emotion,
            metadata={
                "output_format": self.output_format,
            },
        )
