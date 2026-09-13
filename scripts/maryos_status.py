"""Print Mary's bounded operating-environment projection."""
from __future__ import annotations

import argparse
import json

from mary.distributed.os_environment import MaryOSEnvironmentProfile
from mary.distributed.resource_profile import RuntimeResourceProfile


def build_status() -> dict:
    return {
        "maryos": MaryOSEnvironmentProfile.detect().to_dict(),
        "resources": RuntimeResourceProfile.detect().to_dict(),
        "policy": {
            "identity_authority": "mary_core",
            "host_projection": "read_only",
            "arbitrary_shell": False,
            "root_execution": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect MaryOS/Linux host readiness without changing the host.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)
    status = build_status()
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
        return 0
    host = status["maryos"]
    resources = status["resources"]
    print("MARYOS HOST READINESS")
    print("=" * 64)
    print(f"platform:           {host.get('platform')}")
    print(f"distribution:       {host.get('distro_name')}")
    print(f"init:               {host.get('init_system')}")
    print(f"desktop:            {host.get('desktop_session')}")
    print(f"display:            {host.get('display_protocol')}")
    print(f"Omarchy detected:   {host.get('omarchy_detected')}")
    print(f"Hyprland session:   {host.get('hyprland_session')}")
    print(f"Quickshell:         {host.get('quickshell_available')}")
    print(f"MaryOS candidate:   {host.get('maryos_candidate')}")
    print(f"CPU threads:        {resources.get('cpu_count')}")
    print(f"memory GiB:         {resources.get('memory_gib', 'unknown')}")
    print(f"Vulkan:             {resources.get('vulkan_available')}")
    print(f"Ollama:             {resources.get('ollama_available')}")
    print(f"llama.cpp:          {resources.get('llama_cpp_available')}")
    print("authority:          read-only host projection; Core remains Mary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
