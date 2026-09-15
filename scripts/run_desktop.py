"""Launch MaryV2 Desktop Alpha."""

from __future__ import annotations

from mary.desktop.webengine_bootstrap import configure_qtwebengine


def main() -> int:
    # Configure Chromium before importing any Qt WebEngine window classes.
    configure_qtwebengine()

    # Product startup is best-effort: bring up an already-installed local
    # conversation runtime before the window resolves its capability-node
    # advertisement. Failure never prevents the desktop from opening because
    # Mary retains her cloud/free fallback routes.
    try:
        from mary.desktop.runtime_supervisor import prepare_desktop_runtime

        runtime = prepare_desktop_runtime()
        state = "READY" if runtime.get("ready") else "DEGRADED"
        local = dict(runtime.get("local") or {})
        print(
            "[MaryDesktop] local runtime "
            f"{state}: {local.get('runtime') or 'none'} / "
            f"{local.get('model') or 'fallback-only'}",
            flush=True,
        )
    except Exception as exc:
        print(
            f"[MaryDesktop] local runtime supervisor skipped: {type(exc).__name__}",
            flush=True,
        )

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
