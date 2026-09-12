"""Bounded home-node sensor capabilities for realtime Mary experiences.

Sensors produce ephemeral evidence only. They never write Mary memory, identity,
relationship state, or authorize follow-on actions. Both capabilities remain
local-device opt-in through DeviceExecutionPermissions.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path
import tempfile
from typing import Any

from .capabilities import CapabilityDescriptor

AUDIO_TRANSCRIBE_CAPABILITY = "sensor.audio_transcribe"
SCREEN_CAPTURE_CAPABILITY = "sensor.screen_capture"
SENSOR_CAPABILITIES = {AUDIO_TRANSCRIBE_CAPABILITY, SCREEN_CAPTURE_CAPABILITY}

MAX_AUDIO_BYTES = 4 * 1024 * 1024
MAX_SCREEN_BYTES = 1_500_000


def _decode_b64(value: Any, *, limit: int, label: str) -> bytes:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} payload is required.")
    # Avoid allocating an arbitrarily large decoded buffer.
    if len(text) > int(limit * 1.38) + 16:
        raise ValueError(f"{label} payload exceeds the bounded size limit.")
    try:
        data = base64.b64decode(text, validate=True)
    except Exception as exc:
        raise ValueError(f"{label} payload must be valid base64.") from exc
    if not data or len(data) > limit:
        raise ValueError(f"{label} payload is empty or exceeds the bounded size limit.")
    return data


def sanitize_sensor_task_args(capability: str, args: dict[str, Any] | None) -> dict[str, Any]:
    values = dict(args or {})
    if capability == AUDIO_TRANSCRIBE_CAPABILITY:
        raw = _decode_b64(values.get("audio_base64"), limit=MAX_AUDIO_BYTES, label="audio")
        suffix = str(values.get("suffix") or ".wav").strip().lower()
        if suffix not in {".wav", ".mp3", ".m4a", ".ogg", ".flac"}:
            raise ValueError("Audio suffix must be wav, mp3, m4a, ogg, or flac.")
        language = "".join(ch for ch in str(values.get("language") or "en") if ch.isalnum() or ch in {"-", "_"})[:16] or "en"
        return {
            "audio_base64": base64.b64encode(raw).decode("ascii"),
            "suffix": suffix,
            "language": language,
        }
    if capability == SCREEN_CAPTURE_CAPABILITY:
        try:
            max_width = max(320, min(1920, int(values.get("max_width", 1280) or 1280)))
            quality = max(35, min(90, int(values.get("quality", 70) or 70)))
        except (TypeError, ValueError) as exc:
            raise ValueError("Screen capture max_width/quality must be integers.") from exc
        return {
            "max_width": max_width,
            "quality": quality,
            "all_screens": bool(values.get("all_screens", False)),
        }
    raise ValueError(f"Unsupported sensor capability: {capability}")


def sanitize_sensor_result(capability: str, result: dict[str, Any] | None) -> dict[str, Any]:
    values = dict(result or {})
    if capability == AUDIO_TRANSCRIBE_CAPABILITY:
        text = " ".join(str(values.get("text") or "").split())[:12_000]
        if not text:
            return {}
        return {
            "text": text,
            "provider": str(values.get("provider") or "unknown")[:80],
            "model": str(values.get("model") or "unknown")[:180],
            "language": str(values.get("language") or "")[:16],
            "local": bool(values.get("local", False)),
            "privacy": "audio bytes were ephemeral task input; transcript is evidence, not memory truth",
        }
    if capability == SCREEN_CAPTURE_CAPABILITY:
        image = _decode_b64(values.get("image_base64"), limit=MAX_SCREEN_BYTES, label="screen image")
        width = max(1, min(8192, int(values.get("width", 1) or 1)))
        height = max(1, min(8192, int(values.get("height", 1) or 1)))
        return {
            "image_base64": base64.b64encode(image).decode("ascii"),
            "mime_type": "image/jpeg",
            "width": width,
            "height": height,
            "sha256": hashlib.sha256(image).hexdigest(),
            "privacy": "ephemeral screenshot evidence; no automatic memory write or action authority",
        }
    return {}


def _stt_capability() -> CapabilityDescriptor | None:
    try:
        from mary.desktop.stt import DesktopSpeechToText
        stt = DesktopSpeechToText.from_environment()
        status = stt.status
    except Exception:
        return None
    if not status.enabled:
        return None
    return CapabilityDescriptor(
        name=AUDIO_TRANSCRIBE_CAPABILITY,
        available=True,
        private=bool(status.local),
        local=bool(status.local),
        cost="local" if status.local else "provider_policy",
        latency="realtime",
        metadata={
            "provider": status.provider,
            "model": status.model,
            "language": status.language,
            "max_audio_bytes": MAX_AUDIO_BYTES,
        },
    )


def _screen_capability() -> CapabilityDescriptor | None:
    try:
        from PIL import ImageGrab  # noqa: F401
    except Exception:
        return None
    return CapabilityDescriptor(
        name=SCREEN_CAPTURE_CAPABILITY,
        available=True,
        private=True,
        local=True,
        cost="free",
        latency="interactive",
        metadata={
            "backend": "pillow_imagegrab",
            "max_result_bytes": MAX_SCREEN_BYTES,
            "explicit_permission": True,
        },
    )


def sensor_capabilities() -> list[CapabilityDescriptor]:
    output: list[CapabilityDescriptor] = []
    stt = _stt_capability()
    if stt is not None:
        output.append(stt)
    screen = _screen_capability()
    if screen is not None:
        output.append(screen)
    return output


def execute_audio_transcribe(args: dict[str, Any]) -> dict[str, Any]:
    from mary.desktop.stt import DesktopSpeechToText

    values = sanitize_sensor_task_args(AUDIO_TRANSCRIBE_CAPABILITY, args)
    audio = _decode_b64(values["audio_base64"], limit=MAX_AUDIO_BYTES, label="audio")
    stt = DesktopSpeechToText.from_environment()
    if not stt.enabled:
        raise RuntimeError("Speech-to-text is not configured on this node.")
    # A task may request a language, but never a provider/model/path. Those are
    # owned by the device environment so Core cannot cause arbitrary execution.
    stt.language = str(values.get("language") or stt.language)[:16]
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="mary-node-stt-", suffix=values["suffix"], delete=False) as handle:
            handle.write(audio)
            temporary_path = Path(handle.name)
        text = stt.transcribe(temporary_path)
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    status = stt.status
    return {
        "text": text,
        "provider": status.provider,
        "model": status.model,
        "language": status.language,
        "local": status.local,
    }


def execute_screen_capture(args: dict[str, Any]) -> dict[str, Any]:
    values = sanitize_sensor_task_args(SCREEN_CAPTURE_CAPABILITY, args)
    try:
        from PIL import ImageGrab
    except Exception as exc:
        raise RuntimeError("Pillow ImageGrab is not available on this node.") from exc

    try:
        image = ImageGrab.grab(all_screens=bool(values["all_screens"]))
    except TypeError:
        image = ImageGrab.grab()
    if image is None:
        raise RuntimeError("Screen capture returned no image.")
    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    width, height = image.size
    max_width = int(values["max_width"])
    if width > max_width:
        ratio = max_width / float(width)
        image = image.resize((max_width, max(1, int(height * ratio))))
        width, height = image.size

    quality = int(values["quality"])
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    data = buffer.getvalue()
    while len(data) > MAX_SCREEN_BYTES and quality > 35:
        quality = max(35, quality - 10)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        data = buffer.getvalue()
    if len(data) > MAX_SCREEN_BYTES:
        raise RuntimeError("Bounded screenshot still exceeds the maximum result size.")
    return {
        "image_base64": base64.b64encode(data).decode("ascii"),
        "mime_type": "image/jpeg",
        "width": width,
        "height": height,
    }
