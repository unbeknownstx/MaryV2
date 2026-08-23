from __future__ import annotations

from mary.integrations.youtube import YouTubeSearch
from mary.presence.websocket_server import LocalPresenceWebSocket


def test_youtube_is_explicit_and_disabled_without_opt_in(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.setenv("MARY_YOUTUBE_ENABLED", "false")
    youtube = YouTubeSearch()
    assert youtube.status()["enabled"] is False
    assert youtube.status()["mode"] == "explicit_public_search"


def test_websocket_is_loopback_read_only_and_disabled_by_default(monkeypatch):
    monkeypatch.setenv("MARY_WEBSOCKET_ENABLED", "false")
    monkeypatch.delenv("MARY_WEBSOCKET_HOST", raising=False)
    socket = LocalPresenceWebSocket(lambda: {})
    status = socket.status()
    assert status["enabled"] is False
    assert status["host"] == "127.0.0.1"
    assert status["mode"] == "read_only_presence"
