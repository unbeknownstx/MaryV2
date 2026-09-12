"""Run Mary's public-safe creator microphone bridge beside the Twitch cohost.

This optional process captures bounded local utterances, dispatches them through
the normal capability broker to an authorized `sensor.audio_transcribe` node,
submits the transcript to the same canonical public stream conversation, and
publishes Mary's Core TTS to a second loopback OBS Browser Source.

It never creates a second Mary and never uses the private Desktop conversation.
"""
from __future__ import annotations

import asyncio
import base64
from contextlib import suppress
import json
import os
from time import monotonic
from typing import Any
from urllib.request import Request, urlopen

from mary.protocol.client import MaryClient
from mary.streaming.creator_audio import StreamCreatorMicrophone
from mary.streaming.relay import LocalOBSRelay


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _flag(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.casefold() in {"1", "true", "yes", "on", "enabled"}


def _number(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _synthesize_voice(core_url: str, core_token: str, text: str) -> tuple[bytes, str]:
    payload = json.dumps({"text": text, "delivery_plan": {"context": "stream"}}).encode("utf-8")
    request = Request(
        core_url.rstrip("/") + "/v1/voice/synthesize",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {core_token}",
            "Content-Type": "application/json",
            "Accept": "audio/*,application/octet-stream",
            "User-Agent": "MaryV2-Stream-Creator-Voice/13.13",
        },
    )
    with urlopen(request, timeout=75) as response:  # nosec B310 - configured canonical Core endpoint
        audio = response.read(24_000_001)
        if not audio or len(audio) > 24_000_000:
            raise RuntimeError("Mary Core returned invalid or oversized voice audio")
        mime = str(response.headers.get("Content-Type") or "audio/mpeg").split(";", 1)[0].strip()
        return audio, mime


async def _wait_task(client: MaryClient, task_id: str, *, timeout: float = 45.0) -> dict[str, Any]:
    deadline = monotonic() + max(2.0, min(90.0, timeout))
    while monotonic() < deadline:
        status = await asyncio.to_thread(client.capability_task_status, task_id)
        task = dict(status.get("task") or status)
        state = str(task.get("status") or "").strip().lower()
        if state in {"completed", "rejected", "failed", "expired"}:
            return task
        await asyncio.sleep(0.15)
    raise TimeoutError("STT capability task did not complete before timeout")


async def _transcribe(client: MaryClient, wav_bytes: bytes) -> str:
    dispatched = await asyncio.to_thread(
        client.dispatch_capability_task,
        "sensor.audio_transcribe",
        "Transcribe one bounded creator utterance for the public stream conversation.",
        {
            "audio_base64": base64.b64encode(wav_bytes).decode("ascii"),
            "suffix": ".wav",
            "language": _env("MARY_STREAM_LANGUAGE", "en") or "en",
        },
    )
    task = dict(dispatched.get("task") or dispatched)
    task_id = str(task.get("task_id") or "")
    if not task_id:
        raise RuntimeError("Core did not return a capability task id")
    terminal = await _wait_task(client, task_id, timeout=_number("MARY_STREAM_STT_TIMEOUT", 45.0))
    if str(terminal.get("status") or "") != "completed":
        raise RuntimeError(str(terminal.get("error") or f"STT task {terminal.get('status') or 'failed'}"))
    result = dict(terminal.get("result") or {})
    return " ".join(str(result.get("text") or "").split())[:12_000]


async def main_async() -> int:
    if not _flag("MARY_STREAM_CREATOR_HEARING", False):
        raise SystemExit("Set MARY_STREAM_CREATOR_HEARING=1 to explicitly arm stream microphone capture")

    core_url = _env("MARY_CORE_URL")
    core_token = _env("MARY_CORE_TOKEN")
    if not core_url or not core_token:
        raise SystemExit("MARY_CORE_URL and MARY_CORE_TOKEN are required")

    conversation_id = _env("MARY_STREAM_CONVERSATION_ID", "stream-public") or "stream-public"
    device_id = _env("MARY_STREAM_VOICE_DEVICE_ID", "stream-creator-voice") or "stream-creator-voice"
    relay_port = int(_number("MARY_STREAM_VOICE_RELAY_PORT", 8766))
    relay = LocalOBSRelay(port=relay_port)
    relay.start()

    client = MaryClient(core_url, token=core_token, device_id=device_id, surface="stream_creator_voice", timeout=90)
    await asyncio.to_thread(client.surface_register, visible=True, foreground=True, lease_seconds=120)
    await asyncio.to_thread(client.runtime_action, "performance.context.set", {"mode": "stream"})

    queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=3)
    loop = asyncio.get_running_loop()

    def _heard(wav_bytes: bytes) -> None:
        def _enqueue() -> None:
            if queue.full():
                with suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
                    queue.task_done()
            with suppress(asyncio.QueueFull):
                queue.put_nowait(wav_bytes)
        loop.call_soon_threadsafe(_enqueue)

    def _voice_activity(active: bool, confirmed: bool, confidence: float) -> None:
        async def _publish() -> None:
            with suppress(Exception):
                await asyncio.to_thread(
                    client.runtime_action,
                    "realtime.voice_activity",
                    {
                        "active": active,
                        "confirmed": confirmed,
                        "confidence": confidence,
                        "source": "stream_creator_vad",
                    },
                )
        loop.call_soon_threadsafe(lambda: asyncio.create_task(_publish()))

    microphone = StreamCreatorMicrophone(_heard, _voice_activity)
    microphone.start()
    print("Mary stream creator hearing armed", flush=True)
    print(f"OBS creator-voice Browser Source: {relay.url}", flush=True)
    print("Raw microphone PCM remains local until one bounded utterance is dispatched for STT.", flush=True)

    try:
        while True:
            wav_bytes = await queue.get()
            try:
                with suppress(Exception):
                    await asyncio.to_thread(client.runtime_action, "realtime.transcribing", {"active": True, "source": "stream_creator_voice"})
                transcript = await _transcribe(client, wav_bytes)
                with suppress(Exception):
                    await asyncio.to_thread(client.runtime_action, "realtime.transcribing", {"active": False, "source": "stream_creator_voice"})
                if not transcript:
                    continue
                print(f"You: {transcript}", flush=True)
                turn = await asyncio.to_thread(
                    client.turn,
                    transcript,
                    conversation_id=conversation_id,
                    requested_mode="engaged",
                    voice_input=True,
                )
                text = " ".join(str(turn.response or "").split())
                if not text:
                    continue
                try:
                    audio, mime = await asyncio.to_thread(_synthesize_voice, core_url, core_token, text)
                    with suppress(Exception):
                        await asyncio.to_thread(client.runtime_action, "realtime.speech_started", {"turn_id": turn.turn_id or "", "source": "stream_creator_voice"})
                    relay.state.publish_audio(audio, mime_type=mime, caption=text)
                except Exception as exc:  # noqa: BLE001
                    relay.state.publish_caption(text)
                    print(f"voice unavailable: {type(exc).__name__}", flush=True)
                finally:
                    with suppress(Exception):
                        await asyncio.to_thread(client.runtime_action, "realtime.speech_ended", {"turn_id": turn.turn_id or "", "source": "stream_creator_voice"})
                print(f"Mary: {text}", flush=True)
            except Exception as exc:  # noqa: BLE001 - one utterance must not terminate stream hearing
                with suppress(Exception):
                    await asyncio.to_thread(client.runtime_action, "realtime.transcribing", {"active": False, "source": "stream_creator_voice"})
                print(f"creator voice error: {type(exc).__name__}: {exc}", flush=True)
            finally:
                queue.task_done()
    finally:
        microphone.stop()
        relay.stop()
        with suppress(Exception):
            await asyncio.to_thread(client.surface_disconnect)


def main() -> int:
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
