"""Read-only audit of Mary's persistent creator profile and provenance."""

from __future__ import annotations

import argparse

from mary.runtime.application import create_application
from mary.runtime.state_audit import format_creator_state_audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show every creator-profile record instead of only conservative test/probe flags.",
    )
    args = parser.parse_args()

    app = create_application(name="creator_state_audit")
    try:
        print(format_creator_state_audit(app.mary, show_all=args.all))
    finally:
        app.close()


if __name__ == "__main__":
    main()
