"""Mobile voice transport for MaryV2.

This module bridges the existing MaryV2 voice/STT engines to browser and native
mobile clients without exposing provider credentials.  It deliberately keeps
provider selection on Mary's host: the phone asks Mary for speech/audio, while
Mary's configured runtime decides whether ElevenLabs, Piper, Windows SAPI, or a
local/cloud STT provider is available.

The mobile client always retains a device speech fallback, so server-side voice
remains optional and MaryV2 can still run on hosts where no TTS provider exists.
"""

from __future__ import annotations

import base64
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import tempfile
from threading import RLock
from time import monotonic
from typing import Any

from mary.desktop.stt import DesktopSpeechToText
from mary.desktop.voice import DesktopVoiceEngine


DEFAULT_TTS_MAX_CHARS = 4_000
DEFAULT_STT_MAX_BYTES = 12_000_000
DEFAULT_CACHE_ITEMS = 12
DEFAULT_CACHE_BYTES = 24_000_000


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        value = int(raw) if raw else int(default)
    except (TypeError, ValueError):
        value = int(default)
    return max(minimum, min(maximum, value))


def _status_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "to_dict"):
        try:
            result = value.to_dict()
            if isinstance(result, dict):
                return dict(result)
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


@dataclass(frozen=True)
class MobileSpeechAudio:
    audio: bytes
    mime_type: str
    metadata: dict[str, Any]
    cached: bool = False

    @property
    def successful(self) -> bool:
        return bool(self.audio) and str(self.metadata.get("status") or "") == "success"


