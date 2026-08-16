"""
MaryV2 Interactive Runtime

Compatibility entry point for the canonical MaryV2 terminal application.

This module no longer builds a separate LLM-only conversation pipeline.
It delegates to mary.runtime.application so it runs the same complete Mary
system as main.py and scripts.run_mary.
"""

from __future__ import annotations

from mary.runtime.application import (
    create_application,
    run_interactive,
)
from mary.runtime.pipeline import Pipeline


def create_mary() -> Pipeline:
    """
    Compatibility factory returning the canonical full-Mary pipeline.
    """

    return create_application(
        name="mary_interactive",
    ).pipeline


def main() -> None:
    """Start the canonical MaryV2 interactive session."""

    run_interactive()


if __name__ == "__main__":
    main()
