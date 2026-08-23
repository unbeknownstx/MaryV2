from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_release_and_companion_home_are_packaged():
    release = text("mary/runtime/release.py")
    html = text("desktop/index.html")
    assert ('APP_VERSION = "12.10.0"' in release or ('APP_VERSION = "12.11.0"' in release or ('APP_VERSION = "12.12.0"' in release or 'APP_VERSION = "12.12.2"' in release)))
    assert ('DESKTOP_PHASE = "presence-presentation"' in release or 'DESKTOP_PHASE = "fast-dialogue-connected-presence"' in release or 'DESKTOP_PHASE = "cognitive-reservoir-character-runtime"' in release)
    assert 'data-screen="home"' in html
    assert 'id="companion-pulse-card"' in html
    assert (ROOT / "mary/ecosystem/companion.py").is_file()
    assert (ROOT / "desktop/src/ui/presenceHome.js").is_file()
    assert (ROOT / "desktop/src/presence.css").is_file()


def test_portrait_art_is_local_presentation_and_live_vrm_remains():
    html = text("desktop/index.html")
    js = text("desktop/src/main.js")
    assert "mary-reference.jpeg" in html
    assert "data-avatar-presentation" in js
    assert "Portrait Art" in js
    assert "MaryCosma.vrm" in js
    assert "loadMaryVrm" in js
    assert "updateLipSync" in js


def test_vite_8_config_uses_native_dirname_and_rolldown_splitting():
    vite = text("desktop/vite.config.js")
    assert "import.meta.dirname" in vite
    assert "__dirname" not in vite
    assert "codeSplitting" in vite
    assert "three-runtime" in vite
    assert "vrm-runtime" in vite


def test_workspace_actions_publish_typed_presence_context():
    bridge = text("mary/desktop/bridge.py")
    events = text("mary/presence/events.py")
    for name in ("COMMAND_CHANGED", "STUDY_CHANGED", "FOCUS_CHANGED", "CREATIVE_CHANGED"):
        assert name in events
        assert f"PresenceEventType.{name}" in bridge
    assert "publish_workspace_event" in bridge


def test_focus_idle_path_and_chrome_are_quiet():
    bridge = text("mary/desktop/bridge.py")
    manager = text("mary/presence/manager.py")
    css = text("desktop/src/presence.css")
    js = text("desktop/src/main.js")
    assert "focus_active=focus_active" in bridge
    assert '{"animation"} if focus_active else None' in manager
    assert 'data-focus="active"' in css
    assert "!r.focus_quiet" in js


def test_home_renderer_is_read_only_and_cross_workspace():
    home = text("desktop/src/ui/presenceHome.js")
    companion = text("mary/ecosystem/companion.py")
    for screen in ("command", "study", "focus", "stream", "chat"):
        assert f'data-screen-jump="{screen}"' in home or f'"screen": "{screen}"' in companion
    assert "companion.json" not in companion
    assert "not memory" in companion


def test_presence_css_has_laptop_and_low_height_breakpoints():
    css = text("desktop/src/presence.css")
    assert "@media (max-width:1320px)" in css
    assert "@media (max-width:1099px)" in css
    assert "@media (max-height:760px)" in css


def test_package_metadata_retains_12_10_foundations_in_current_release():
    package = text("PACKAGE_INFO.json")
    assert ('"version": "12.10.0"' in package or ('"version": "12.11.0"' in package or ('"version": "12.12.0"' in package or '"version": "12.12.2"' in package)))
    assert ('"desktop_phase": "presence-presentation"' in package or '"desktop_phase": "fast-dialogue-connected-presence"' in package or '"desktop_phase": "cognitive-reservoir-character-runtime"' in package)


def test_windows_setup_references_existing_regression_files_only():
    setup = text("SETUP_WINDOWS_12_10.ps1")
    referenced = (
        "tests/desktop/test_desktop_uplift_12_9.py",
        "tests/llm/test_provider_timing_12_9.py",
        "tests/voice/test_voice_timing_12_9.py",
        "tests/desktop/test_presence_presentation_12_10.py",
        "tests/integration/test_presence_pathways_12_10.py",
    )
    for relative in referenced:
        assert relative in setup
        assert (ROOT / relative).is_file(), relative
    assert "MIGRATE_PRIVATE_STATE.ps1" not in setup
    assert "MaryV2_12_9_CLEAN_PROJECT" not in setup


def test_distributable_no_longer_depends_on_temporary_clean_project_flow():
    assert not (ROOT / "MIGRATE_PRIVATE_STATE.ps1").exists()
    assert not (ROOT / "SETUP_CLEAN_WINDOWS.ps1").exists()
    assert (ROOT / "SETUP_WINDOWS_12_10.ps1").is_file()
    assert (ROOT / "SETUP_WINDOWS.ps1").is_file()
