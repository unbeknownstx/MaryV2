"""Compatibility entry point retained for release-registry completeness.

Hotfix 06 supersedes Hotfix 05 while preserving its isolated provenance rules.
"""
from scripts.verify_acceptance_hotfix_06 import main


if __name__ == "__main__":
    main()
