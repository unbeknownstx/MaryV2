"""
MaryV2 Runner

Canonical terminal launcher for MaryV2.

Run with:

    python -m scripts.run_mary

All supported terminal entry points delegate to the same application runtime.
"""

from __future__ import annotations

from mary.runtime.application import run_interactive


def main() -> None:
    """Start the canonical MaryV2 terminal application."""

    run_interactive()


if __name__ == "__main__":
    main()
