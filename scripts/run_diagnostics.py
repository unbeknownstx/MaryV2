"""
MaryV2 Diagnostics Runner

Provides a simple command-line entry point for running
Mary's existing diagnostic system.
"""

from mary.core.diagnostics import MaryDiagnostics
from mary.core.mary import Mary


def main() -> None:
    mary = Mary()

    diagnostics = MaryDiagnostics(
        mary
    )

    print(
        diagnostics.report()
    )


if __name__ == "__main__":
    main()