"""Run a cross-platform bounded MaryV2 local capability node.

This is the preferred Mac/Linux headless node and can also be used on Windows.
It advertises only locally reachable LLM executors that the creator has also
explicitly allowed in the local device-permission file.
"""
from __future__ import annotations

import argparse
import os
import platform
import signal
import socket
from threading import Event

from dotenv import load_dotenv

from mary.desktop.device_node import DesktopCapabilityNodeAgent, headless_node_capabilities
from mary.distributed import DeviceExecutionPermissions
from mary.runtime.gateway import RemoteMaryGateway, gateway_from_environment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Mary's bounded local capability node.")
    parser.add_argument("--enroll-only", action="store_true", help="Establish durable device trust and exit.")
    args = parser.parse_args(argv)
    load_dotenv()

    if not os.getenv("MARY_CORE_URL", "").strip():
        print("MARY_CORE_URL is not configured. This node requires canonical remote Mary Core.")
        return 2

    permissions = DeviceExecutionPermissions()
    allowed = permissions.allowed()
    available = headless_node_capabilities(permissions)
    capabilities = [item for item in available if item.name in allowed]
    if not capabilities:
        available_names = [item.name for item in available]
        print("No bounded capability is both configured/detected and locally allowed.")
        print(f"Detected/configured: {', '.join(available_names) if available_names else 'none'}")
        print("Allow one explicitly, for example:")
        print("  python -m scripts.node_permissions allow llm.llama_cpp")
        print("  python -m scripts.node_permissions allow llm.ollama")
        print("  python -m scripts.node_permissions allow mcp.opendesign")
        print("MCP capabilities also require an exact per-tool allow:")
        print("  python -m scripts.node_permissions allow-tool opendesign recommend_references")
        return 2

    device_id = (
        os.getenv("MARY_NODE_ID", "").strip()
        or os.getenv("COMPUTERNAME", "").strip()
        or socket.gethostname().strip()
        or "mary-capability-node"
    )
    try:
        gateway = gateway_from_environment(
            application=None,
            device_id=device_id,
            surface="capability_node",
            node_only=True,
        )
    except RuntimeError as exc:
        print(str(exc))
        return 2
    if not isinstance(gateway, RemoteMaryGateway):
        print("Capability node did not resolve remote Mary Core authority.")
        return 2

    agent = DesktopCapabilityNodeAgent(
        gateway,
        application=None,
        bridge=None,
        capabilities=capabilities,
        host_type="capability_node",
        surface="capability_node",
        permissions=permissions,
    )

    if args.enroll_only:
        enrolled = False
        try:
            agent.register()
            enrolled = True
            print("Durable capability-node enrollment completed and stored locally.")
            return 0
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            request_id = str(getattr(exc, "request_id", "") or "")
            error_type = type(exc).__name__
            if status_code is not None:
                safe_detail = f"{error_type}: HTTP {int(status_code)}"
                if request_id:
                    safe_detail += f" request_id={request_id}"
            elif error_type in {"MaryProtocolError", "CredentialStoreError"}:
                safe_detail = f"{error_type}: {exc}"
            else:
                safe_detail = error_type
            print(f"Durable capability-node enrollment failed ({safe_detail}).")
            # Registration can succeed remotely before local durable credential
            # storage fails. In that case the client may already hold a session
            # token even though register() raised. Best-effort disconnect prevents
            # a half-open live node from blocking the next creator-authorized
            # enrollment attempt. Durable trust, if already committed by Core, is
            # intentionally left intact.
            try:
                agent.disconnect()
            except Exception:
                pass
            return 1
        finally:
            if enrolled:
                agent.disconnect()
            os.environ.pop("MARY_NODE_ENROLLMENT_GRANT", None)

    stop = Event()
    def request_stop(*_args) -> None:
        stop.set()
    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if sig is not None:
            try:
                signal.signal(sig, request_stop)
            except Exception:
                pass

    agent.start()
    print("MARYV2 CAPABILITY NODE")
    print("=" * 64)
    print(f"node:             {agent.display_name}")
    print(f"platform:         {platform.system()} {platform.machine()}")
    print("Core authority:   remote / canonical")
    print("capabilities:     " + ", ".join(item.name for item in capabilities))
    for item in capabilities:
        print(
            f"  {item.name}: "
            f"{item.metadata.get('configured_model') or item.metadata.get('runtime') or item.metadata.get('server') or item.readiness}"
        )
    print("Mary identity:    NOT OWNED BY THIS NODE")
    print("Press Ctrl+C to stop.")
    try:
        while not stop.wait(1.0):
            pass
    finally:
        agent.stop()
        print("Capability node disconnected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
