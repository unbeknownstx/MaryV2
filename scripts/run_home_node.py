"""Run a bounded Mary capability node on macOS, Windows, or Linux.

This is the preferred home-fabric launcher for MaryV2 13.12+. It reuses the
existing durable enrollment, permission file, task broker, local inference,
MCP executors and explicit sensor workers. No arbitrary shell task exists here.
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
from mary.distributed.benchmarking import (
    apply_benchmark_profile,
    host_fingerprint,
    load_profile,
)
from mary.distributed.creative_runtime import creative_runtime_catalog
from mary.distributed.inference_acceleration import local_acceleration_status
from mary.distributed.hardware_profiles import (
    HARDWARE_PROFILES as _HARDWARE_PROFILES,
    SAFE_LOCAL_MODEL,
    apply_hardware_profile as _apply_hardware_profile,
)
from mary.distributed.local_runtime_catalog import local_runtime_catalog
from mary.distributed.os_environment import MaryOSEnvironmentProfile
from mary.distributed.resource_profile import RuntimeResourceProfile
from mary.distributed.sensor_node import SensorCapabilityNodeAgent
from mary.distributed.sensors import sensor_capabilities
from mary.runtime.gateway import RemoteMaryGateway, gateway_from_environment
from mary.runtime.resource_reporting_gateway import ResourceReportingGateway


def _optional_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _resource_capability() -> CapabilityDescriptor:
    profile = RuntimeResourceProfile.detect().to_dict()
    os_environment = MaryOSEnvironmentProfile.detect().to_dict()
    runtime = os.getenv("MARY_LOCAL_INFERENCE_RUNTIME", "ollama").strip().lower() or "ollama"
    model = (
        os.getenv("MARY_LOCAL_INFERENCE_MODEL", "").strip()
        or os.getenv("MARY_OLLAMA_MODEL", SAFE_LOCAL_MODEL).strip()
        or SAFE_LOCAL_MODEL
    )
    acceleration = local_acceleration_status(
        model=model,
        runtime=runtime,
        gguf_nextn_predict_layers=_optional_int("MARY_GGUF_NEXTN_PREDICT_LAYERS"),
    )
    candidate = dict(acceleration.get("candidate") or {})
    inference_runtimes = local_runtime_catalog()
    creative_runtimes = creative_runtime_catalog()
    configured_inference = [
        str(item.get("name")) for item in inference_runtimes if item.get("configured")
    ]
    configured_creative = [
        str(item.get("name")) for item in creative_runtimes if item.get("configured")
    ]
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
            "metal": profile.get("metal_available", False),
            "vulkan": profile.get("vulkan_available", False),
            "ollama": profile.get("ollama_available", False),
            "llama_cpp": profile.get("llama_cpp_available", False),
            "whisper_cpp": profile.get("whisper_cpp_available", False),
            "distro_id": os_environment.get("distro_id", "unknown"),
            "init_system": os_environment.get("init_system", "unknown"),
            "desktop_session": os_environment.get("desktop_session", "unknown"),
            "display_protocol": os_environment.get("display_protocol", "headless"),
            "systemd": os_environment.get("systemd_available", False),
            "hyprland": os_environment.get("hyprland_session", False),
            "quickshell": os_environment.get("quickshell_available", False),
            "omarchy": os_environment.get("omarchy_detected", False),
            "maryos_candidate": os_environment.get("maryos_candidate", False),
            "local_inference_runtime": runtime[:32],
            "local_inference_model": model[:128],
            "configured_inference_runtimes": configured_inference[:16],
            "configured_creative_runtimes": configured_creative[:16],
            "acceleration_method": candidate.get("method"),
            "acceleration_state": candidate.get("state"),
            "acceleration_checkpoint_evidence": candidate.get("checkpoint_evidence"),
            "acceleration_speculative_tokens": acceleration.get("speculative_tokens"),
            "acceleration_policy_version": acceleration.get("version"),
        },
    )


def _profile_path(cli_path: Path | None) -> Path | None:
    if cli_path is not None:
        return cli_path.expanduser()
    value = os.getenv("MARY_NODE_BENCHMARK_PROFILE", "").strip()
    return Path(value).expanduser() if value else None


def _verify_bounded_agent_contract() -> None:
    """Keep sensors as a narrow extension of the established node agent."""
    if not issubclass(SensorCapabilityNodeAgent, DesktopCapabilityNodeAgent):
        raise RuntimeError("Home sensor node must remain a bounded DesktopCapabilityNodeAgent extension.")


def _authorized_sensor_capabilities(
    permissions: DeviceExecutionPermissions,
) -> list[CapabilityDescriptor]:
    """Advertise sensor workers only when the local device has opted in."""

    return [
        capability
        for capability in sensor_capabilities()
        if permissions.is_allowed(capability.name)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Mary's bounded cross-platform home capability node.")
    parser.add_argument("--benchmark-profile", type=Path, default=None, help="Benchmark JSON produced by scripts.benchmark_home_node.")
    parser.add_argument(
        "--hardware-profile",
        choices=sorted(_HARDWARE_PROFILES),
        default=None,
        help="Apply an explicit device-local inference safety profile.",
    )
    parser.add_argument("--enroll-only", action="store_true", help="Establish durable node trust and exit.")
    args = parser.parse_args(argv)
    load_dotenv()
    hardware_profile = _apply_hardware_profile(args.hardware_profile)
    _verify_bounded_agent_contract()

    core_url = os.getenv("MARY_CORE_URL", "").strip()
    if not core_url:
        print("MARY_CORE_URL is not configured. A home node requires remote Mary Core.")
        return 2

    permissions = DeviceExecutionPermissions()
    capabilities = [
        *headless_node_capabilities(permissions),
        *_authorized_sensor_capabilities(permissions),
        _resource_capability(),
    ]

    benchmark_path = _profile_path(args.benchmark_profile)
    benchmark_loaded = False
    if benchmark_path is not None and benchmark_path.exists():
        try:
            benchmark_profile = load_profile(benchmark_path)
            measured_host = str(benchmark_profile.get("host_fingerprint") or "").strip()
            current_host = host_fingerprint()
            if measured_host and measured_host != current_host:
                print("Benchmark profile ignored: host fingerprint does not match this machine.")
            else:
                capabilities = apply_benchmark_profile(capabilities, benchmark_profile)
                benchmark_loaded = any(
                    "benchmark_profile_version" in dict(item.metadata or {})
                    for item in capabilities
                )
                if not benchmark_loaded:
                    print("Benchmark profile loaded but no compatible measurements matched the active runtime.")
        except Exception as exc:
            print(f"Benchmark profile ignored: {type(exc).__name__}: {exc}")

    device_id = (
        os.getenv("MARY_NODE_ID", "").strip()
        or os.getenv("COMPUTERNAME", "").strip()
        or socket.gethostname().strip()
        or "home-node"
    )
    try:
        gateway = gateway_from_environment(application=None, device_id=device_id, surface="home_node", node_only=True)
    except RuntimeError as exc:
        print(str(exc))
        return 2
    if not isinstance(gateway, RemoteMaryGateway):
        print("Home node did not resolve remote Mary Core authority.")
        return 2
    node_gateway = ResourceReportingGateway(gateway)

    agent = SensorCapabilityNodeAgent(
        node_gateway,
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
    print("MARYV2 HOME COMPUTE NODE")
    print("=" * 64)
    print(f"node:              {agent.display_name}")
    print(f"platform:          {agent.platform}")
    print(f"hardware profile:  {args.hardware_profile or 'default'}")
    print(f"benchmark profile: {'loaded' if benchmark_loaded else 'not loaded'}")
    print("capabilities:")
    for capability in capabilities:
        status = "ready" if capability.routable else capability.readiness
        print(f"  - {capability.name:<28} {status}")
    resource_cap = next((item for item in capabilities if item.name == "runtime.resource_profile"), None)
    if resource_cap is not None:
        print(f"local runtime:      {resource_cap.metadata.get('local_inference_runtime', 'unknown')}")
        print(f"runtime fabric:     {', '.join(resource_cap.metadata.get('configured_inference_runtimes') or []) or 'none explicitly configured'}")
        print(f"creative fabric:    {', '.join(resource_cap.metadata.get('configured_creative_runtimes') or []) or 'none explicitly configured'}")
        print(f"acceleration:       {resource_cap.metadata.get('acceleration_method')} / {resource_cap.metadata.get('acceleration_state')}")
        print(f"host substrate:     {resource_cap.metadata.get('distro_id', 'unknown')} / {resource_cap.metadata.get('init_system', 'unknown')}")
    allowed = sorted(permissions.allowed())
    print(f"execution allowed: {', '.join(allowed) if allowed else 'none (default deny)'}")
    print("sensor policy:      transcription/screen capture are explicit local opt-ins")
    print("authority:          compute/evidence only; Mary Core owns identity/state")
    print("registration:       starting / waiting for Core acknowledgement")
    print("Press Ctrl+C to stop the node.")

    last_registered: bool | None = None
    last_error = ""
    try:
        while not stop.wait(1.0):
            status = agent.status()
            registered = bool(status.get("registered", False))
            error = str(status.get("last_error") or "").strip()
            if registered != last_registered:
                print(
                    "registration:       "
                    + ("connected to canonical Core" if registered else "not connected / retrying")
                )
                last_registered = registered
            if error and error != last_error:
                print(f"registration detail: {error}")
                last_error = error
            elif not error and last_error:
                print("registration detail: recovered")
                last_error = ""
    finally:
        agent.stop()
        print("Home node disconnected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
