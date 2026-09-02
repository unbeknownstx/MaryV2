"""Optional OBS WebSocket -> Mary Core presence adapter."""
from __future__ import annotations

import asyncio
import json
import os

from mary.integrations.obs_client import identify_message, normalize_obs_event, parse_hello
from mary.protocol.client import MaryClient


async def main_async() -> int:
    try:
        import websockets
    except ImportError as exc:
        raise SystemExit("Install requirements-streaming.txt first") from exc
    host = os.getenv("MARY_OBS_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("MARY_OBS_PORT", "4455") or 4455)
    password = os.getenv("MARY_OBS_PASSWORD", "")
    core_url = os.getenv("MARY_CORE_URL", "").strip()
    core_token = os.getenv("MARY_CORE_TOKEN", "").strip()
    if not core_url or not core_token:
        raise SystemExit("MARY_CORE_URL and MARY_CORE_TOKEN are required")
    client = MaryClient(core_url, token=core_token, device_id="obs-presence-node", surface="stream_adapter", timeout=20)
    uri = f"ws://{host}:{port}"
    async with websockets.connect(uri, subprotocols=["obswebsocket.json"], max_size=2_000_000) as socket:
        hello = parse_hello(json.loads(await asyncio.wait_for(socket.recv(), timeout=10)))
        await socket.send(json.dumps(identify_message(hello, password=password, event_subscriptions=(1 << 0) | (1 << 2) | (1 << 6))))
        identified = json.loads(await asyncio.wait_for(socket.recv(), timeout=10))
        if int(identified.get("op", -1)) != 2:
            raise RuntimeError("OBS did not identify Mary adapter")
        print("OBS presence adapter connected", flush=True)
        async for raw in socket:
            observation = normalize_obs_event(json.loads(raw))
            if not observation:
                continue
            await asyncio.to_thread(
                client.runtime_action,
                "perception.observe",
                {
                    "modality": "application_event",
                    "description": observation["summary"],
                    "source": observation["source"],
                    "confidence": .98,
                    "importance": .55,
                    "metadata": observation["metadata"],
                },
            )
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
