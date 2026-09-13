"""Run MaryV2's bounded Windows Ollama capability node without the Desktop GUI."""
from __future__ import annotations

import argparse
import os
import signal
import socket
from threading import Event
from time import sleep

from dotenv import load_dotenv

from mary.desktop.device_node import DesktopCapabilityNodeAgent, headless_ollama_capabilities
from mary.distributed import DeviceExecutionPermissions
from mary.runtime.gateway import RemoteMaryGateway, gateway_from_environment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Mary's bounded Windows Ollama capability node.",
    )
    parser.add_argument(
        "--enroll-only",
        action="store_true",
        help="Establish durable device trust, store it locally, then exit.",
    )
    args = parser.parse_args(argv)
    load_dotenv()

    core_url = os.getenv("MARY_CORE_URL", "").strip()
    if not core_url:
        print("MARY_CORE_URL is not configured. The headless node requires remote Mary Core.")
        return 2
    permissions = DeviceExecutionPermissions()
    if not permissions.is_allowed("llm.ollama"):
        print("Local permission llm.ollama is not enabled.")
        print("Run: python -m scripts.node_permissions allow llm.ollama")
        return 2

    capabilities = headless_ollama_capabilities()
    if not capabilities:
        print("Ollama is not available on this PC. Start Ollama and try again.")
        return 2

    device_id = (
        os.getenv("MARY_NODE_ID", "").strip()
        or os.getenv("COMPUTERNAME", "").strip()
        or socket.gethostname().strip()
        or "windows-node"
    )
    try:
        gateway = gateway_from_environment(
            application=None,
            device_id=device_id,
            surface="windows_node",
            node_only=True,
        )
    except RuntimeError as exc:
        print(str(exc))
        return 2
    if not isinstance(gateway, RemoteMaryGateway):
        print("Headless node did not resolve remote Mary Core authority.")
        return 2

    agent = DesktopCapabilityNodeAgent(
        gateway,
        application=None,
        bridge=None,
        capabilities=capabilities,
        host_type="capability_node",
        surface="windows_node",
    )

    if args.enroll_only:
        enrolled = False
        try:
            agent.register()
            enrolled = True
            print("Durable node enrollment completed and was stored for this Windows user.")
            return 0
        except Exception:
            print("Durable node enrollment failed.")
            return 1
        finally:
            if enrolled:
                agent.disconnect()
            # The short-lived enrollment grant remains process-only. The
            # credential store has already protected the durable proof.
            os.environ.pop("MARY_NODE_ENROLLMENT_GRANT", None)

    stop = Event()

    def _request_stop(*_args) -> None:
        stop.set()

    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if sig is not None:
            try:
                signal.signal(sig, _request_stop)
            except Exception:
                pass

    agent.start()
    print("MARYV2 WINDOWS HEADLESS NODE")
    print("=" * 64)
    print(f"node:             {agent.display_name}")
    print("surface:          windows_node")
    print("capability:       llm.ollama")
    print(f"model:            {capabilities[0].metadata.get('configured_model', '')}")
    print("Desktop GUI:      NOT RUNNING / NOT REQUIRED")
    print("Enrollment:       one-time grant or stored local credential")
    print("Press Ctrl+C to stop the node.")

    last_task_signature = ""
    try:
        while not stop.wait(1.0):
            status = agent.status()
            task = dict(status.get("last_task", {}) or {})
            signature = repr(sorted(task.items()))
            if task and signature != last_task_signature:
                last_task_signature = signature
                print(
                    "task: "
                    f"{task.get('capability', 'unknown')} "
                    f"status={task.get('status', 'unknown')} "
                    f"model={task.get('model', '')} "
                    f"ctx={task.get('num_ctx', '')} "
                    f"est_prompt_tokens={task.get('estimated_prompt_tokens', '')} "
                    f"elapsed_ms={task.get('elapsed_ms', '')}"
                )
                if task.get("status") == "failed":
                    print(
                        "task_error: "
                        f"{task.get('error_type', 'unknown')} "
                        f"{status.get('last_error', '')}"
                    )
    finally:
        agent.stop()
        print("Headless node disconnected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
