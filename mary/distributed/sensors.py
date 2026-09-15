"""Bounded home-node sensor capabilities for realtime Mary experiences.

Sensors produce ephemeral evidence only. They never write Mary memory, identity,
relationship state, or authorize follow-on actions. All capabilities remain
local-device opt-in through DeviceExecutionPermissions.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .capabilities import CapabilityDescriptor

AUDIO_TRANSCRIBE_CAPABILITY = "sensor.audio_transcribe"
SCREEN_CAPTURE_CAPABILITY = "sensor.screen_capture"
SCREEN_DESCRIBE_CAPABILITY = "sensor.screen_describe"
SENSOR_CAPABILITIES = {
    AUDIO_TRANSCRIBE_CAPABILITY,
    SCREEN_CAPTURE_CAPABILITY,
    SCREEN_DESCRIBE_CAPABILITY,
}

MAX_AUDIO_BYTES = 4 * 1024 * 1024
MAX_SCREEN_BYTES = 1_500_000
MAX_VISION_RESPONSE_BYTES = 1_000_000


def _decode_b64(value: Any, *, limit: int, label: str) -> bytes:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} payload is required.")
    if len(text) > int(limit * 1.38) + 16:
        raise ValueError(f"{label} payload exceeds the bounded size limit.")
    try:
        data = base64.b64decode(text, validate=True)
    except Exception as exc:
        raise ValueError(f"{label} payload must be valid base64.") from exc
    if not data or len(data) > limit:
        raise ValueError(f"{label} payload is empty or exceeds the bounded size limit.")
    return data


def _safe_endpoint(value: str) -> str:
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


def _vision_config() -> tuple[str, str]:
    requested = str(os.getenv("MARY_VISION_PROVIDER", "")).strip().casefold()
    if requested in {"omniparser", "omni_parser"}:
        endpoint = _safe_endpoint(os.getenv("MARY_OMNIPARSER_ENDPOINT", ""))
        return ("omniparser", endpoint)
    if requested in {"llama_cpp_mtmd", "llama_cpp", "mtmd"}:
        endpoint = _safe_endpoint(os.getenv("MARY_LLAMA_CPP_VLM_URL", ""))
        return ("llama_cpp_mtmd", endpoint)

    omni = _safe_endpoint(os.getenv("MARY_OMNIPARSER_ENDPOINT", ""))
    if omni:
        return ("omniparser", omni)
    mtmd = _safe_endpoint(os.getenv("MARY_LLAMA_CPP_VLM_URL", ""))
    if mtmd:
        return ("llama_cpp_mtmd", mtmd)
    return ("", "")


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
    if capability in {SCREEN_CAPTURE_CAPABILITY, SCREEN_DESCRIBE_CAPABILITY}:
        try:
            max_width = max(320, min(1920, int(values.get("max_width", 1280) or 1280)))
            quality = max(35, min(90, int(values.get("quality", 70) or 70)))
        except (TypeError, ValueError) as exc:
            raise ValueError("Screen sensor max_width/quality must be integers.") from exc
        output = {
            "max_width": max_width,
            "quality": quality,
            "all_screens": bool(values.get("all_screens", False)),
        }
        if capability == SCREEN_DESCRIBE_CAPABILITY:
            mode = str(values.get("mode") or "scene").strip().casefold()
            if mode not in {"scene", "ui", "stream"}:
                raise ValueError("Screen description mode must be scene, ui, or stream.")
            output["mode"] = mode
        return output
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
    if capability == SCREEN_DESCRIBE_CAPABILITY:
        description = " ".join(str(values.get("description") or "").split())[:12_000]
        if not description:
            return {}
        elements: list[dict[str, Any]] = []
        for raw in list(values.get("elements") or [])[:64]:
            if not isinstance(raw, dict):
                continue
            elements.append({
                "label": " ".join(str(raw.get("label") or raw.get("text") or "").split())[:240],
                "kind": str(raw.get("kind") or raw.get("type") or "unknown")[:80],
                "confidence": max(0.0, min(1.0, float(raw.get("confidence", 0.0) or 0.0))),
            })
        return {
            "description": description,
            "elements": elements,
            "provider": str(values.get("provider") or "unknown")[:80],
            "model": str(values.get("model") or "unknown")[:180],
            "source_sha256": str(values.get("source_sha256") or "")[:64],
            "privacy": "ephemeral visual interpretation; evidence only, not memory truth or computer-control authority",
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


def _screen_describe_capability() -> CapabilityDescriptor | None:
    try:
        from PIL import ImageGrab  # noqa: F401
    except Exception:
        return None
    provider, endpoint = _vision_config()
    if not provider or not endpoint:
        return None
    local = (urlparse(endpoint).hostname or "").casefold() in {"127.0.0.1", "localhost", "::1"}
    return CapabilityDescriptor(
        name=SCREEN_DESCRIBE_CAPABILITY,
        available=True,
        private=local,
        local=local,
        cost="local" if local else "provider_policy",
        latency="interactive",
        metadata={
            "backend": provider,
            "explicit_permission": True,
            "evidence_only": True,
            "computer_control": False,
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
    described = _screen_describe_capability()
    if described is not None:
        output.append(described)
    return output


def execute_audio_transcribe(args: dict[str, Any]) -> dict[str, Any]:
    from mary.desktop.stt import DesktopSpeechToText

    values = sanitize_sensor_task_args(AUDIO_TRANSCRIBE_CAPABILITY, args)
    audio = _decode_b64(values["audio_base64"], limit=MAX_AUDIO_BYTES, label="audio")
    stt = DesktopSpeechToText.from_environment()
    if not stt.enabled:
        raise RuntimeError("Speech-to-text is not configured on this node.")
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


def _capture_screen(values: dict[str, Any]) -> tuple[bytes, int, int]:
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
    return data, width, height


def execute_screen_capture(args: dict[str, Any]) -> dict[str, Any]:
    values = sanitize_sensor_task_args(SCREEN_CAPTURE_CAPABILITY, args)
    data, width, height = _capture_screen(values)
    return {
        "image_base64": base64.b64encode(data).decode("ascii"),
        "mime_type": "image/jpeg",
        "width": width,
        "height": height,
    }


def _vision_prompt(mode: str) -> str:
    if mode == "ui":
        return (
            "Describe the visible user interface as neutral evidence. Identify the foreground app, major panels, "
            "visible status/errors, and important interactive regions. Do not infer private intent and do not give control instructions."
        )
    if mode == "stream":
        return (
            "Describe what is visibly happening on screen for a livestream cohost. Be concise, factual, and avoid reading secrets, tokens, "
            "passwords, private messages, or hidden/system content. Return only observations useful for conversational awareness."
        )
    return (
        "Describe the visible screen as concise factual evidence: foreground application, major content, and any salient visible change. "
        "Do not infer private thoughts and do not propose computer actions."
    )


def _describe_with_omniparser(endpoint: str, image: bytes, mode: str) -> dict[str, Any]:
    payload = json.dumps({
        "image_base64": base64.b64encode(image).decode("ascii"),
        "mode": mode,
    }).encode("utf-8")
    request = Request(
        endpoint,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "MaryV2-Vision/13.14"},
    )
    with urlopen(request, timeout=45) as response:  # nosec B310 - endpoint is device configuration validated above
        raw = response.read(MAX_VISION_RESPONSE_BYTES + 1)
    if len(raw) > MAX_VISION_RESPONSE_BYTES:
        raise RuntimeError("Visual specialist returned an oversized response.")
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError("Visual specialist returned an invalid response object.")
    description = parsed.get("description") or parsed.get("text") or parsed.get("summary") or ""
    return {
        "description": description,
        "elements": list(parsed.get("elements") or parsed.get("regions") or [])[:64],
        "provider": "omniparser",
        "model": str(parsed.get("model") or "omniparser")[:180],
    }


def _describe_with_mtmd(endpoint: str, image: bytes, mode: str) -> dict[str, Any]:
    target = endpoint if endpoint.endswith("/v1/chat/completions") else endpoint + "/v1/chat/completions"
    data_uri = "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")
    payload = json.dumps({
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": _vision_prompt(mode)},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        }],
        "temperature": 0.1,
        "max_tokens": 700,
    }).encode("utf-8")
    request = Request(
        target,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "MaryV2-Vision/13.14"},
    )
    with urlopen(request, timeout=60) as response:  # nosec B310 - endpoint is device configuration validated above
        raw = response.read(MAX_VISION_RESPONSE_BYTES + 1)
    if len(raw) > MAX_VISION_RESPONSE_BYTES:
        raise RuntimeError("llama.cpp multimodal endpoint returned an oversized response.")
    parsed = json.loads(raw.decode("utf-8"))
    choices = list(parsed.get("choices") or []) if isinstance(parsed, dict) else []
    message = dict(choices[0].get("message") or {}) if choices and isinstance(choices[0], dict) else {}
    return {
        "description": message.get("content") or "",
        "elements": [],
        "provider": "llama_cpp_mtmd",
        "model": str(parsed.get("model") or "llama_cpp_mtmd")[:180] if isinstance(parsed, dict) else "llama_cpp_mtmd",
    }


def execute_screen_describe(args: dict[str, Any]) -> dict[str, Any]:
    values = sanitize_sensor_task_args(SCREEN_DESCRIBE_CAPABILITY, args)
    provider, endpoint = _vision_config()
    if not provider or not endpoint:
        raise RuntimeError("No configured visual-description specialist is available on this node.")
    image, _width, _height = _capture_screen(values)
    if provider == "omniparser":
        result = _describe_with_omniparser(endpoint, image, str(values["mode"]))
    elif provider == "llama_cpp_mtmd":
        result = _describe_with_mtmd(endpoint, image, str(values["mode"]))
    else:
        raise RuntimeError("Unsupported visual-description specialist.")
    result["source_sha256"] = hashlib.sha256(image).hexdigest()
    return result
