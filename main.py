"""
MaryV2 Entry Point

Canonical project entry point.

The actual interactive application runtime lives in
mary.runtime.application so every supported entry point starts the same
complete MaryV2 system.
"""

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
        name="mary",
    ).pipeline


def main() -> None:
    """Run the canonical MaryV2 terminal application."""

    run_interactive()


if __name__ == "__main__":
    main()
