"""Compatibility entrypoint for the canonical cross-platform home node.

New Windows deployments should invoke scripts.run_home_node directly. This
module remains so old shortcuts/tasks cannot create a second windows_node
registration for the same device ID.
"""
from __future__ import annotations

import os
import sys

from scripts.run_home_node import main as run_home_node_main


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--hardware-profile" not in args:
        profile = os.getenv(
            "MARY_WINDOWS_HARDWARE_PROFILE",
            "windows-rx580-4gb",
        ).strip()
        if profile:
            args = ["--hardware-profile", profile, *args]
    return run_home_node_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
