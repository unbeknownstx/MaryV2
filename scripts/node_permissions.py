"""Manage local device capability execution permissions.

Examples:
    python -m scripts.node_permissions status
    python -m scripts.node_permissions allow personal_search
    python -m scripts.node_permissions deny personal_search
"""
from __future__ import annotations

import argparse
import json

from mary.distributed import DeviceExecutionPermissions


def main() -> int:
    parser = argparse.ArgumentParser(description="MaryV2 local device capability permissions")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    allow = sub.add_parser("allow")
    allow.add_argument("capability")
    deny = sub.add_parser("deny")
    deny.add_argument("capability")
    args = parser.parse_args()

    permissions = DeviceExecutionPermissions()
    if args.command == "allow":
        payload = permissions.allow(args.capability)
    elif args.command == "deny":
        payload = permissions.deny(args.capability)
    else:
        payload = permissions.status()

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
