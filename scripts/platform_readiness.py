"""Read-only cross-platform MaryV2 host readiness report.

This module never starts services, executes shell commands, or prints secret
values. It reports repository contracts, optional host packages/executables,
configuration presence and 13.14 specialist readiness so a Mac or PC can be
prepared without making any optional dependency a Mary Core startup requirement.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_REPO_PATHS = (
    "MARY_ROOT.md",
    "docs/architecture/SYSTEM_REGISTRY.md",
    "requirements.txt",
    "requirements-desktop.txt",
    "requirements-host-extras.txt",
    "requirements-node-mcp.txt",
    "requirements-local-voice.txt",
    "requirements-realtime-local.txt",
    "requirements-streaming.txt",
    "mary/distributed/mcp_fabric.py",
    "scripts/run_capability_node.py",
    "ios/MaryV2iOS/project.yml",
)

OPTIONAL_REPO_PATHS = (
    "requirements-home-node.txt",
    "requirements-streaming-audio.txt",
    "docs/architecture/HOME_COMPUTE_FABRIC_13_11.md",
    "docs/architecture/HOME_SENSOR_WORKERS_13_12.md",
    "docs/architecture/STREAM_SENSES_13_13.md",
    "docs/architecture/CHARACTER_INTELLIGENCE_LEARNING_13_14.md",
)

OPTIONAL_MODULES = {
    "mcp": "bounded MCP client",
    "faster_whisper": "local Whisper STT",
    "onnxruntime": "local ONNX runtime",
    "sherpa_onnx": "local realtime speech runtime",
    "websockets": "stream/presence transport",
    "sounddevice": "optional public creator microphone capture",
}

OPTIONAL_EXECUTABLES = {
    "git": ("git",),
    "ollama": ("ollama",),
    "llama.cpp server": ("llama-server", "llama-server.exe"),
    "Whisper.cpp": ("whisper-cli", "whisper-cli.exe"),
    "Piper TTS": ("piper", "piper.exe"),
    "Node.js": ("node",),
    "npm": ("npm", "npm.cmd"),
    "XcodeGen": ("xcodegen",),
}

CONFIG_PRESENCE = (
    "MARY_CORE_URL",
    "MARY_MCP_OPENDESIGN_URL",
    "MARY_MCP_SCRAPLING_URL",
    "MARY_MCP_LANGFLOW_URL",
    "MARY_FLUID_AUDIO_ENDPOINT",
    "MARY_QWEN_ASR_ENDPOINT",
    "MARY_LLAMA_CPP_VLM_URL",
    "MARY_OMNIPARSER_ENDPOINT",
    "MARY_CHATTERBOX_ENDPOINT",
    "ELEVENLABS_API_KEY",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
)


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError, AttributeError):
        module = sys.modules.get(name)
        return module is not None and getattr(module, "__file__", None) is not None


def _which_any(names: tuple[str, ...]) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def collect_readiness() -> dict[str, Any]:
    repo_paths = {
        relative: (ROOT / relative).exists() for relative in REQUIRED_REPO_PATHS
    }
    optional_repo_paths = {
        relative: (ROOT / relative).exists() for relative in OPTIONAL_REPO_PATHS
    }
    modules = {
        name: {"purpose": purpose, "available": _module_available(name)}
        for name, purpose in OPTIONAL_MODULES.items()
    }
    executables = {
        label: {"available": bool(found := _which_any(names)), "path": found}
        for label, names in OPTIONAL_EXECUTABLES.items()
    }
    configured = {
        name: bool(os.getenv(name, "").strip()) for name in CONFIG_PRESENCE
    }

    try:
        from mary.distributed.specialist_catalog import specialist_status
        specialists = specialist_status()
    except Exception:
        specialists = {
            "version": "13.14",
            "backends": [],
            "ready": [],
            "semantics": {
                "discovery_only": True,
                "core_startup_dependency": False,
                "external_identity_authority": False,
                "external_memory_authority": False,
                "arbitrary_shell": False,
            },
        }

    platform_name = platform.system().lower()
    surface = {
        "macos": platform_name == "darwin",
        "windows": platform_name == "windows",
        "linux": platform_name == "linux",
        "native_iphone_project": (ROOT / "ios" / "MaryV2iOS" / "project.yml").exists(),
        "desktop_project": (ROOT / "desktop" / "package.json").exists(),
        "mobile_web_project": (ROOT / "mobile" / "web").exists(),
    }

    return {
        "schema": "maryv2.platform_readiness.v1",
        "mary_version": "13.5-readiness",
        "python": {
            "version": platform.python_version(),
            "supported": sys.version_info >= (3, 10),
        },
        "platform": platform.platform(),
        "surface": surface,
        "repo_contracts": repo_paths,
        "optional_repo_contracts": optional_repo_paths,
        "optional_modules": modules,
        "optional_executables": executables,
        "configuration": configured,
        "specialist_backends": specialists,
        "core_startup_requires_optional_host_extras": False,
        "shell_execution_surface_added": False,
    }


def _strict_failures(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not report["python"]["supported"]:
        failures.append("Python 3.10+ is required")
    for path, present in report["repo_contracts"].items():
        if not present:
            failures.append(f"missing repository contract: {path}")
    return failures


def _print_human(report: dict[str, Any]) -> None:
    print("=" * 72)
    print("MARYV2 PLATFORM READINESS")
    print("=" * 72)
    print(f"Platform: {report['platform']}")
    print(f"Python:   {report['python']['version']} ({'PASS' if report['python']['supported'] else 'FAIL'})")

    print("\nRepository contracts")
    for path, present in report["repo_contracts"].items():
        print(f"  {'PASS' if present else 'FAIL'}  {path}")

    print("\nOptional architecture/runtime contracts")
    for path, present in report["optional_repo_contracts"].items():
        print(f"  {'READY' if present else 'OPTIONAL'}  {path}")

    print("\nOptional host packages")
    for name, status in report["optional_modules"].items():
        print(f"  {'READY' if status['available'] else 'OPTIONAL'}  {name}: {status['purpose']}")

    print("\nOptional host executables")
    for label, status in report["optional_executables"].items():
        detail = status["path"] if status["available"] else "not detected"
        print(f"  {'READY' if status['available'] else 'OPTIONAL'}  {label}: {detail}")

    print("\nConfiguration presence (values are never displayed)")
    for name, configured in report["configuration"].items():
        print(f"  {'SET' if configured else 'UNSET'}  {name}")

    print("\nResearch-derived specialist backends")
    for item in report.get("specialist_backends", {}).get("backends", []):
        print(f"  {'READY' if item['ready'] else 'OPTIONAL'}  {item['backend_id']}: {item['role']} ({item['state']})")

    print("\nOptional host extras/specialists are never a Mary Core startup dependency.")
    print("No shell/exec capability is introduced by this readiness layer.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail only on required repository/Python contracts; optional tools stay optional",
    )
    args = parser.parse_args(argv)

    report = collect_readiness()
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)

    failures = _strict_failures(report) if args.strict else []
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
