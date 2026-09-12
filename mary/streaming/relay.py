"""Loopback-only OBS browser-source relay for Mary stream audio/captions.

The relay is presentation transport only. It stores at most one bounded audio
payload in process memory and exposes it on localhost for an OBS Browser Source.
It does not expose Core credentials, model prompts, relationship state, or tools.
"""
from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import RLock, Thread
from time import time
from typing import Any
from urllib.parse import parse_qs, urlsplit


_MAX_AUDIO_BYTES = 24_000_000


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[: max(0, int(limit))]


@dataclass(frozen=True)
class RelaySnapshot:
    sequence: int
    caption: str
    mime_type: str
    audio_bytes: int
    published_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "caption": self.caption,
            "mime_type": self.mime_type,
            "audio_bytes": self.audio_bytes,
            "published_at": self.published_at,
        }


class StreamRelayState:
    """Thread-safe single-packet relay state."""

    VERSION = "13.10"

    def __init__(self) -> None:
        self._lock = RLock()
        self._sequence = 0
        self._audio = b""
        self._mime_type = "audio/mpeg"
        self._caption = ""
        self._published_at = 0.0

    def publish_audio(self, audio: bytes, *, mime_type: str, caption: str = "") -> RelaySnapshot:
        payload = bytes(audio or b"")
        if not payload:
            raise ValueError("stream relay audio cannot be empty")
        if len(payload) > _MAX_AUDIO_BYTES:
            raise ValueError("stream relay audio exceeds the bounded packet limit")
        mime = _clean(mime_type, 80).casefold() or "audio/mpeg"
        if not mime.startswith("audio/"):
            raise ValueError("stream relay accepts audio MIME types only")
        with self._lock:
            self._sequence += 1
            self._audio = payload
            self._mime_type = mime
            self._caption = _clean(caption, 1000)
            self._published_at = time()
            return self._snapshot_locked()

    def publish_caption(self, caption: str) -> RelaySnapshot:
        with self._lock:
            self._caption = _clean(caption, 1000)
            self._published_at = time()
            return self._snapshot_locked()

    def snapshot(self) -> RelaySnapshot:
        with self._lock:
            return self._snapshot_locked()

    def audio(self, sequence: int) -> tuple[bytes, str] | None:
        with self._lock:
            if int(sequence) != self._sequence or not self._audio:
                return None
            return bytes(self._audio), self._mime_type

    def _snapshot_locked(self) -> RelaySnapshot:
        return RelaySnapshot(
            sequence=self._sequence,
            caption=self._caption,
            mime_type=self._mime_type,
            audio_bytes=len(self._audio),
            published_at=self._published_at,
        )


_PLAYER_HTML = """<!doctype html>
<html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\">
<style>
html,body{margin:0;width:100%;height:100%;background:transparent;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif}
#caption{position:absolute;left:4%;right:4%;bottom:5%;padding:10px 14px;border-radius:14px;background:rgba(6,7,17,.72);border:1px solid rgba(255,79,166,.28);color:#fff;font-size:26px;font-weight:650;line-height:1.25;text-align:center;text-shadow:0 2px 10px #000;opacity:0;transition:opacity .18s ease}
#caption.show{opacity:1}
</style></head>
<body><audio id=\"mary-audio\" autoplay></audio><div id=\"caption\"></div>
<script>
const audio=document.getElementById('mary-audio'); const caption=document.getElementById('caption');
let last=0; let hideTimer=null;
async function poll(){
 try{
  const r=await fetch('/state?ts='+Date.now(),{cache:'no-store'}); if(!r.ok)return;
  const s=await r.json();
  if(s.sequence>last){
    last=s.sequence;
    caption.textContent=s.caption||''; caption.classList.toggle('show',!!s.caption);
    clearTimeout(hideTimer); hideTimer=setTimeout(()=>caption.classList.remove('show'),12000);
    audio.src='/audio?seq='+encodeURIComponent(last)+'&ts='+Date.now();
    try{await audio.play();}catch(e){}
  }
 }catch(e){}
}
setInterval(poll,250); poll();
</script></body></html>"""


def _handler_for(state: StreamRelayState):
    class RelayHandler(BaseHTTPRequestHandler):
        server_version = "MaryStreamRelay/13.10"

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
            parsed = urlsplit(self.path)
            if parsed.path == "/":
                body = _PLAYER_HTML.encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8")
                return
            if parsed.path == "/health":
                body = json.dumps({"ok": True, "version": state.VERSION}).encode("utf-8")
                self._send(200, body, "application/json")
                return
            if parsed.path == "/state":
                body = json.dumps(state.snapshot().to_dict(), ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json", cache=False)
                return
            if parsed.path == "/audio":
                raw = parse_qs(parsed.query).get("seq", ["0"])[0]
                try:
                    sequence = int(raw)
                except (TypeError, ValueError):
                    sequence = 0
                packet = state.audio(sequence)
                if packet is None:
                    self._send(404, b"", "text/plain")
                    return
                audio, mime_type = packet
                self._send(200, audio, mime_type, cache=False)
                return
            self._send(404, b"not found", "text/plain")

        def log_message(self, _format: str, *args: Any) -> None:
            return

        def _send(self, status: int, body: bytes, content_type: str, *, cache: bool = True) -> None:
            self.send_response(int(status))
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if not cache:
                self.send_header("Cache-Control", "no-store, max-age=0")
            self.end_headers()
            if body:
                self.wfile.write(body)

    return RelayHandler


class LocalOBSRelay:
    """Own one loopback HTTP server suitable for an OBS Browser Source."""

    def __init__(self, *, host: str = "127.0.0.1", port: int = 8765, state: StreamRelayState | None = None) -> None:
        normalized_host = str(host or "127.0.0.1").strip()
        if normalized_host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Mary stream relay is loopback-only")
        self.host = normalized_host
        self.port = max(1024, min(65535, int(port)))
        self.state = state or StreamRelayState()
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    @property
    def url(self) -> str:
        host = "127.0.0.1" if self.host == "localhost" else self.host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"http://{host}:{self.port}/"

    def start(self) -> None:
        if self._server is not None:
            return
        server = ThreadingHTTPServer((self.host, self.port), _handler_for(self.state))
        server.daemon_threads = True
        thread = Thread(target=server.serve_forever, name="mary-stream-relay", daemon=True)
        thread.start()
        self._server = server
        self._thread = thread

    def stop(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.shutdown()
            server.server_close()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)

    def status(self) -> dict[str, Any]:
        return {
            "version": "13.10",
            "running": self._server is not None,
            "url": self.url,
            "relay": self.state.snapshot().to_dict(),
            "authority": "loopback presentation transport only",
        }
