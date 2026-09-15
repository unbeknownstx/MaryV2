"""Compatibility entrypoint for the canonical cross-platform home node.

Use python -m scripts.run_home_node for new Mac/Windows/Linux deployments.
This wrapper remains for older setup instructions and enrollment tooling.
"""
from __future__ import annotations

import sys

from scripts.run_home_node import main as run_home_node_main


def main(argv: list[str] | None = None) -> int:
    return run_home_node_main(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