class MobileSpeechService:
    """Bounded server-side TTS/STT adapter for the mobile surface."""

    def __init__(
        self,
        *,
        voice_engine: Any | None = None,
        stt_engine: Any | None = None,
        tts_max_chars: int | None = None,
        stt_max_bytes: int | None = None,
        cache_items: int | None = None,
        cache_bytes: int | None = None,
    ) -> None:
        self.voice_engine = voice_engine or DesktopVoiceEngine.from_environment()
        self.stt_engine = stt_engine or DesktopSpeechToText.from_environment()
        self.tts_max_chars = int(
            tts_max_chars
            if tts_max_chars is not None
            else _env_int(
                "MARY_MOBILE_TTS_MAX_CHARS",
                DEFAULT_TTS_MAX_CHARS,
                minimum=200,
                maximum=20_000,
            )
        )
        self.stt_max_bytes = int(
            stt_max_bytes
            if stt_max_bytes is not None
            else _env_int(
                "MARY_MOBILE_STT_MAX_BYTES",
                DEFAULT_STT_MAX_BYTES,
                minimum=256_000,
                maximum=50_000_000,
            )
        )
        self.cache_items = int(
            cache_items
            if cache_items is not None
            else _env_int(
                "MARY_MOBILE_TTS_CACHE_ITEMS",
                DEFAULT_CACHE_ITEMS,
                minimum=0,
                maximum=64,
            )
        )
        self.cache_bytes = int(
            cache_bytes
            if cache_bytes is not None
            else _env_int(
                "MARY_MOBILE_TTS_CACHE_BYTES",
                DEFAULT_CACHE_BYTES,
                minimum=0,
                maximum=128_000_000,
            )
        )
        self._lock = RLock()
        self._tts_lock = RLock()
        self._stt_lock = RLock()
        self._cache: OrderedDict[str, MobileSpeechAudio] = OrderedDict()
        self._cache_size = 0
        self._last_tts: dict[str, Any] = {}
        self._last_stt: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        voice_status = _status_dict(getattr(self.voice_engine, "status", None))
        stt_status = _status_dict(getattr(self.stt_engine, "status", None))
        tts_enabled = bool(voice_status.get("enabled"))
        stt_enabled = bool(stt_status.get("enabled"))
        with self._lock:
            cache_items = len(self._cache)
            cache_bytes = self._cache_size
            last_tts = dict(self._last_tts)
            last_stt = dict(self._last_stt)
        return _json_safe(
            {
                "tts": {
                    **voice_status,
                    "enabled": tts_enabled,
                    "server_available": tts_enabled,
                    "device_fallback": True,
                    "max_chars": self.tts_max_chars,
                    "cache_items": cache_items,
                    "cache_bytes": cache_bytes,
                    "last": last_tts,
                },
                "stt": {
                    **stt_status,
                    "enabled": stt_enabled,
                    "server_available": stt_enabled,
                    "browser_fallback": True,
                    "max_bytes": self.stt_max_bytes,
                    "last": last_stt,
                },
            }
        )

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------

    def _cache_key(
        self,
        text: str,
        *,
        user_text: str | None,
        delivery_plan: dict[str, Any] | None,
    ) -> str:
        voice_status = _status_dict(getattr(self.voice_engine, "status", None))
        payload = {
            "text": text,
            "user_text": user_text or "",
            "delivery_plan": delivery_plan or {},
            "provider": voice_status.get("provider"),
            "voice_id": voice_status.get("voice_id"),
            "model": voice_status.get("model"),
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _get_cached(self, key: str) -> MobileSpeechAudio | None:
        if self.cache_items <= 0 or self.cache_bytes <= 0:
            return None
        with self._lock:
            item = self._cache.get(key)
            if item is None:
                return None
            self._cache.move_to_end(key)
            return MobileSpeechAudio(
                audio=item.audio,
                mime_type=item.mime_type,
                metadata=dict(item.metadata),
                cached=True,
            )

    def _put_cached(self, key: str, item: MobileSpeechAudio) -> None:
        if self.cache_items <= 0 or self.cache_bytes <= 0 or not item.audio:
            return
        if len(item.audio) > self.cache_bytes:
            return
        with self._lock:
            previous = self._cache.pop(key, None)
            if previous is not None:
                self._cache_size -= len(previous.audio)
            stored = MobileSpeechAudio(
                audio=bytes(item.audio),
                mime_type=item.mime_type,
                metadata=dict(item.metadata),
                cached=False,
            )
            self._cache[key] = stored
            self._cache_size += len(stored.audio)
            while self._cache and (
                len(self._cache) > self.cache_items
                or self._cache_size > self.cache_bytes
            ):
                _, removed = self._cache.popitem(last=False)
                self._cache_size -= len(removed.audio)

    def synthesize(
        self,
        text: str,
        *,
        user_text: str | None = None,
        delivery_plan: dict[str, Any] | None = None,
    ) -> MobileSpeechAudio:
        value = str(text or "").strip()
        if not value:
            raise ValueError("Speech text cannot be empty.")
        if len(value) > self.tts_max_chars:
            raise ValueError(
                f"Speech text is too long. Maximum is {self.tts_max_chars} characters."
            )

        key = self._cache_key(
            value,
            user_text=str(user_text or "")[:4_000] or None,
            delivery_plan=dict(delivery_plan or {}),
        )
        cached = self._get_cached(key)
        if cached is not None:
            with self._lock:
                self._last_tts = {
                    "status": "success",
                    "provider": cached.metadata.get("provider"),
                    "model": cached.metadata.get("model"),
                    "cached": True,
                    "audio_size": len(cached.audio),
                }
            return cached

        voice_status = _status_dict(getattr(self.voice_engine, "status", None))
        if not voice_status.get("enabled"):
            metadata = {
                **voice_status,
                "status": "disabled",
                "server_available": False,
                "reason": "No server-side TTS provider is configured on this Mary host.",
            }
            with self._lock:
                self._last_tts = dict(metadata)
            return MobileSpeechAudio(b"", "", metadata)

        started = monotonic()
        with self._tts_lock:
            payload = self.voice_engine.synthesize(
                value,
                user_text=str(user_text or "")[:4_000] or None,
                delivery_plan=dict(delivery_plan or {}),
            )
        elapsed_ms = round((monotonic() - started) * 1000.0, 2)
        metadata = dict(payload or {})
        encoded = str(metadata.pop("audio_base64", "") or "")
        try:
            audio = base64.b64decode(encoded, validate=True) if encoded else b""
        except Exception as exc:
            raise RuntimeError("Mary's TTS provider returned invalid audio data.") from exc

        mime_type = str(metadata.get("mime_type") or "").strip()
        if not mime_type:
            fmt = str(metadata.get("format") or "").strip().lower()
            mime_type = {
                "mp3": "audio/mpeg",
                "wav": "audio/wav",
                "ogg": "audio/ogg",
                "opus": "audio/ogg; codecs=opus",
                "flac": "audio/flac",
            }.get(fmt, "application/octet-stream")

        metadata["mobile_transport_ms"] = elapsed_ms
        metadata["audio_size"] = len(audio)
        metadata["server_available"] = bool(audio)
        metadata["cached"] = False
        result = MobileSpeechAudio(audio, mime_type, _json_safe(metadata))

        with self._lock:
            self._last_tts = {
                "status": metadata.get("status"),
                "provider": metadata.get("provider"),
                "model": metadata.get("model"),
                "voice_id": metadata.get("voice_id"),
                "audio_size": len(audio),
                "cached": False,
                "elapsed_ms": elapsed_ms,
            }
        if result.successful:
            self._put_cached(key, result)
        return result

    # ------------------------------------------------------------------
    # STT
    # ------------------------------------------------------------------

    @staticmethod
    def _suffix_for_audio(*, filename: str | None, content_type: str | None) -> str:
        candidate = Path(str(filename or "")).suffix.lower()
        allowed = {".wav", ".mp3", ".mp4", ".m4a", ".flac", ".ogg", ".webm"}
        if candidate in allowed:
            return candidate
        mime = str(content_type or "").split(";", 1)[0].strip().lower()
        explicit = {
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/mpeg": ".mp3",
            "audio/mp4": ".m4a",
            "audio/x-m4a": ".m4a",
            "audio/flac": ".flac",
            "audio/ogg": ".ogg",
            "audio/webm": ".webm",
        }.get(mime)
        if explicit:
            return explicit
        guessed = mimetypes.guess_extension(mime) if mime else None
        return guessed if guessed in allowed else ".webm"

    def transcribe(
        self,
        audio: bytes,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(audio, (bytes, bytearray)):
            raise TypeError("Recorded audio must be bytes.")
        raw = bytes(audio)
        if not raw:
            raise ValueError("Recorded audio is empty.")
        if len(raw) > self.stt_max_bytes:
            raise ValueError(
                f"Recorded audio is too large. Maximum is {self.stt_max_bytes} bytes."
            )

        stt_status = _status_dict(getattr(self.stt_engine, "status", None))
        if not stt_status.get("enabled"):
            return {
                **stt_status,
                "status": "disabled",
                "server_available": False,
                "text": "",
            }

        suffix = self._suffix_for_audio(filename=filename, content_type=content_type)
        started = monotonic()
        target: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix="mary_mobile_", suffix=suffix, delete=False) as handle:
                handle.write(raw)
                target = Path(handle.name)
            with self._stt_lock:
                text = str(self.stt_engine.transcribe(target) or "").strip()
        finally:
            if target is not None:
                target.unlink(missing_ok=True)

        elapsed_ms = round((monotonic() - started) * 1000.0, 2)
        payload = {
            **stt_status,
            "status": "success" if text else "empty",
            "server_available": True,
            "text": text,
            "audio_size": len(raw),
            "elapsed_ms": elapsed_ms,
        }
        with self._lock:
            self._last_stt = {
                "status": payload["status"],
                "provider": payload.get("provider"),
                "model": payload.get("model"),
                "audio_size": len(raw),
                "elapsed_ms": elapsed_ms,
            }
        return _json_safe(payload)
