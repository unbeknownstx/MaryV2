"""Inspect MaryV2's optional node-local MCP capability fabric.

This command never dispatches Mary Core tasks and has no tool-call subcommand.
"status" is local/config-only. "discover" and "diagnostics" explicitly contact
configured MCP endpoints to list tool names for permission review.
"""
from __future__ import annotations

import argparse
import json

from dotenv import load_dotenv

from mary.distributed import DeviceExecutionPermissions, MCPFabric, sanitize_mcp_error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MaryV2 MCP node capability diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show safe local configuration without contacting MCP servers.")
    discover = sub.add_parser("discover", help="Contact one configured MCP server and list its tools.")
    discover.add_argument("server", choices=("opendesign", "scrapling", "langflow"))
    sub.add_parser("diagnostics", help="Probe every configured MCP server.")
    args = parser.parse_args(argv)

    load_dotenv()
    fabric = MCPFabric(DeviceExecutionPermissions())
    try:
        if args.command == "discover":
            payload = fabric.discover(args.server)
        elif args.command == "diagnostics":
            payload = fabric.diagnostics()
        else:
            payload = fabric.status()
    except Exception as exc:
        payload = {
            "ok": False,
            "error_type": type(exc).__name__,
            "error": sanitize_mcp_error(f"{type(exc).__name__}: {exc}"),
            "status": fabric.status(),
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
