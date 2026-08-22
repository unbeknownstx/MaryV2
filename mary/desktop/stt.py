"""Provider-independent speech-to-text support for MaryV2 Desktop.

12.8 adds optional local ``faster-whisper`` while retaining Groq as the simple
cloud fallback.  The dependency is optional so the first desktop boot is not
blocked by a large local model install.
"""
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
    local: bool = False

    def to_dict(self) -> dict[str, Any]: return asdict(self)

class SpeechToTextError(RuntimeError): pass

def _create_groq_client(api_key: str) -> Any:
    from groq import Groq
    return Groq(api_key=api_key, timeout=20.0, max_retries=0)

class DesktopSpeechToText:
    def __init__(self, *, provider: str, model: str, language: str, api_key: str | None) -> None:
        self.provider=provider.strip().lower(); self.model=model.strip(); self.language=language.strip() or "en"; self.api_key=api_key
        self.client: Any|None=None; self.local_model: Any|None=None
        if self.provider=="groq" and self.api_key: self.client=_create_groq_client(self.api_key)
        if self.provider in {"faster_whisper","local","local_first"}:
            try:
                from faster_whisper import WhisperModel
                device=os.getenv("MARY_STT_DEVICE","auto").strip() or "auto"
                compute=os.getenv("MARY_STT_COMPUTE_TYPE","int8").strip() or "int8"
                self.local_model=WhisperModel(self.model,device=device,compute_type=compute)
                self.provider="faster_whisper"
            except Exception:
                if self.provider=="local_first" and self.api_key:
                    self.provider="groq"; self.client=_create_groq_client(self.api_key)

    @classmethod
    def from_environment(cls) -> "DesktopSpeechToText":
        provider=os.getenv("MARY_STT_PROVIDER","groq")
        model=os.getenv("MARY_STT_MODEL", "whisper-large-v3-turbo")
        if provider.strip().lower() in {"faster_whisper", "local", "local_first"} and not os.getenv("MARY_STT_MODEL", "").strip():
            model = "small.en"
        language=os.getenv("MARY_STT_LANGUAGE","en")
        return cls(provider=provider,model=model,language=language,api_key=os.getenv("GROQ_API_KEY"))

    @property
    def enabled(self)->bool: return bool((self.provider=="groq" and self.client) or (self.provider=="faster_whisper" and self.local_model))
    @property
    def status(self)->SpeechToTextStatus: return SpeechToTextStatus(self.enabled,self.provider or "disabled",self.model,self.language,self.provider=="faster_whisper")

    def transcribe(self,path:str|Path)->str:
        if not self.enabled: raise SpeechToTextError("Desktop speech input is not configured. Use Groq STT or install faster-whisper for local STT.")
        audio_path=Path(path)
        if not audio_path.exists() or not audio_path.is_file() or audio_path.stat().st_size<=0: raise SpeechToTextError("Recorded microphone audio was not found or is empty.")
        if self.provider=="faster_whisper" and self.local_model is not None:
            try:
                segments,_=self.local_model.transcribe(str(audio_path),language=self.language,beam_size=1,vad_filter=True)
                text=" ".join(str(seg.text).strip() for seg in segments if str(seg.text).strip()).strip()
            except Exception as exc: raise SpeechToTextError(f"Local faster-whisper transcription failed: {exc}") from exc
        else:
            try:
                with audio_path.open("rb") as audio_file:
                    response=self.client.audio.transcriptions.create(file=(audio_path.name,audio_file.read()),model=self.model,response_format="json",language=self.language,temperature=0.0,
                        prompt="A natural conversation between Unbe and Mary Cosma in MaryV2. Preserve the spellings Unbe, Mary Cosma, and MaryV2.")
                text=str(getattr(response,"text","") or "").strip()
            except Exception as exc: raise SpeechToTextError(f"Groq speech transcription failed: {exc}") from exc
        if not text: raise SpeechToTextError("No speech was detected in the recording.")
        return text
