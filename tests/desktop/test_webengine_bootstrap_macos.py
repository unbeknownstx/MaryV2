from __future__ import annotations

from pathlib import Path

from mary.desktop.webengine_bootstrap import configure_qtwebengine


FILE_ACCESS_FLAG = "--allow-file-access-from-files"


def test_macos_bootstrap_adds_local_file_access_flag(monkeypatch):
    monkeypatch.delenv("QTWEBENGINE_CHROMIUM_FLAGS", raising=False)

    effective = configure_qtwebengine(platform="darwin")

    assert effective == FILE_ACCESS_FLAG
    assert effective == __import__("os").environ["QTWEBENGINE_CHROMIUM_FLAGS"]


def test_macos_bootstrap_preserves_existing_flags_and_is_idempotent(monkeypatch):
    monkeypatch.setenv("QTWEBENGINE_CHROMIUM_FLAGS", "--enable-logging=stderr")

    first = configure_qtwebengine(platform="darwin")
    second = configure_qtwebengine(platform="darwin")

    assert first == f"--enable-logging=stderr {FILE_ACCESS_FLAG}"
    assert second == first
    assert second.split().count(FILE_ACCESS_FLAG) == 1


def test_non_macos_bootstrap_leaves_webengine_flags_unchanged(monkeypatch):
    monkeypatch.setenv("QTWEBENGINE_CHROMIUM_FLAGS", "--existing-flag")

    effective = configure_qtwebengine(platform="win32")

    assert effective == "--existing-flag"
    assert __import__("os").environ["QTWEBENGINE_CHROMIUM_FLAGS"] == "--existing-flag"


def test_entrypoints_configure_webengine_before_importing_qt_windows():
    root = Path(__file__).resolve().parents[2]
    desktop = (root / "scripts" / "run_desktop.py").read_text(encoding="utf-8")
    launcher = (root / "scripts" / "run_launcher.py").read_text(encoding="utf-8")

    assert desktop.index("configure_qtwebengine()") < desktop.index(
        "from mary.desktop.window import run_desktop"
    )
    assert launcher.index("configure_qtwebengine()") < launcher.index(
        "from mary.launcher.window import run_launcher"
    )
