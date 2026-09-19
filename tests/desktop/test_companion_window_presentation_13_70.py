from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_native_desktop_has_opt_in_companion_window_mode():
    bridge = (ROOT / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    window = (ROOT / "mary" / "desktop" / "window.py").read_text(encoding="utf-8")
    ui = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    css = (ROOT / "desktop" / "src" / "companion-window.css").read_text(encoding="utf-8")
    html = (ROOT / "desktop" / "index.html").read_text(encoding="utf-8")

    assert "windowPresentationRequested = Signal(str)" in bridge
    assert "def setWindowPresentationMode" in bridge
    assert "_set_window_presentation_mode" in window
    assert "WindowStaysOnTopHint" in window
    assert "WA_TranslucentBackground" in window
    assert "setBackgroundColor(QColor(0, 0, 0, 0))" in window
    assert "Ctrl+Shift+P" in window

    assert "setWindowPresentationMode" in ui
    assert "desktop-companion-toggle" in ui
    assert "companion-exit" in html
    assert 'html[data-window-mode="companion"]' in css
    assert "background: transparent !important" in css


def test_companion_window_is_presentation_only():
    window = (ROOT / "mary" / "desktop" / "window.py").read_text(encoding="utf-8")
    start = window.index("def _set_window_presentation_mode")
    end = window.index("def _project_window_mode_to_frontend", start)
    block = window[start:end].lower()

    for forbidden in (
        "memory",
        "relationship",
        "provider",
        "tool",
        "node_registry",
        "autonomy",
        "write_",
    ):
        assert forbidden not in block


def test_character_studio_scene_presets_are_renderer_local():
    source = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "applyStageScenePreset" in source
    assert "data-stage-scene" in source
    assert "stageGroundMaterial" in source
    assert "renderer.setClearColor(0x000000, 0)" in source
    assert "stageSceneBeforeCompanion" in source
    assert "scene: stageScenePreset" in source
