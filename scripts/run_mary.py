"""MaryV2 canonical terminal launcher.

``python -m scripts.run_mary`` is a presentation surface.  Authority resolution
lives in :mod:`mary.runtime.terminal`: remote Core wins whenever
``MARY_CORE_URL`` is configured; standalone Mary is created only when remote
Core is intentionally absent.
"""
from __future__ import annotations

from dotenv import load_dotenv

from mary.runtime.terminal import run_terminal


def main() -> None:
    # Load configuration once at the process boundary. Authority resolution
    # inside run_terminal() then depends only on the established environment
    # and cannot unexpectedly rehydrate variables mid-call.
    load_dotenv(override=False)
    run_terminal()


if __name__ == "__main__":
    main()
