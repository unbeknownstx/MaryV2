"""Provider-independent speech-to-text support for MaryV2 Desktop/home nodes.

Local/cloud backends remain optional. 13.14 adds a fixed specialist-HTTP bridge
so Qwen3-ASR, FluidAudio or another audited STT service can be benchmarked behind
the same bounded node contract without becoming a Core dependency. The endpoint
is host configuration; remote tasks can never choose a URL or executable.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SpeechToTextStatus:
    enabled: bool
    provider: str
    model: str
    language: str
    local: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpeechToTextError(RuntimeError):
    pass


def _create_groq_client(api_key: str) -> Any:
    from groq import Groq
    return Groq(api_key=api_key, timeout=20.0, max_retries=0)


def _safe_specialist_endpoint(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    if not raw:
        return ""
    parsed = urlparse(raw)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme == "https" and host:
        return raw
    if parsed.scheme == "http" and host in {"127.0.0.1", "localhost", "::1"}:
        return raw
    return ""


def _multipart_audio(path: Path, *, language: str, model: str) -> tuple[bytes, str]:
    boundary = "----MaryV2STT13_14"
    audio = path.read_bytes()
    if len(audio) > 25_000_000:
        raise SpeechToTextError("Recorded microphone audio exceeds the specialist STT limit.")
    fields = [
        ("language", language or "en"),
        ("model", model or "default"),
    ]
    parts: list[bytes] = []
    for name, value in fields:
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8")
        )
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode("utf-8")
        + audio
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class DesktopSpeechToText:
    def __init__(self, *, provider: str, model: str, language: str, api_key: str | None) -> None:
        self.provider = provider.strip().lower()
        self.model = model.strip()
        self.language = language.strip() or "en"
        self.api_key = api_key
        self.client: Any | None = None
        self.local_model: Any | None = None
        self.whisper_cpp_executable: Path | None = None
        self.whisper_cpp_model: Path | None = None
        self.specialist_endpoint = ""

        if self.provider == "groq" and self.api_key:
            self.client = _create_groq_client(self.api_key)

        if self.provider in {"qwen3_asr", "qwen_asr"}:
            self.specialist_endpoint = _safe_specialist_endpoint(os.getenv("MARY_QWEN_ASR_ENDPOINT", ""))
            self.provider = "qwen3_asr"
        elif self.provider in {"fluid_audio", "fluidaudio"}:
            self.specialist_endpoint = _safe_specialist_endpoint(os.getenv("MARY_FLUID_AUDIO_ENDPOINT", ""))
            self.provider = "fluid_audio"
        elif self.provider in {"specialist_http", "http"}:
            self.specialist_endpoint = _safe_specialist_endpoint(os.getenv("MARY_STT_ENDPOINT", ""))
            self.provider = "specialist_http"

        if self.provider in {"whisper_cpp", "whisper.cpp"}:
            executable = os.getenv("MARY_WHISPER_CPP_EXECUTABLE", "").strip()
            model_path = os.getenv("MARY_WHISPER_CPP_MODEL", "").strip()
            discovered = executable or shutil.which("whisper-cli") or ""
            exe = Path(discovered).expanduser() if discovered else None
            model = Path(model_path).expanduser() if model_path else None
            if exe is not None and exe.exists() and model is not None and model.exists():
                self.whisper_cpp_executable = exe.resolve()
                self.whisper_cpp_model = model.resolve()
                self.provider = "whisper_cpp"

        if self.provider in {"faster_whisper", "local", "local_first"}:
            try:
                from faster_whisper import WhisperModel
                device = os.getenv("MARY_STT_DEVICE", "auto").strip() or "auto"
                compute = os.getenv("MARY_STT_COMPUTE_TYPE", "int8").strip() or "int8"
                self.local_model = WhisperModel(self.model, device=device, compute_type=compute)
                self.provider = "faster_whisper"
            except Exception:
                if self.provider == "local_first" and self.api_key:
                    self.provider = "groq"
                    self.client = _create_groq_client(self.api_key)

    @classmethod
    def from_environment(cls) -> "DesktopSpeechToText":
        provider = os.getenv("MARY_STT_PROVIDER", "groq")
        model = os.getenv("MARY_STT_MODEL", "whisper-large-v3-turbo")
        if provider.strip().lower() in {"faster_whisper", "local", "local_first"} and not os.getenv("MARY_STT_MODEL", "").strip():
            model = "small.en"
        if provider.strip().lower() in {"qwen3_asr", "qwen_asr"} and not os.getenv("MARY_STT_MODEL", "").strip():
            model = "qwen3-asr"
        if provider.strip().lower() in {"fluid_audio", "fluidaudio"} and not os.getenv("MARY_STT_MODEL", "").strip():
            model = "fluid-audio"
        language = os.getenv("MARY_STT_LANGUAGE", "en")
        return cls(provider=provider, model=model, language=language, api_key=os.getenv("GROQ_API_KEY"))

    @property
    def enabled(self) -> bool:
        return bool(
            (self.provider == "groq" and self.client)
            or (self.provider == "faster_whisper" and self.local_model)
            or (self.provider == "whisper_cpp" and self.whisper_cpp_executable and self.whisper_cpp_model)
            or (self.provider in {"qwen3_asr", "fluid_audio", "specialist_http"} and self.specialist_endpoint)
        )

    @property
    def status(self) -> SpeechToTextStatus:
        model = str(self.whisper_cpp_model) if self.provider == "whisper_cpp" and self.whisper_cpp_model else self.model
        local_endpoint = False
        if self.specialist_endpoint:
            local_endpoint = (urlparse(self.specialist_endpoint).hostname or "").casefold() in {"127.0.0.1", "localhost", "::1"}
        return SpeechToTextStatus(
            self.enabled,
            self.provider or "disabled",
            model,
            self.language,
            self.provider in {"faster_whisper", "whisper_cpp"} or local_endpoint,
        )

    def _transcribe_specialist(self, audio_path: Path) -> str:
        body, content_type = _multipart_audio(audio_path, language=self.language, model=self.model)
        endpoint = self.specialist_endpoint
        request = Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": content_type,
                "Accept": "application/json",
                "User-Agent": "MaryV2-STT/13.14",
            },
        )
        try:
            with urlopen(request, timeout=45) as response:  # nosec B310 - endpoint validated at configuration time
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise SpeechToTextError("Specialist STT returned an oversized response.")
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise SpeechToTextError("Specialist STT returned an invalid response object.")
            text = " ".join(str(parsed.get("text") or parsed.get("transcript") or "").split())
            return text[:16000]
        except SpeechToTextError:
            raise
        except Exception as exc:
            raise SpeechToTextError(f"Specialist STT transcription failed: {type(exc).__name__}") from exc

    def transcribe(self, path: str | Path) -> str:
        if not self.enabled:
            raise SpeechToTextError(
                "Desktop speech input is not configured. Use Groq STT, faster-whisper, whisper.cpp, or a configured specialist STT bridge."
            )
        audio_path = Path(path)
        if not audio_path.exists() or not audio_path.is_file() or audio_path.stat().st_size <= 0:
            raise SpeechToTextError("Recorded microphone audio was not found or is empty.")

        if self.provider in {"qwen3_asr", "fluid_audio", "specialist_http"}:
            text = self._transcribe_specialist(audio_path)
        elif self.provider == "faster_whisper" and self.local_model is not None:
            try:
                segments, _ = self.local_model.transcribe(str(audio_path), language=self.language, beam_size=1, vad_filter=True)
                text = " ".join(str(seg.text).strip() for seg in segments if str(seg.text).strip()).strip()
            except Exception as exc:
                raise SpeechToTextError(f"Local faster-whisper transcription failed: {exc}") from exc
        elif self.provider == "whisper_cpp" and self.whisper_cpp_executable and self.whisper_cpp_model:
            try:
                with tempfile.TemporaryDirectory(prefix="mary-whisper-cpp-") as temporary:
                    output_base = Path(temporary) / "transcript"
                    command = [
                        str(self.whisper_cpp_executable),
                        "-m", str(self.whisper_cpp_model),
                        "-f", str(audio_path),
                        "-l", self.language or "en",
                        "-nt",
                        "-otxt",
                        "-of", str(output_base),
                    ]
                    result = subprocess.run(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=45,
                        check=False,
                        text=True,
                    )
                    target = output_base.with_suffix(".txt")
                    if result.returncode != 0:
                        raise RuntimeError((result.stderr or result.stdout or "whisper.cpp failed")[-1000:])
                    text = target.read_text(encoding="utf-8").strip() if target.exists() else result.stdout.strip()
            except Exception as exc:
                raise SpeechToTextError(f"Local whisper.cpp transcription failed: {exc}") from exc
        else:
            try:
                with audio_path.open("rb") as audio_file:
                    response = self.client.audio.transcriptions.create(
                        file=(audio_path.name, audio_file.read()),
                        model=self.model,
                        response_format="json",
                        language=self.language,
                        temperature=0.0,
                        prompt="A natural conversation between Unbe and Mary Cosma in MaryV2. Preserve the spellings Unbe, Mary Cosma, and MaryV2.",
                    )
                text = str(getattr(response, "text", "") or "").strip()
            except Exception as exc:
                raise SpeechToTextError(f"Groq speech transcription failed: {exc}") from exc

        if not text:
            raise SpeechToTextError("No speech was detected in the recording.")
        return text
