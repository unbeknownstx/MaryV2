from __future__ import annotations

import base64
from pathlib import Path
from urllib.request import urlopen

from mary.desktop.audio_cache import DesktopAudioCache
from mary.desktop.static_server import DesktopStaticServer


def test_loopback_server_serves_vite_assets_same_origin(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text('<script type="module" src="./assets/main.js"></script>', encoding="utf-8")
    (assets / "main.js").write_text('globalThis.__maryBoot = true;', encoding="utf-8")

    server = DesktopStaticServer(dist).start()
    try:
        assert server.base_url.startswith("http://127.0.0.1:")
        with urlopen(server.url_for("index.html"), timeout=2) as response:
            assert response.status == 200
            assert b"type=\"module\"" in response.read()
        with urlopen(server.url_for("assets/main.js"), timeout=2) as response:
            assert response.status == 200
            assert b"__maryBoot" in response.read()
            assert response.headers["Cache-Control"] == "no-store"
    finally:
        server.stop()


def test_desktop_audio_cache_can_use_same_loopback_origin(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("Mary", encoding="utf-8")
    cache = DesktopAudioCache(tmp_path / "voice")
    server = DesktopStaticServer(dist, voice_root=cache.root).start()
    cache.set_public_url_builder(server.voice_url)
    try:
        payload = cache.stage({
            "enabled": True,
            "status": "success",
            "format": "mp3",
            "mime_type": "audio/mpeg",
            "audio_base64": base64.b64encode(b"ID3mary").decode("ascii"),
        })
        assert payload["audio_transport"] == "loopback_url"
        assert payload["audio_url"].startswith(server.base_url + "/__mary_voice__/")
        with urlopen(payload["audio_url"], timeout=2) as response:
            assert response.status == 200
            assert response.read() == b"ID3mary"
    finally:
        server.stop()
        cache.cleanup()


def test_desktop_window_uses_loopback_origin_not_file_origin() -> None:
    source = Path("mary/desktop/window.py").read_text(encoding="utf-8")
    assert "DesktopStaticServer" in source
    assert "self._static_server.url_for(frontend_path.name)" in source
    assert "self.web.setUrl(QUrl(self._static_server.url_for(frontend_path.name)))" in source


def test_launcher_uses_same_loopback_origin() -> None:
    source = Path("mary/launcher/window.py").read_text(encoding="utf-8")
    assert "DesktopStaticServer" in source
    assert "self.web.setUrl(QUrl(self._static_server.url_for(frontend_path.name)))" in source
