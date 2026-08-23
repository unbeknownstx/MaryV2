"""Optional loopback WebSocket transport for MaryV2 presence/state.

The server is disabled by default, binds to 127.0.0.1 by default, and exposes a
small read-only protocol suitable for a future phone/browser client.  It does
not accept creator instructions or mutate Mary state.
"""
from __future__ import annotations

import asyncio
import json
import os
from queue import Empty, Queue
from threading import Event, Thread
from typing import Any, Callable


class LocalPresenceWebSocket:
    def __init__(self, snapshot_factory: Callable[[], dict[str, Any]]) -> None:
        self.snapshot_factory = snapshot_factory
        self.enabled = os.getenv("MARY_WEBSOCKET_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.host = os.getenv("MARY_WEBSOCKET_HOST", "127.0.0.1").strip() or "127.0.0.1"
        try:
            self.port = max(1024, min(65535, int(os.getenv("MARY_WEBSOCKET_PORT", "8765"))))
        except ValueError:
            self.port = 8765
        self.token = os.getenv("MARY_WEBSOCKET_TOKEN", "").strip()
        self._queue: Queue[dict[str, Any]] = Queue(maxsize=128)
        self._stop = Event()
        self._thread: Thread | None = None
        self._started = False
        self._error = ""

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = Thread(target=self._run, name="MaryPresenceWebSocket", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None
        self._started = False

    def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        if not self.enabled:
            return
        item = {"type": str(event_type), "payload": dict(payload or {})}
        try:
            self._queue.put_nowait(item)
        except Exception:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(item)
            except Exception:
                pass

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "started": self._started,
            "host": self.host,
            "port": self.port,
            "auth": "token" if self.token else "loopback_only",
            "mode": "read_only_presence",
            "error": self._error or None,
        }

    def _run(self) -> None:
        try:
            asyncio.run(self._serve())
        except Exception as exc:  # optional transport must never kill Mary
            self._error = f"{type(exc).__name__}: {exc}"
            self._started = False

    async def _serve(self) -> None:
        try:
            import websockets
        except Exception as exc:
            self._error = f"websockets dependency unavailable: {exc}"
            return

        clients: set[Any] = set()

        async def handler(ws):
            if self.token:
                supplied = str(ws.request.headers.get("Authorization", ""))
                if supplied != f"Bearer {self.token}":
                    await ws.close(code=4401, reason="Unauthorized")
                    return
            clients.add(ws)
            try:
                await ws.send(json.dumps({"type": "hello", "payload": self._safe_snapshot()}))
                async for raw in ws:
                    try:
                        message = json.loads(raw)
                    except Exception:
                        continue
                    kind = str(message.get("type") if isinstance(message, dict) else "")
                    if kind == "ping":
                        await ws.send(json.dumps({"type": "pong", "payload": {}}))
                    elif kind == "snapshot":
                        await ws.send(json.dumps({"type": "snapshot", "payload": self._safe_snapshot()}))
            finally:
                clients.discard(ws)

        async def broadcaster():
            while not self._stop.is_set():
                item = None
                try:
                    item = await asyncio.to_thread(self._queue.get, True, 0.25)
                except Empty:
                    pass
                if item and clients:
                    encoded = json.dumps(item, ensure_ascii=False, default=str)
                    dead = []
                    for ws in list(clients):
                        try:
                            await ws.send(encoded)
                        except Exception:
                            dead.append(ws)
                    for ws in dead:
                        clients.discard(ws)

        async with websockets.serve(handler, self.host, self.port, max_size=256_000):
            self._started = True
            task = asyncio.create_task(broadcaster())
            try:
                while not self._stop.is_set():
                    await asyncio.sleep(0.2)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                self._started = False

    def _safe_snapshot(self) -> dict[str, Any]:
        try:
            snapshot = dict(self.snapshot_factory() or {})
        except Exception as exc:
            return {"error": f"snapshot unavailable: {type(exc).__name__}"}
        # Keep the transport deliberately small and display-safe.
        return {
            "companion": snapshot.get("companion", {}),
            "focus": snapshot.get("focus", {}),
            "last_turn": snapshot.get("last_turn", {}),
            "presence": {
                "mode": (snapshot.get("presence") or {}).get("mode"),
                "pending_thoughts": (snapshot.get("presence") or {}).get("pending_thoughts", [])[:5],
            },
        }
