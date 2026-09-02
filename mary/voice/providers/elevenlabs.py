"""ElevenLabs text-to-speech provider for MaryV2.

The provider is deliberately small and uses ElevenLabs' documented REST
endpoint directly so the core does not depend on a vendor SDK. Nothing in this
module makes a network request until ``synthesize`` is explicitly called.
"""

from __future__ import annotations

import base64
import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from mary.voice.text_to_speech import (
    SpeechAudio,
    SpeechAlignment,
    SpeechAlignmentMark,
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

    @staticmethod
    def _alignment_from_payload(payload: dict) -> SpeechAlignment | None:
        """Normalize ElevenLabs character timing into Mary's TTS contract."""

        raw = payload.get("normalized_alignment") or payload.get("alignment")
        if not isinstance(raw, dict):
            return None
        chars = list(raw.get("characters") or [])
        starts = list(raw.get("character_start_times_seconds") or [])
        ends = list(raw.get("character_end_times_seconds") or [])
        count = min(len(chars), len(starts), len(ends), 12000)
        marks: list[SpeechAlignmentMark] = []
        for index in range(count):
            try:
                marks.append(
                    SpeechAlignmentMark(
                        text=str(chars[index]),
                        start_seconds=float(starts[index]),
                        end_seconds=float(ends[index]),
                    )
                )
            except (TypeError, ValueError):
                continue

        # Derive word spans locally so downstream avatar/caption clients do not
        # need a provider-specific parser.  Character marks remain the precise
        # source for future viseme generation.
        words: list[SpeechAlignmentMark] = []
        buffer: list[SpeechAlignmentMark] = []
        for mark in marks + [SpeechAlignmentMark(text=" ", start_seconds=marks[-1].end_seconds if marks else 0.0, end_seconds=marks[-1].end_seconds if marks else 0.0)]:
            if mark.text.isspace():
                if buffer:
                    words.append(
                        SpeechAlignmentMark(
                            text="".join(item.text for item in buffer),
                            start_seconds=buffer[0].start_seconds,
                            end_seconds=buffer[-1].end_seconds,
                        )
                    )
                    buffer = []
            else:
                buffer.append(mark)
        return SpeechAlignment(
            characters=tuple(marks),
            words=tuple(words[:2000]),
            normalized=bool(payload.get("normalized_alignment")),
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

        with_timestamps = bool(active.metadata.get("with_timestamps", False))
        endpoint = "with-timestamps" if with_timestamps else ""
        suffix = f"/{endpoint}" if endpoint else ""
        url = (
            f"{self.base_url}/text-to-speech/{quote(voice_id, safe='')}{suffix}"
            f"?output_format={quote(self.output_format, safe='')}"
        )
        voice_settings = {
            "stability": _setting_float(active.metadata, "stability", 0.50, 0.0, 1.0),
            "similarity_boost": _setting_float(
                active.metadata,
                "similarity_boost",
                0.75,
                0.0,
                1.0,
            ),
            "style": _setting_float(active.metadata, "style", 0.0, 0.0, 1.0),
            "speed": max(0.7, min(1.2, float(active.speed))),
            "use_speaker_boost": bool(
                active.metadata.get("use_speaker_boost", False)
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
                "Accept": "application/json" if with_timestamps else "audio/mpeg",
            },
        )

        try:
            raw_response = self._open_audio(request)
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

        alignment = None
        if with_timestamps:
            try:
                response_payload = json.loads(raw_response.decode("utf-8"))
                audio = base64.b64decode(str(response_payload.get("audio_base64") or ""), validate=True)
                alignment = self._alignment_from_payload(response_payload)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                raise SynthesisError(
                    "ElevenLabs timestamp response could not be decoded.",
                    provider=self.name,
                ) from exc
        else:
            audio = raw_response

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
                "alignment": alignment.to_dict() if alignment is not None else None,
                "alignment_source": "elevenlabs_tts_timestamps" if alignment is not None else None,
            },
        )
