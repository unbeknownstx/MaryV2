"""Provider-independent speech-to-text support for MaryV2 Desktop."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class SpeechToTextStatus:
    enabled: bool
    provider: str
    model: str
    language: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpeechToTextError(RuntimeError):
    """Raised when desktop speech transcription cannot complete."""


def _create_groq_client(api_key: str) -> Any:
    from groq import Groq

    return Groq(
        api_key=api_key,
        timeout=20.0,
        max_retries=0,
    )


class DesktopSpeechToText:
    """Small STT adapter used by the desktop push-to-talk surface."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        language: str,
        api_key: str | None,
    ) -> None:
        self.provider = provider.strip().lower()
        self.model = model.strip()
        self.language = language.strip() or "en"
        self.api_key = api_key
        self.client: Any | None = None

        if self.provider == "groq" and self.api_key:
            self.client = _create_groq_client(self.api_key)

    @classmethod
    def from_environment(cls) -> "DesktopSpeechToText":
        provider = os.getenv("MARY_STT_PROVIDER", "groq")
        model = os.getenv("MARY_STT_MODEL", "whisper-large-v3-turbo")
        language = os.getenv("MARY_STT_LANGUAGE", "en")
        return cls(
            provider=provider,
            model=model,
            language=language,
            api_key=os.getenv("GROQ_API_KEY"),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.provider == "groq" and self.client)

    @property
    def status(self) -> SpeechToTextStatus:
        return SpeechToTextStatus(
            enabled=self.enabled,
            provider=self.provider or "disabled",
            model=self.model,
            language=self.language,
        )

    def transcribe(self, path: str | Path) -> str:
        if not self.enabled or self.client is None:
            raise SpeechToTextError(
                "Desktop speech input is not configured. Set GROQ_API_KEY "
                "and MARY_STT_PROVIDER=groq."
            )

        audio_path = Path(path)
        if not audio_path.exists() or not audio_path.is_file():
            raise SpeechToTextError("Recorded microphone audio was not found.")
        if audio_path.stat().st_size <= 0:
            raise SpeechToTextError("Recorded microphone audio is empty.")

        try:
            with audio_path.open("rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    file=(audio_path.name, audio_file.read()),
                    model=self.model,
                    response_format="json",
                    language=self.language,
                    temperature=0.0,
                    prompt=(
                        "A natural conversation between Unbe and Mary Cosma in "
                        "MaryV2. Preserve the spellings Unbe, Mary Cosma, and MaryV2."
                    ),
                )
        except Exception as exc:
            raise SpeechToTextError(
                f"Groq speech transcription failed: {exc}"
            ) from exc

        text = str(getattr(response, "text", "") or "").strip()
        if not text:
            raise SpeechToTextError("No speech was detected in the recording.")
        return text
