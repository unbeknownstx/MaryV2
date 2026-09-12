"""Loopback-only static server for Mary Desktop/Launcher WebEngine assets.

Qt WebEngine on macOS follows Chromium's stricter file-origin rules. A Vite
production build opened through ``file://`` can display its HTML while Chromium
blocks the ES-module chunks as cross-origin resources, leaving the splash screen
stuck before Mary's JavaScript boot sequence begins.

Serve the already-built ``desktop/dist`` directory from an ephemeral
``127.0.0.1`` HTTP port instead. This gives every Vite module/CSS/manifest asset
a normal same-origin URL without exposing Mary to the LAN or creating another
Mary runtime. The server is presentation-only and is stopped with the window.
"""
from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
from threading import Thread
from typing import Final
from urllib.parse import quote, unquote, urlencode, urlsplit


_VOICE_PREFIX: Final[str] = "/__mary_voice__/"


class _MaryStaticHandler(SimpleHTTPRequestHandler):
    """Serve desktop assets plus Mary's bounded temporary voice cache."""

    server_version = "MaryDesktopStatic/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def translate_path(self, path: str) -> str:
        parsed_path = unquote(urlsplit(path).path)
        if parsed_path.startswith(_VOICE_PREFIX):
            voice_root = getattr(self.server, "mary_voice_root", None)
            if voice_root is not None:
                name = Path(parsed_path[len(_VOICE_PREFIX):]).name
                candidate = (Path(voice_root) / name).resolve()
                root = Path(voice_root).resolve()
                try:
                    candidate.relative_to(root)
                except ValueError:
                    return str(root / "__blocked__")
                return str(candidate)
        return super().translate_path(path)


class DesktopStaticServer:
    """Ephemeral loopback server for one desktop/dist tree."""

    def __init__(self, root: str | Path, *, voice_root: str | Path | None = None) -> None:
        self.root = Path(root).expanduser().resolve()
        self.voice_root = Path(voice_root).expanduser().resolve() if voice_root is not None else None
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    @property
    def base_url(self) -> str:
        if self._httpd is None:
            raise RuntimeError("Desktop static server has not been started")
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "DesktopStaticServer":
        if self._httpd is not None:
            return self
        if not self.root.is_dir():
            raise FileNotFoundError(f"Desktop static root does not exist: {self.root}")

        handler = partial(_MaryStaticHandler, directory=str(self.root))
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        httpd.daemon_threads = True
        setattr(httpd, "mary_voice_root", self.voice_root)
        thread = Thread(target=httpd.serve_forever, name="MaryDesktopStaticServer", daemon=True)
        self._httpd = httpd
        self._thread = thread
        thread.start()
        return self

    def url_for(self, relative_path: str = "index.html") -> str:
        clean = str(relative_path or "index.html").replace("\\", "/").lstrip("/")
        url = f"{self.base_url}/{quote(clean, safe='/')}"
        # On macOS, presentation must not block the rest of Mary. The Vite
        # safe-renderer transform honors this query by skipping WebGL/Metal and
        # keeping the full companion UI alive on portrait art. Creator opt-in
        # to the live renderer remains explicit.
        if sys.platform == "darwin" and Path(clean).name == "index.html":
            requested = os.getenv("MARY_DESKTOP_MAC_RENDERER", "portrait").strip().lower()
            mode = "webgl" if requested == "webgl" else "portrait"
            url = f"{url}?{urlencode({'mary_renderer': mode})}"
        return url

    def voice_url(self, path: str | Path) -> str:
        candidate = Path(path).expanduser().resolve()
        if self.voice_root is None:
            raise RuntimeError("No voice root is configured")
        candidate.relative_to(self.voice_root)
        return f"{self.base_url}{_VOICE_PREFIX}{quote(candidate.name)}"

    def stop(self) -> None:
        httpd = self._httpd
        thread = self._thread
        self._httpd = None
        self._thread = None
        if httpd is None:
            return
        try:
            httpd.shutdown()
        finally:
            httpd.server_close()
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def __enter__(self) -> "DesktopStaticServer":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
