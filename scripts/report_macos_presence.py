"""Report bounded macOS foreground-app context to canonical Mary Core.

Explicit opt-in utility for a Mac capability client.  It never captures screen
pixels, keystrokes, document contents, or arbitrary process lists.  The only
observation sent is the foreground application name and, when macOS permits it,
a bounded front-window title.  Mary Core stores this as environment context,
not identity or durable memory.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Callable

from dotenv import load_dotenv

from mary.protocol.client import MaryClient


@dataclass(frozen=True)
class ForegroundContext:
    application: str
    window_title: str = ""

    @property
    def summary(self) -> str:
        if self.window_title:
            return f"{self.application} — {self.window_title}"[:700]
        return self.application[:700]


def _osascript(script: str) -> str:
    completed = subprocess.run(
        ["osascript", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=3,
    )
    return " ".join(completed.stdout.split()).strip()


def foreground_context(*, runner: Callable[[str], str] = _osascript) -> ForegroundContext:
    app = runner(
        'tell application "System Events" to get name of first application process whose frontmost is true'
    )
    if not app:
        raise RuntimeError("macOS did not report a foreground application")

    # Window-title access may require Accessibility permission.  Failure is
    # intentionally non-fatal; the app name alone is useful bounded context.
    title = ""
    try:
        title = runner(
            'tell application "System Events" to tell first application process whose frontmost is true '
            'to get name of front window'
        )
    except Exception:
        title = ""
    return ForegroundContext(application=app[:160], window_title=title[:240])


def core_client() -> MaryClient:
    load_dotenv(override=False)
    url = str(os.environ.get("MARY_CORE_URL") or "").strip()
    token = str(os.environ.get("MARY_CORE_TOKEN") or "").strip()
    if not url:
        raise RuntimeError("MARY_CORE_URL is not configured")
    if not token:
        raise RuntimeError("MARY_CORE_TOKEN is not configured")
    return MaryClient(
        url,
        token=token,
        device_id=str(os.environ.get("MARY_DEVICE_ID") or "mac-presence"),
        surface="mac-presence",
        timeout=8,
    )


def publish(client: MaryClient, context: ForegroundContext) -> dict:
    metadata = {"platform": "macos", "application": context.application}
    if context.window_title:
        metadata["window_title"] = context.window_title
    return client.runtime_action(
        "presence.observe",
        {
            "event_type": "foreground_app",
            "summary": context.summary,
            "importance": 0.45,
            "metadata": metadata,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true", help="Report foreground changes until interrupted.")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds (minimum 1).")
    parser.add_argument("--print-only", action="store_true", help="Inspect local foreground context without sending it.")
    args = parser.parse_args()

    interval = max(1.0, min(60.0, float(args.interval)))
    client = None if args.print_only else core_client()
    last: ForegroundContext | None = None

    while True:
        current = foreground_context()
        if current != last:
            if args.print_only:
                print(current.summary)
            else:
                result = publish(client, current)  # type: ignore[arg-type]
                print(f"Mary Core presence: {current.summary} ({'ok' if result.get('ok') else 'error'})")
            last = current

        if not args.watch:
            break
        time.sleep(interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
