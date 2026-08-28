"""Desktop text-to-speech adapter.

V2.12.8 adds an explicit *local-first* mode while keeping ElevenLabs as the
optional premium voice.  Local engines are deliberately finite/configured:
Piper when the executable+model are provided, then Windows SAPI on Windows.
Cloud fallback is opt-in so an idle/long-running Mary cannot silently consume
ElevenLabs credits.
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import tempfile
from time import monotonic
from typing import Any

from mary.expression.emotion import EmotionalState
from mary.expression.delivery_plan import DeliveryPlan
from mary.voice import (
    SpeechAudioFormat,
    SpeechRenderer,
    VoiceSettings,
    create_tts_service,
    emotion_voice_profile_name,
    resolve_emotion_voice_settings,
)
from mary.voice.providers import ElevenLabsTextToSpeechProvider


@dataclass(frozen=True)
class DesktopVoiceStatus:
    enabled: bool
    provider: str = "off"
    voice_id: str | None = None
    model: str | None = None
    local: bool = False
    premium: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "voice_id": self.voice_id,
            "model": self.model,
            "local": self.local,
            "premium": self.premium,
        }


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
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


def _piper_paths() -> tuple[Path | None, Path | None]:
    executable = os.getenv("MARY_PIPER_EXECUTABLE", "").strip()
    model = os.getenv("MARY_PIPER_MODEL", "").strip()
    exe_path = Path(executable).expanduser().resolve() if executable else None
    model_path = Path(model).expanduser().resolve() if model else None
    if exe_path is not None and (not exe_path.exists() or not exe_path.is_file()):
        exe_path = None
    if model_path is not None and (not model_path.exists() or not model_path.is_file()):
        model_path = None
    return exe_path, model_path


def _apply_delivery_plan(settings: VoiceSettings, plan: DeliveryPlan | dict[str, Any] | None) -> VoiceSettings:
    # Keep this helper pure: when a caller explicitly applies a delivery plan,
    # it performs that transformation. Mary 13.0 gates whether the live voice
    # pipeline calls it via MARY_TTS_DYNAMIC_DELIVERY so the default remains the
    # natural Voice Lab baseline.
    if plan is None:
        return settings
    values = plan.to_dict() if hasattr(plan, "to_dict") else dict(plan)
    metadata = dict(settings.metadata)
    if values.get("stability") is not None:
        metadata["stability"] = max(0.0, min(1.0, float(values["stability"])))
    if values.get("style") is not None:
        metadata["style"] = max(0.0, min(1.0, float(values["style"])))
    metadata["delivery_profile"] = str(values.get("profile") or "neutral")
    metadata["delivery_energy"] = max(0.0, min(1.0, float(values.get("energy", 0.5))))
    metadata["delivery_warmth"] = max(0.0, min(1.0, float(values.get("warmth", 0.5))))
    speed = max(0.7, min(1.2, float(values.get("pace", settings.speed))))
    return VoiceSettings(
        voice=settings.voice,
        language=settings.language,
        speed=speed,
        pitch=settings.pitch,
        volume=settings.volume,
        style=settings.style,
        emotion=settings.emotion,
        emotion_intensity=settings.emotion_intensity,
        output_format=settings.output_format,
        sample_rate=settings.sample_rate,
        metadata=metadata,
    )


class DesktopVoiceEngine:
    """Best-effort desktop TTS with local-first routing."""

    def __init__(
        self,
        *,
        service=None,
        status: DesktopVoiceStatus | None = None,
        renderer: SpeechRenderer | None = None,
        base_settings: VoiceSettings | None = None,
        local_engine: str | None = None,
        piper_executable: Path | None = None,
        piper_model: Path | None = None,
        cloud_fallback: "DesktopVoiceEngine | None" = None,
    ) -> None:
        self.service = service
        self.status = status or DesktopVoiceStatus(enabled=False)
        self.renderer = renderer or SpeechRenderer()
        self.base_settings = base_settings or VoiceSettings()
        self.local_engine = local_engine
        self.piper_executable = piper_executable
        self.piper_model = piper_model
        self.cloud_fallback = cloud_fallback

    @classmethod
    def _elevenlabs_from_environment(cls) -> "DesktopVoiceEngine":
        api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        voice_id = os.getenv("MARY_ELEVENLABS_VOICE_ID", "").strip()
        model_id = os.getenv("MARY_ELEVENLABS_MODEL", "eleven_flash_v2_5").strip()
        if not api_key or not voice_id:
            return cls(status=DesktopVoiceStatus(False, "elevenlabs", voice_id or None, model_id or None, False, True))

        stability = _env_float("MARY_TTS_STABILITY", 0.50, minimum=0.0, maximum=1.0)
        similarity = _env_float("MARY_TTS_SIMILARITY", 0.75, minimum=0.0, maximum=1.0)
        style = _env_float("MARY_TTS_STYLE", 0.0, minimum=0.0, maximum=1.0)
        speed = _env_float("MARY_TTS_SPEED", 1.0, minimum=0.7, maximum=1.2)
        speaker_boost = _env_bool("MARY_TTS_SPEAKER_BOOST", False)
        provider = ElevenLabsTextToSpeechProvider(api_key=api_key, voice_id=voice_id, model_id=model_id or "eleven_flash_v2_5", timeout=20.0)
        settings = VoiceSettings(voice=voice_id, speed=speed, output_format=SpeechAudioFormat.MP3,
            metadata={"stability": stability, "similarity_boost": similarity, "style": style, "use_speaker_boost": speaker_boost})
        return cls(service=create_tts_service(provider, settings=settings), base_settings=settings,
                   status=DesktopVoiceStatus(True, "elevenlabs", voice_id, model_id, False, True))

    @classmethod
    def from_environment(cls) -> "DesktopVoiceEngine":
        # Keep this exact default for offline/backward-compatible tests.  The
        # shipped .env.example opts into local_first for the real PC install.
        provider_name = os.getenv("MARY_TTS_PROVIDER", "off").strip().lower()
        if provider_name in {"", "off", "none", "null", "disabled"}:
            return cls()
        if provider_name == "elevenlabs":
            return cls._elevenlabs_from_environment()

        # Fast companion policy for the creator's primary Windows host:
        # prefer the configured ElevenLabs Flash voice when credentials are
        # present, otherwise fall back to the existing local-first chain.
        # This keeps cloud voice optional for portable/offline installs.
        if provider_name in {"auto_fast", "fast_voice"}:
            cloud = cls._elevenlabs_from_environment()
            if cloud.status.enabled:
                return cloud
            provider_name = "local_first"

        if provider_name in {"local", "local_first", "auto"}:
            piper_exe, piper_model = _piper_paths()
            fallback = cls._elevenlabs_from_environment() if _env_bool("MARY_TTS_ALLOW_CLOUD_FALLBACK", False) else None
            if piper_exe and piper_model:
                return cls(status=DesktopVoiceStatus(True, "piper", model=str(piper_model), local=True),
                           local_engine="piper", piper_executable=piper_exe, piper_model=piper_model,
                           cloud_fallback=fallback if fallback and fallback.status.enabled else None)
            if sys.platform == "win32":
                voice_name = os.getenv("MARY_WINDOWS_TTS_VOICE", "").strip() or None
                return cls(status=DesktopVoiceStatus(True, "windows_sapi", voice_id=voice_name, model="System.Speech", local=True),
                           local_engine="windows_sapi", cloud_fallback=fallback if fallback and fallback.status.enabled else None)
            if fallback and fallback.status.enabled:
                return fallback
            return cls(status=DesktopVoiceStatus(False, "local_first", local=True))

        if provider_name == "piper":
            piper_exe, piper_model = _piper_paths()
            return cls(status=DesktopVoiceStatus(bool(piper_exe and piper_model), "piper", model=str(piper_model) if piper_model else None, local=True),
                       local_engine="piper" if piper_exe and piper_model else None, piper_executable=piper_exe, piper_model=piper_model)
        if provider_name in {"sapi", "windows_sapi"} and sys.platform == "win32":
            return cls(status=DesktopVoiceStatus(True, "windows_sapi", voice_id=os.getenv("MARY_WINDOWS_TTS_VOICE", "").strip() or None, model="System.Speech", local=True), local_engine="windows_sapi")
        return cls(status=DesktopVoiceStatus(False, provider_name))

    def render_text(self, text: str, *, user_text: str | None = None) -> str:
        return self.renderer.render(str(text), user_text=user_text)

    def _synthesize_piper(self, text: str) -> bytes:
        if not self.piper_executable or not self.piper_model:
            raise RuntimeError("Piper is not configured.")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            target = Path(handle.name)
        try:
            command = [str(self.piper_executable), "--model", str(self.piper_model), "--output_file", str(target)]
            speaker = os.getenv("MARY_PIPER_SPEAKER", "").strip()
            if speaker:
                command += ["--speaker", speaker]
            result = subprocess.run(command, input=text.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
            if result.returncode != 0 or not target.exists() or target.stat().st_size <= 44:
                raise RuntimeError((result.stderr.decode("utf-8", errors="ignore") or "Piper synthesis failed.")[:500])
            return target.read_bytes()
        finally:
            target.unlink(missing_ok=True)

    def _synthesize_sapi(self, text: str) -> bytes:
        if sys.platform != "win32":
            raise RuntimeError("Windows SAPI is only available on Windows.")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            target = Path(handle.name)
        voice_name = os.getenv("MARY_WINDOWS_TTS_VOICE", "").strip()
        # Text and paths are supplied as PowerShell arguments rather than
        # interpolated into executable script syntax.
        script = (
            "param([string]$Text,[string]$Out,[string]$Voice,[int]$Rate); "
            "Add-Type -AssemblyName System.Speech; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "if($Voice){ try{$s.SelectVoice($Voice)}catch{} }; $s.Rate=$Rate; "
            "$s.SetOutputToWaveFile($Out); $s.Speak($Text); $s.Dispose();"
        )
        speed = _env_float("MARY_TTS_SPEED", 1.0, minimum=0.7, maximum=1.2)
        rate = int(round((speed - 1.0) * 10))
        try:
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script,
                                     "-Text", text, "-Out", str(target), "-Voice", voice_name, "-Rate", str(rate)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
            if result.returncode != 0 or not target.exists() or target.stat().st_size <= 44:
                raise RuntimeError((result.stderr.decode("utf-8", errors="ignore") or "Windows SAPI synthesis failed.")[:500])
            return target.read_bytes()
        finally:
            target.unlink(missing_ok=True)

    def _local_synthesize(self, spoken_text: str) -> dict[str, Any]:
        if self.local_engine == "piper":
            audio = self._synthesize_piper(spoken_text)
        elif self.local_engine == "windows_sapi":
            audio = self._synthesize_sapi(spoken_text)
        else:
            raise RuntimeError("No local TTS engine is configured.")
        return {**self.status.to_dict(), "status": "success", "format": "wav", "mime_type": "audio/wav",
                "audio_base64": base64.b64encode(audio).decode("ascii"), "audio_size": len(audio), "spoken_text": spoken_text,
                "emotion": "presentation", "emotion_intensity": 0.0, "emotion_profile": "local_default"}

    def synthesize(self, text: str, *, user_text: str | None = None, emotional_state: EmotionalState | None = None, delivery_plan: DeliveryPlan | dict[str, Any] | None = None) -> dict[str, Any]:
        """Render + synthesize speech and attach display-safe timing metadata."""

        total_started = monotonic()
        render_started = total_started
        spoken_text = self.render_text(text, user_text=user_text)
        render_ms = round((monotonic() - render_started) * 1000.0, 2)

        def finish(payload: dict[str, Any], synth_started: float | None = None) -> dict[str, Any]:
            now = monotonic()
            synthesis_ms = 0.0 if synth_started is None else max(0.0, (now - synth_started) * 1000.0)
            payload["timings"] = {
                "speech_render_ms": render_ms,
                "tts_synthesis_ms": round(synthesis_ms, 2),
                "voice_total_ms": round((now - total_started) * 1000.0, 2),
            }
            return payload

        if not spoken_text:
            return finish({**self.status.to_dict(), "status": "empty", "spoken_text": ""})

        if self.local_engine:
            synth_started = monotonic()
            try:
                payload = self._local_synthesize(spoken_text)
            except Exception as exc:
                if self.cloud_fallback and self.cloud_fallback.status.enabled:
                    payload = self.cloud_fallback.synthesize(
                        text,
                        user_text=user_text,
                        emotional_state=emotional_state,
                        delivery_plan=delivery_plan,
                    )
                    payload["fallback_from"] = self.status.provider
                    payload["local_error"] = f"{type(exc).__name__}: {exc}"
                    # Preserve the outer local-attempt wall time in addition to
                    # any nested cloud-fallback timing.
                    return finish(payload, synth_started)
                return finish(
                    {
                        **self.status.to_dict(),
                        "status": "failed",
                        "spoken_text": spoken_text,
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                    synth_started,
                )
            return finish(payload, synth_started)

        if self.service is None or not self.status.enabled:
            return finish({**self.status.to_dict(), "status": "disabled", "spoken_text": spoken_text})

        active_settings = self.base_settings
        # Stage 12 separates two concerns that used to share one switch.
        # Emotion-profile shaping remains opt-in, but TurnMind's bounded
        # performer delivery is on by default so Mary's represented sarcasm,
        # warmth, excitement, firmness, etc. are actually audible instead of
        # being flattened back to one Voice Lab baseline.  Set
        # MARY_TTS_PERFORMANCE_DELIVERY=false to disable this presentation-only
        # layer without changing Mary Core state.
        if _env_bool("MARY_TTS_DYNAMIC_DELIVERY", False):
            active_settings = resolve_emotion_voice_settings(self.base_settings, emotional_state)
        if _env_bool("MARY_TTS_PERFORMANCE_DELIVERY", True):
            active_settings = _apply_delivery_plan(active_settings, delivery_plan)
        synth_started = monotonic()
        speech = self.service.synthesize(spoken_text, settings=active_settings)
        if not speech.is_successful:
            return finish(
                {**self.status.to_dict(), "status": speech.status.value, "spoken_text": spoken_text},
                synth_started,
            )
        mime_type = "audio/mpeg" if speech.format == SpeechAudioFormat.MP3 else "application/octet-stream"
        return finish(
            {
                **self.status.to_dict(),
                "status": speech.status.value,
                "format": speech.format.value,
                "mime_type": mime_type,
                "audio_base64": base64.b64encode(speech.audio).decode("ascii"),
                "audio_size": len(speech.audio),
                "spoken_text": spoken_text,
                "emotion": active_settings.emotion.value if active_settings.emotion else "neutral",
                "emotion_intensity": active_settings.emotion_intensity,
                "emotion_profile": emotion_voice_profile_name(emotional_state),
                "delivery_profile": active_settings.metadata.get("delivery_profile"),
                "voice_settings": {
                    "stability": active_settings.metadata.get("stability"),
                    "similarity_boost": active_settings.metadata.get("similarity_boost"),
                    "style": active_settings.metadata.get("style"),
                    "speed": active_settings.speed,
                },
            },
            synth_started,
        )
