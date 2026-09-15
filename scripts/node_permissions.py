"""Manage local device capability execution permissions.

Examples:
    python -m scripts.node_permissions status
    python -m scripts.node_permissions allow mcp.opendesign
    python -m scripts.node_permissions allow-tool opendesign recommend_references
    python -m scripts.node_permissions deny-tool opendesign recommend_references
"""
from __future__ import annotations

import argparse
import json

from mary.distributed import DeviceExecutionPermissions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MaryV2 local device capability permissions")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    allow = sub.add_parser("allow")
    allow.add_argument("capability")
    deny = sub.add_parser("deny")
    deny.add_argument("capability")
    allow_tool = sub.add_parser("allow-tool")
    allow_tool.add_argument("server")
    allow_tool.add_argument("tool")
    deny_tool = sub.add_parser("deny-tool")
    deny_tool.add_argument("server")
    deny_tool.add_argument("tool")
    args = parser.parse_args(argv)

    permissions = DeviceExecutionPermissions()
    if args.command == "allow":
        payload = permissions.allow(args.capability)
    elif args.command == "deny":
        payload = permissions.deny(args.capability)
    elif args.command == "allow-tool":
        payload = permissions.allow_mcp_tool(args.server, args.tool)
    elif args.command == "deny-tool":
        payload = permissions.deny_mcp_tool(args.server, args.tool)
    else:
        payload = permissions.status()

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
