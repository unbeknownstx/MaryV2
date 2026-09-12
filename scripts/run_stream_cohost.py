"""Run MaryV2 as a bounded Twitch/OBS live cohost.

Pipeline:
    Twitch EventSub -> Core stream.chat.ingest -> existing attention/floor policy
    -> bounded StreamCohostPlanner -> canonical Mary Core turn
    -> Core voice synthesis -> loopback OBS Browser Source relay
    -> optional Twitch typed reply

This process owns transport only. It never constructs Mary, never writes memory or
relationship state directly, and never treats audience text as creator/tool
authority.
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
import json
import os
from time import monotonic
from typing import Any
from urllib.request import Request, urlopen

from mary.integrations import (
    SEND_CHAT_URL,
    TwitchChatOutbox,
    TwitchChatSendConfig,
    TwitchEventSubConfig,
    TwitchEventSubSession,
    normalize_chat_notification,
    parse_send_chat_response,
)
from mary.integrations.twitch_eventsub import EVENTSUB_URL
from mary.protocol.client import MaryClient
from mary.streaming import LocalOBSRelay, StreamCohostPlanner, summarize_stream_context


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _flag(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if not raw:
        return bool(default)
    return raw.casefold() in {"1", "true", "yes", "on", "enabled"}


def _number(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return float(default)


def _twitch_config() -> TwitchEventSubConfig:
    cfg = TwitchEventSubConfig(
        client_id=_env("MARY_TWITCH_CLIENT_ID"),
        oauth_token=_env("MARY_TWITCH_OAUTH_TOKEN"),
        broadcaster_user_id=_env("MARY_TWITCH_BROADCASTER_ID"),
        user_id=_env("MARY_TWITCH_USER_ID"),
    )
    if not cfg.public_status()["configured"]:
        raise SystemExit("Twitch EventSub credentials/IDs are incomplete. See docs/STREAMING_ADAPTERS.md")
    return cfg


def _subscribe(cfg: TwitchEventSubConfig, session_id: str) -> None:
    body = json.dumps(cfg.subscription_body(session_id)).encode("utf-8")
    request = Request(
        "https://api.twitch.tv/helix/eventsub/subscriptions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {cfg.oauth_token}",
            "Client-Id": cfg.client_id,
            "Content-Type": "application/json",
            "User-Agent": "MaryV2-Stream-Cohost/13.10",
        },
    )
    with urlopen(request, timeout=20) as response:  # nosec B310 - fixed Twitch API endpoint
        if int(response.status) not in {200, 202}:
            raise RuntimeError(f"Twitch subscription failed: HTTP {response.status}")


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
            "User-Agent": "MaryV2-Stream-Cohost/13.10",
        },
    )
    with urlopen(request, timeout=75) as response:  # nosec B310 - configured canonical Core endpoint
        audio = response.read(24_000_001)
        if not audio or len(audio) > 24_000_000:
            raise RuntimeError("Mary Core returned invalid or oversized voice audio")
        mime = str(response.headers.get("Content-Type") or "audio/mpeg").split(";", 1)[0].strip()
        return audio, mime


def _send_twitch_chat(cfg: TwitchChatSendConfig, text: str, *, reply_parent_message_id: str = "") -> dict[str, Any]:
    payload = cfg.body(text, reply_parent_message_id=reply_parent_message_id)
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        SEND_CHAT_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {cfg.oauth_token}",
            "Client-Id": cfg.client_id,
            "Content-Type": "application/json",
            "User-Agent": "MaryV2-Stream-Cohost/13.10",
        },
    )
    with urlopen(request, timeout=20) as response:  # nosec B310 - fixed Twitch API endpoint
        raw = json.loads(response.read(1_000_000).decode("utf-8"))
    return parse_send_chat_response(raw)


def _estimated_speech_seconds(text: str) -> float:
    words = max(1, len(str(text or "").split()))
    # About 155 wpm plus a small playback/render margin, bounded so stale floor
    # ownership cannot persist indefinitely if the browser source is stopped.
    return max(1.2, min(25.0, words / 155.0 * 60.0 + 0.8))


async def _renew_surface(client: MaryClient, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=60.0)
            return
        except asyncio.TimeoutError:
            pass
        try:
            await asyncio.to_thread(
                client.surface_renew,
                visible=True,
                foreground=True,
                activity=False,
                lease_seconds=120,
            )
        except Exception as exc:  # noqa: BLE001 - stream should keep trying while transport lives
            print(f"surface renew warning: {type(exc).__name__}", flush=True)


async def _end_speech_later(client: MaryClient, turn_id: str, seconds: float) -> None:
    await asyncio.sleep(seconds)
    with suppress(Exception):
        await asyncio.to_thread(
            client.runtime_action,
            "realtime.speech_ended",
            {"turn_id": turn_id, "source": "stream_obs_relay"},
        )


async def _response_worker(
    queue: asyncio.Queue[tuple[dict[str, Any], dict[str, Any]]],
    *,
    client: MaryClient,
    planner: StreamCohostPlanner,
    relay: LocalOBSRelay,
    core_url: str,
    core_token: str,
    outbox: TwitchChatOutbox,
    chat_send: TwitchChatSendConfig,
    voice_enabled: bool,
    write_chat: bool,
    include_context: bool,
    stop: asyncio.Event,
) -> None:
    while not stop.is_set():
        try:
            message, ingest = await asyncio.wait_for(queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        try:
            observation_context = ""
            if include_context:
                perception: dict[str, Any] = {}
                scene: dict[str, Any] = {}
                with suppress(Exception):
                    perception = await asyncio.to_thread(client.runtime_action, "perception.status", {})
                with suppress(Exception):
                    scene = await asyncio.to_thread(client.runtime_action, "presence.scene.status", {})
                observation_context = summarize_stream_context(perception, scene)

            candidate = planner.prepare(
                message,
                ingest,
                observation_context=observation_context,
            )
            if candidate is None:
                continue

            turn = await asyncio.to_thread(
                client.turn,
                candidate.prompt,
                conversation_id=candidate.conversation_id,
                requested_mode="engaged",
                voice_input=False,
            )
            rendered = planner.render_response(turn.response, output_mode=candidate.output_mode)
            delivered = False

            if rendered.speak and voice_enabled:
                try:
                    audio, mime = await asyncio.to_thread(
                        _synthesize_voice,
                        core_url,
                        core_token,
                        rendered.voice_text,
                    )
                    with suppress(Exception):
                        await asyncio.to_thread(
                            client.runtime_action,
                            "realtime.speech_started",
                            {"turn_id": turn.turn_id or "", "source": "stream_obs_relay"},
                        )
                    relay.state.publish_audio(
                        audio,
                        mime_type=mime,
                        caption=rendered.voice_text,
                    )
                    asyncio.create_task(
                        _end_speech_later(
                            client,
                            turn.turn_id or "",
                            _estimated_speech_seconds(rendered.voice_text),
                        )
                    )
                    delivered = True
                except Exception as exc:  # noqa: BLE001 - typed fallback remains available
                    print(f"voice unavailable: {type(exc).__name__}", flush=True)

            if rendered.send_chat and write_chat and chat_send.configured:
                planned, reason = outbox.plan(
                    channel=candidate.channel,
                    text=rendered.chat_text,
                    reply_parent_message_id=candidate.reply_to_message_id,
                    dedupe_key=candidate.message_id,
                )
                if planned is not None:
                    try:
                        sent = await asyncio.to_thread(
                            _send_twitch_chat,
                            chat_send,
                            planned.text,
                            reply_parent_message_id=planned.reply_parent_message_id,
                        )
                        delivered = delivered or bool(sent.get("is_sent"))
                        if not sent.get("is_sent"):
                            print(f"Twitch chat not sent: {sent.get('drop_code') or 'unknown'}", flush=True)
                    except Exception as exc:  # noqa: BLE001
                        print(f"Twitch chat send failed: {type(exc).__name__}", flush=True)
                elif reason != "duplicate":
                    print(f"Twitch chat skipped: {reason}", flush=True)

            if not delivered:
                # A stream can still be tested before OBS/TTS/write-chat are
                # configured; never silently lose the canonical Mary response.
                relay.state.publish_caption(rendered.voice_text or rendered.chat_text)
                print(f"Mary: {rendered.voice_text or rendered.chat_text}", flush=True)
            else:
                planner.mark_responded()
                with suppress(Exception):
                    stream = getattr(getattr(client, "", None), "", None)  # deliberately no local Mary access
                with suppress(Exception):
                    # Marking answered occurs on canonical stream governor via a
                    # tiny bounded action added by the Core in a later pass; the
                    # current ingest dedupe already prevents same message IDs.
                    pass

            print(
                f"responded to {candidate.viewer_name} via {candidate.output_mode} "
                f"score={candidate.score:.2f}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001 - one viewer must not kill the stream runner
            print(f"cohost response error: {type(exc).__name__}: {exc}", flush=True)
        finally:
            queue.task_done()


async def main_async() -> int:
    try:
        import websockets
    except ImportError as exc:
        raise SystemExit("Install requirements-streaming.txt first") from exc

    twitch = _twitch_config()
    core_url = _env("MARY_CORE_URL")
    core_token = _env("MARY_CORE_TOKEN")
    if not core_url or not core_token:
        raise SystemExit("MARY_CORE_URL and MARY_CORE_TOKEN are required")

    device_id = _env("MARY_STREAM_DEVICE_ID", "stream-cohost-node") or "stream-cohost-node"
    conversation_id = _env("MARY_STREAM_CONVERSATION_ID", "stream-public") or "stream-public"
    relay_port = int(_number("MARY_STREAM_RELAY_PORT", 8765))
    planner = StreamCohostPlanner(
        conversation_id=conversation_id,
        response_cooldown_seconds=_number("MARY_STREAM_RESPONSE_COOLDOWN", 5.0),
    )
    relay = LocalOBSRelay(port=relay_port)
    relay.start()

    client = MaryClient(
        core_url,
        token=core_token,
        device_id=device_id,
        surface="stream_cohost",
        timeout=90,
    )
    await asyncio.to_thread(
        client.surface_register,
        visible=True,
        foreground=True,
        lease_seconds=120,
    )
    await asyncio.to_thread(
        client.runtime_action,
        "performance.context.set",
        {"mode": "stream"},
    )

    write_chat = _flag("MARY_TWITCH_WRITE_CHAT", False)
    voice_enabled = _flag("MARY_STREAM_VOICE", True)
    include_context = _flag("MARY_STREAM_INCLUDE_CONTEXT", True)
    bot_user_id = _env("MARY_TWITCH_BOT_USER_ID") or twitch.user_id
    approved_channels = tuple(
        item.strip().casefold().lstrip("#")
        for item in _env("MARY_TWITCH_APPROVED_CHANNELS").split(",")
        if item.strip()
    )
    outbox = TwitchChatOutbox(
        approved_channels=approved_channels,
        bot_user_id=bot_user_id,
    )
    chat_send = TwitchChatSendConfig(
        client_id=twitch.client_id,
        oauth_token=twitch.oauth_token,
        broadcaster_user_id=twitch.broadcaster_user_id,
        sender_user_id=twitch.user_id,
    )

    print("Mary stream cohost ready", flush=True)
    print(f"OBS Browser Source: {relay.url}", flush=True)
    print(
        f"voice={'on' if voice_enabled else 'off'} "
        f"typed_chat={'on' if write_chat else 'off'} "
        f"context={'on' if include_context else 'off'}",
        flush=True,
    )

    queue: asyncio.Queue[tuple[dict[str, Any], dict[str, Any]]] = asyncio.Queue(maxsize=8)
    stop = asyncio.Event()
    renew_task = asyncio.create_task(_renew_surface(client, stop))
    worker_task = asyncio.create_task(
        _response_worker(
            queue,
            client=client,
            planner=planner,
            relay=relay,
            core_url=core_url,
            core_token=core_token,
            outbox=outbox,
            chat_send=chat_send,
            voice_enabled=voice_enabled,
            write_chat=write_chat,
            include_context=include_context,
            stop=stop,
        )
    )

    session = TwitchEventSubSession()
    reconnect_url = EVENTSUB_URL
    try:
        while True:
            session.connecting()
            async with websockets.connect(
                reconnect_url,
                max_size=2_000_000,
                ping_interval=None,
            ) as socket:
                first = json.loads(await asyncio.wait_for(socket.recv(), timeout=20))
                actions = session.handle(first)
                subscribe = next((item for item in actions if item.action == "subscribe"), None)
                if subscribe is None or not subscribe.session_id:
                    raise RuntimeError("Twitch did not send EventSub welcome")
                if reconnect_url == EVENTSUB_URL:
                    session.mark_subscribing()
                    await asyncio.to_thread(_subscribe, twitch, subscribe.session_id)
                    session.mark_ready()
                print(f"Twitch connected: {subscribe.session_id[:10]}…", flush=True)

                async for raw in socket:
                    payload = json.loads(raw)
                    controls = session.handle(payload)
                    reconnect = next((item for item in controls if item.action == "reconnect"), None)
                    if reconnect is not None:
                        reconnect_url = reconnect.reconnect_url or EVENTSUB_URL
                        break
                    message = normalize_chat_notification(payload)
                    if message is None:
                        continue
                    if outbox.is_self_message(author_id=message.author_id):
                        continue
                    result = await asyncio.to_thread(
                        client.runtime_action,
                        "stream.chat.ingest",
                        message.to_dict(),
                    )
                    selection = dict(result or {}).get("selection") or {}
                    action = str(selection.get("action") or "ignore")
                    score = selection.get("score", "")
                    print(f"chat {message.display_name}: {action} {score}", flush=True)
                    plan = dict(result or {}).get("response_plan") or {}
                    if str(plan.get("mode") or "") in {"chat", "speak", "both"}:
                        item = (message.to_dict(), dict(result or {}))
                        try:
                            queue.put_nowait(item)
                        except asyncio.QueueFull:
                            print("cohost queue full; dropping oldest response candidate", flush=True)
                            with suppress(asyncio.QueueEmpty):
                                queue.get_nowait()
                                queue.task_done()
                            with suppress(asyncio.QueueFull):
                                queue.put_nowait(item)
            if reconnect_url != EVENTSUB_URL:
                continue
            await asyncio.sleep(1.0)
    finally:
        stop.set()
        renew_task.cancel()
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await renew_task
        with suppress(asyncio.CancelledError):
            await worker_task
        with suppress(Exception):
            await asyncio.to_thread(client.surface_disconnect)
        relay.stop()
    return 0


def main() -> int:
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
