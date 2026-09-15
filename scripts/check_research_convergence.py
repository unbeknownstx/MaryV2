"""Read-only diagnostic for MaryV2 13.29-13.32 research convergence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Support both:
#   python -m scripts.check_research_convergence
#   python scripts/check_research_convergence.py
# Direct file execution otherwise places only scripts/ on sys.path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mary.cognition.deliberation import DeliberationGovernor
from mary.distributed.research_runtime_catalog import research_runtime_status
from mary.learning.trajectory import TrajectoryRecorder
from mary.memory.action_policy import MemoryActionPolicy
from mary.realtime.duplex_policy import DuplexInteractionPolicy


def snapshot() -> dict:
    return {
        "version": "13.32",
        "deliberation": DeliberationGovernor().status(),
        "memory_action_policy": MemoryActionPolicy().status(),
        "trajectory_telemetry": TrajectoryRecorder().snapshot(),
        "duplex_policy": DuplexInteractionPolicy().status(),
        "research_runtimes": research_runtime_status(),
        "semantics": {
            "read_only": True,
            "identity_authority": False,
            "memory_authority": False,
            "tool_authority": False,
            "automatic_training": False,
            "automatic_self_modification": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect MaryV2 cognitive research convergence readiness."
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    data = snapshot()
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print("MaryV2 research convergence:", data["version"])
        print("deliberation:", data["deliberation"]["version"])
        print("memory policy:", data["memory_action_policy"]["version"])
        print("trajectory telemetry:", data["trajectory_telemetry"]["version"])
        print("duplex policy:", data["duplex_policy"]["version"])
        ready = data["research_runtimes"]["ready"]
        print("optional research runtimes ready:", ", ".join(ready) if ready else "none")
        print("automatic self-modification: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
