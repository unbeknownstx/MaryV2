"""Run a bounded Mary capability node on macOS, Windows, or Linux.

This is the preferred home-fabric launcher for MaryV2 13.11. It reuses the
existing durable enrollment, permission file, task broker, Ollama/llama.cpp,
and MCP executors. No arbitrary shell task exists here.
"""
from __future__ import annotations

import argparse
import os
import signal
import socket
from pathlib import Path
from threading import Event

from dotenv import load_dotenv

from mary.desktop.device_node import DesktopCapabilityNodeAgent, headless_node_capabilities
from mary.distributed import CapabilityDescriptor, DeviceExecutionPermissions
from mary.distributed.benchmarking import apply_benchmark_profile, load_profile
from mary.distributed.resource_profile import RuntimeResourceProfile
from mary.runtime.gateway import RemoteMaryGateway, gateway_from_environment


def _resource_capability() -> CapabilityDescriptor:
    profile = RuntimeResourceProfile.detect().to_dict()
    return CapabilityDescriptor(
        name="runtime.resource_profile",
        private=True,
        local=True,
        cost="free",
        latency="instant",
        metadata={
            "platform": profile.get("platform", "unknown"),
            "machine": profile.get("machine", "unknown"),
            "cpu_count": profile.get("cpu_count", 1),
            "memory_gib": profile.get("memory_gib", "unknown"),
            "apple_silicon": profile.get("apple_silicon", False),
            "ollama": profile.get("ollama_available", False),
            "llama_cpp": profile.get("llama_cpp_available", False),
            "whisper_cpp": profile.get("whisper_cpp_available", False),
        },
    )


def _profile_path(cli_path: Path | None) -> Path | None:
    if cli_path is not None:
        return cli_path.expanduser()
    value = os.getenv("MARY_NODE_BENCHMARK_PROFILE", "").strip()
    return Path(value).expanduser() if value else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Mary's bounded cross-platform home capability node.")
    parser.add_argument("--benchmark-profile", type=Path, default=None, help="13.11 benchmark JSON produced by scripts.benchmark_home_node.")
    parser.add_argument("--enroll-only", action="store_true", help="Establish durable node trust and exit.")
    args = parser.parse_args(argv)
    load_dotenv()

    core_url = os.getenv("MARY_CORE_URL", "").strip()
    if not core_url:
        print("MARY_CORE_URL is not configured. A home node requires remote Mary Core.")
        return 2

    permissions = DeviceExecutionPermissions()
    capabilities = headless_node_capabilities(permissions)
    capabilities.append(_resource_capability())

    benchmark_path = _profile_path(args.benchmark_profile)
    benchmark_loaded = False
    if benchmark_path is not None and benchmark_path.exists():
        try:
            capabilities = apply_benchmark_profile(capabilities, load_profile(benchmark_path))
            benchmark_loaded = True
        except Exception as exc:
            print(f"Benchmark profile ignored: {type(exc).__name__}: {exc}")

    device_id = (
        os.getenv("MARY_NODE_ID", "").strip()
        or os.getenv("COMPUTERNAME", "").strip()
        or socket.gethostname().strip()
        or "home-node"
    )
    try:
        gateway = gateway_from_environment(
            application=None,
            device_id=device_id,
            surface="home_node",
            node_only=True,
        )
    except RuntimeError as exc:
        print(str(exc))
        return 2
    if not isinstance(gateway, RemoteMaryGateway):
        print("Home node did not resolve remote Mary Core authority.")
        return 2

    agent = DesktopCapabilityNodeAgent(
        gateway,
        application=None,
        bridge=None,
        capabilities=capabilities,
        host_type="capability_node",
        surface="home_node",
        permissions=permissions,
    )

    if args.enroll_only:
        enrolled = False
        try:
            agent.register()
            enrolled = True
            print("Durable home-node enrollment completed and stored locally.")
            return 0
        except Exception as exc:
            print(f"Durable node enrollment failed: {type(exc).__name__}: {exc}")
            return 1
        finally:
            if enrolled:
                agent.disconnect()
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
    print("MARYV2 13.11 HOME COMPUTE NODE")
    print("=" * 64)
    print(f"node:              {agent.display_name}")
    print(f"platform:          {agent.platform}")
    print(f"benchmark profile: {'loaded' if benchmark_loaded else 'not loaded'}")
    print("capabilities:")
    for capability in capabilities:
        status = "ready" if capability.routable else capability.readiness
        print(f"  - {capability.name:<28} {status}")
    allowed = sorted(permissions.allowed())
    print(f"execution allowed: {', '.join(allowed) if allowed else 'none (default deny)'}")
    print("authority:          compute only; Mary Core owns identity/state")
    print("Press Ctrl+C to stop the node.")

    try:
        while not stop.wait(1.0):
            pass
    finally:
        agent.stop()
        print("Home node disconnected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
