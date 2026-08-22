from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_stage_polish_preserves_absolute_vrm_layout():
    css = _text("desktop/src/style.css")
    assert ".main-stage > * { position:relative" not in css
    assert ".avatar-stage { position:absolute; inset:0" in css


def test_vrm_reframes_after_qt_layout():
    js = _text("desktop/src/main.js")
    assert "window.requestAnimationFrame(() => setAvatarFraming(avatarFraming))" in js
    assert "Mary VRM produced invalid bounds" in js


def test_desktop_has_windowed_maximized_and_true_fullscreen_modes():
    source = _text("mary/desktop/window.py")
    assert 'MARY_DESKTOP_START_MODE", "maximized"' in source
    assert 'QKeySequence("F11")' in source
    assert 'QKeySequence("Alt+Return")' in source
    assert "showFullScreen()" in source
    assert "show_for_startup()" in source


def test_launcher_centers_inside_available_screen():
    source = _text("mary/launcher/window.py")
    assert "availableGeometry()" in source
    assert "show_centered()" in source


def test_state_migration_is_dry_run_by_default_and_preserves_current_desktop_state():
    source = _text("scripts/migrate_repo_state_windows.ps1")
    assert "DRY RUN ONLY" in source
    assert "data.before_repo_migration_" in source
    assert "Move-Item" in source
    assert "Copy-Item" in source
