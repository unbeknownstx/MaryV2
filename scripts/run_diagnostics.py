"""
MaryV2 Diagnostics Runner

Provides a simple command-line entry point for running
Mary's existing diagnostic system.
"""

from mary.core.diagnostics import MaryDiagnostics
from mary.runtime.application import create_application


def main() -> None:
    app = create_application()
    try:
        diagnostics = MaryDiagnostics(app.mary)
        print(diagnostics.report())
    finally:
        app.close()


if __name__ == "__main__":
    main()