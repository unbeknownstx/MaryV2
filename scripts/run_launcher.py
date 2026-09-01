"""Launch the MaryV2 game-style launcher."""

from __future__ import annotations

from mary.desktop.webengine_bootstrap import configure_qtwebengine


def main() -> int:
    # The launcher is built by the same Vite pipeline and uses the same local
    # file:// asset model as the main desktop shell.  Configure WebEngine before
    # importing the Qt window for identical macOS behavior.
    configure_qtwebengine()

    try:
        from mary.launcher.window import run_launcher
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("PySide6"):
            print("Mary Launcher requires PySide6.")
            print("Install it with: pip install -r requirements-desktop.txt")
            return 2
        raise

    try:
        return run_launcher()
    except FileNotFoundError as exc:
        print(exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
