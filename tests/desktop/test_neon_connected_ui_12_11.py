from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_screen_launcher_and_less_cluttered_dock_exist():
    html = text("desktop/index.html")
    assert 'id="screen-launcher"' in html
    assert 'id="workspace-menu-button"' in html
    assert "compact-dock" in html


def test_neon_street_clarity_layer_is_packaged():
    css = text("desktop/src/neon-street.css")
    js = text("desktop/src/main.js")
    assert "--street-blue" in css
    assert "screen-launcher-grid" in css
    assert "youtube-result" in css
    assert "import './neon-street.css'" in js


def test_ambient_audio_is_local_and_ducks_for_speech():
    html = text("desktop/index.html")
    js = text("desktop/src/main.js")
    assert 'id="ambient-audio"' in html
    assert "ambient_neon.wav" in html
    assert "duckAmbientVolume" in js
    assert "restoreAmbientVolume" in js
    assert (ROOT / "desktop/public/assets/sounds/ambient_neon.wav").is_file()


def test_youtube_and_websocket_surfaces_are_optional():
    bridge = text("mary/desktop/bridge.py")
    settings = text("desktop/src/main.js")
    assert "searchYouTube" in bridge
    assert "LocalPresenceWebSocket" in bridge
    assert "Local WebSocket" in settings
    assert "OpenAI Expert" in settings


def test_runtime_trace_surfaces_lane():
    trace = text("mary/desktop/turn_trace.py")
    ui = text("desktop/src/main.js")
    assert '"conversation_lane"' in trace
    assert "trace.conversation_lane" in ui
