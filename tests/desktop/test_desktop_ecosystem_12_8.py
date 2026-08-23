from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_release_metadata_preserves_12_8_foundation_under_12_9():
    source = text("mary/runtime/release.py")
    assert ('APP_VERSION = "12.11.0"' in source or ('APP_VERSION = "12.12.0"' in source or 'APP_VERSION = "12.12.2"' in source))
    assert any(phase in source for phase in (
        'DESKTOP_PHASE = "presence-presentation"',
        'DESKTOP_PHASE = "fast-dialogue-connected-presence"',
        'DESKTOP_PHASE = "cognitive-reservoir-character-runtime"',
    ))


def test_game_shell_exposes_new_core_workspaces():
    html = text("desktop/index.html")
    js = text("desktop/src/main.js")
    for label in ("Study", "Command", "Focus", "Stream"):
        assert label in html
    for screen in ("renderStudy", "renderCommand", "renderFocus", "renderStream", "renderSearch", "renderResearch", "renderArcade", "renderDiagnostics"):
        assert screen in js


def test_game_shell_keeps_real_vrm_voice_and_persistent_chat():
    html = text("desktop/index.html")
    js = text("desktop/src/main.js")
    assert "MaryCosma.vrm" in js
    assert "chat-scroll" in html
    assert "composer-deck" in html
    assert "playVoice" in js
    assert "updateLipSync" in js


def test_12_8_original_assets_exist():
    required = (
        "desktop/design/MARY_12_8_ECOSYSTEM_TARGET.png",
        "desktop/public/assets/ui/mary-sigil.svg",
        "desktop/public/assets/ui/neon-grid.svg",
        "desktop/public/assets/sounds/startup.wav",
        "desktop/public/assets/sounds/ui_select.wav",
        "desktop/public/assets/sounds/focus_complete.wav",
        "desktop/public/assets/sounds/idle_hum.wav",
    )
    for relative in required:
        path = ROOT / relative
        assert path.exists(), relative
        assert path.stat().st_size > 40


def test_bridge_exposes_ecosystem_without_second_mary():
    bridge = text("mary/desktop/bridge.py")
    assert "MaryEcosystem(self.application.mary)" in bridge
    assert "getEcosystemState" in bridge
    assert "personalSearch" in bridge
    assert "startFocus" in bridge
    assert "createStudyProject" in bridge
    assert "Mary(" not in bridge


def test_local_voice_is_optional_and_cloud_fallback_is_opt_in():
    source = text("mary/desktop/voice.py")
    env = text(".env.example")
    assert 'os.getenv("MARY_TTS_PROVIDER", "off")' in source
    assert "windows_sapi" in source
    assert "piper" in source.lower()
    assert "MARY_TTS_ALLOW_CLOUD_FALLBACK" in source
    assert any(mode in env for mode in ("MARY_TTS_PROVIDER=local_first", "MARY_TTS_PROVIDER=auto_fast"))
    assert "MARY_TTS_ALLOW_CLOUD_FALLBACK=false" in env


def test_boot_and_ui_sound_polish_is_local():
    html = text("desktop/index.html")
    css = text("desktop/src/style.css")
    assert "boot-screen" in html and "startup.wav" in html
    assert "boot-pulse" in css and "stage-breathe" in css
    assert "cdn.jsdelivr" not in html.lower()
    assert "unpkg" not in html.lower()
