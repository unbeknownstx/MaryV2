"""Launch MaryV2 Desktop Alpha."""

from __future__ import annotations

from mary.desktop.webengine_bootstrap import configure_qtwebengine


def main() -> int:
    # Qt WebEngine reads Chromium process flags during import/initialization.
    # Configure them before importing the window module so the Vite production
    # shell can load its local JS/CSS assets on current macOS Qt builds.
    configure_qtwebengine()

    try:
        from mary.desktop.window import run_desktop
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("PySide6"):
            print("MaryV2 Desktop requires PySide6.")
            print("Install it with: pip install -r requirements-desktop.txt")
            return 2
        raise

    try:
        return run_desktop()
    except FileNotFoundError as exc:
        print(exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
