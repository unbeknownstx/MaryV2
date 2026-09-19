"""Loopback-only GPT-SoVITS v2 text-to-speech provider.

This adapter follows the official GPT-SoVITS api_v2.py /tts contract while
keeping the engine a replaceable renderer.  It deliberately accepts only
loopback HTTP(S) endpoints: a Mary configuration string must never turn this
local voice adapter into an arbitrary network request primitive.
"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from mary.voice.text_to_speech import (
    SpeechAudio,
    SpeechAudioFormat,
    SpeechStatus,
    SynthesisError,
    TextToSpeechProvider,
    VoiceSettings,
)


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _loopback_base_url(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    if not raw:
        raise ValueError("GPT-SoVITS base_url is required.")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("GPT-SoVITS base_url must use http or https.")
    if (parsed.hostname or "").casefold() not in _LOOPBACK_HOSTS:
        raise ValueError("GPT-SoVITS base_url must be loopback-only.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("GPT-SoVITS base_url may not contain credentials, query, or fragment.")
    return raw


class GPTSoVITSLocalTextToSpeechProvider(TextToSpeechProvider):
    """Synthesize speech through an explicitly running local GPT-SoVITS API."""

    name = "gpt_sovits"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:9880",
        ref_audio_path: str,
        prompt_text: str = "",
        text_lang: str = "en",
        prompt_lang: str = "en",
        timeout: float = 45.0,
    ) -> None:
        self.base_url = _loopback_base_url(base_url)
        self.ref_audio_path = str(ref_audio_path or "").strip()
        if not self.ref_audio_path:
            raise ValueError("GPT-SoVITS ref_audio_path is required.")
        self.prompt_text = str(prompt_text or "").strip()
        self.text_lang = str(text_lang or "en").strip().lower()
        self.prompt_lang = str(prompt_lang or self.text_lang or "en").strip().lower()
        self.timeout = max(1.0, min(180.0, float(timeout)))

    def supports_format(self, audio_format: SpeechAudioFormat) -> bool:
        return audio_format == SpeechAudioFormat.WAV

    def synthesize(
        self,
        text: str,
        *,
        settings: VoiceSettings | None = None,
    ) -> SpeechAudio:
        active = settings if settings is not None else VoiceSettings(
            output_format=SpeechAudioFormat.WAV
        )
        if active.output_format != SpeechAudioFormat.WAV:
            raise SynthesisError(
                "Mary's GPT-SoVITS adapter requests WAV output.",
                provider=self.name,
            )

        value = str(text or "").strip()
        if not value:
            return SpeechAudio(
                audio=b"",
                status=SpeechStatus.EMPTY,
                format=SpeechAudioFormat.WAV,
                text="",
                provider=self.name,
            )

        metadata = dict(active.metadata or {})
        text_lang = str(metadata.get("gpt_sovits_text_lang") or self.text_lang).strip().lower()
        prompt_lang = str(metadata.get("gpt_sovits_prompt_lang") or self.prompt_lang).strip().lower()
        prompt_text = str(metadata.get("gpt_sovits_prompt_text") or self.prompt_text).strip()
        body = json.dumps(
            {
                "text": value,
                "text_lang": text_lang,
                "ref_audio_path": self.ref_audio_path,
                "aux_ref_audio_paths": [],
                "prompt_text": prompt_text,
                "prompt_lang": prompt_lang,
                "text_split_method": str(metadata.get("gpt_sovits_split_method") or "cut5"),
                "batch_size": 1,
                "speed_factor": max(0.6, min(1.5, float(active.speed))),
                "media_type": "wav",
                "streaming_mode": False,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/tts",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "audio/wav",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                audio = response.read()
                content_type = str(response.headers.get("Content-Type") or "").lower()
        except HTTPError as exc:
            raise SynthesisError(
                f"Local GPT-SoVITS request failed with HTTP {int(exc.code)}.",
                provider=self.name,
                retryable=500 <= int(exc.code) < 600,
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise SynthesisError(
                "Local GPT-SoVITS is temporarily unreachable.",
                provider=self.name,
                retryable=True,
            ) from exc

        if content_type and "audio" not in content_type:
            raise SynthesisError(
                "Local GPT-SoVITS returned a non-audio response.",
                provider=self.name,
            )
        if not audio:
            raise SynthesisError(
                "Local GPT-SoVITS returned empty audio.",
                provider=self.name,
            )

        return SpeechAudio(
            audio=audio,
            status=SpeechStatus.SUCCESS,
            format=SpeechAudioFormat.WAV,
            text=value,
            provider=self.name,
            model="GPT-SoVITS local",
            voice=active.voice,
            emotion=active.emotion,
            metadata={
                "local": True,
                "endpoint": "loopback",
                "text_lang": text_lang,
                "prompt_lang": prompt_lang,
            },
        )
