"""Run an explicit Twitch EventSub -> canonical Mary Core chat adapter.

Requires ``requirements-streaming.txt`` and Twitch OAuth scopes documented in
``docs/STREAMING_ADAPTERS.md``. The adapter never owns Mary or writes memory; it
only forwards normalized chat events through typed Core runtime actions.
"""
from __future__ import annotations

import asyncio
import json
import os
from urllib.request import Request, urlopen

from mary.integrations.twitch_eventsub import EVENTSUB_URL, TwitchEventSubConfig, normalize_chat_notification, session_from_welcome
from mary.protocol.client import MaryClient


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _config() -> TwitchEventSubConfig:
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
            "User-Agent": "MaryV2-Twitch-Adapter/1",
        },
    )
    with urlopen(request, timeout=20) as response:  # nosec B310 - fixed Twitch API endpoint
        if int(response.status) not in {200, 202}:
            raise RuntimeError(f"Twitch subscription failed: HTTP {response.status}")


async def main_async() -> int:
    try:
        import websockets
    except ImportError as exc:
        raise SystemExit("Install requirements-streaming.txt first") from exc

    cfg = _config()
    core_url = _env("MARY_CORE_URL")
    core_token = _env("MARY_CORE_TOKEN")
    if not core_url or not core_token:
        raise SystemExit("MARY_CORE_URL and MARY_CORE_TOKEN are required")
    client = MaryClient(core_url, token=core_token, device_id="twitch-chat-node", surface="stream_adapter", timeout=20)

    reconnect_url = EVENTSUB_URL
    while True:
        async with websockets.connect(reconnect_url, max_size=2_000_000, ping_interval=None) as socket:
            first = json.loads(await asyncio.wait_for(socket.recv(), timeout=20))
            session = session_from_welcome(first)
            if not session:
                raise RuntimeError("Twitch did not send EventSub welcome")
            if reconnect_url == EVENTSUB_URL:
                await asyncio.to_thread(_subscribe, cfg, str(session.get("id") or ""))
            print(f"Twitch EventSub connected: {session.get('id','')[:10]}…", flush=True)
            async for raw in socket:
                payload = json.loads(raw)
                message_type = str((payload.get("metadata") or {}).get("message_type") or "")
                if message_type == "session_reconnect":
                    reconnect_url = str(((payload.get("payload") or {}).get("session") or {}).get("reconnect_url") or EVENTSUB_URL)
                    break
                message = normalize_chat_notification(payload)
                if message is None:
                    continue
                result = await asyncio.to_thread(
                    client.runtime_action,
                    "stream.chat.ingest",
                    message.to_dict(),
                )
                selection = dict(result or {}).get("selection") or {}
                print(f"chat {message.display_name}: {selection.get('action','ignore')} {selection.get('score','')}", flush=True)
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
