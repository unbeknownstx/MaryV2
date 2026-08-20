"""Compatibility entry point retained for release-registry completeness.

Hotfix 05 supersedes the Hotfix 04 provenance verifier and fixes its dependence
on the developer's real persistent relationship/agency state.
"""
from scripts.verify_acceptance_hotfix_05 import main


if __name__ == "__main__":
    main()
