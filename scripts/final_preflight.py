"""Read-only final handoff/build preflight for MaryV2.

This command is intentionally safe to run before copying the project or before a
standalone build. It reports configuration presence, host prerequisites, private
state integrity, and optional local Ollama readiness without printing secrets or
modifying Mary's state.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from mary import __release__, __version__
from mary.core.config import Config
from scripts.verify_state_integrity import inspect_state

ROOT = Path(__file__).resolve().parents[1]


def _configured(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _truthy(value: str | None, *, default: bool = True) -> bool:
    if value is None or not str(value).strip():
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}



def _node_runtime() -> tuple[bool, str]:
    executable = shutil.which("node")
    if not executable:
        return False, "missing"
    try:
        value = subprocess.check_output([executable, "--version"], text=True, timeout=3).strip().lstrip("v")
        parts = value.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
    except (OSError, subprocess.SubprocessError, ValueError):
        return False, "version unreadable"
    compatible = (major == 20 and minor >= 19) or (major >= 22 and (major > 22 or minor >= 12))
    return compatible, value

def _ollama_status(
    base_url: str,
    expected_model: str,
    *,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    url = str(base_url or "http://localhost:11434").rstrip("/") + "/api/tags"
    try:
        request = Request(url, headers={"User-Agent": "MaryV2-Preflight/1"})
        with opener(request, timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (OSError, URLError, ValueError, json.JSONDecodeError) as exc:
        return {"reachable": False, "model_present": False, "models": 0, "reason": exc.__class__.__name__}

    models = payload.get("models", []) if isinstance(payload, dict) else []
    names: set[str] = set()
    for item in models if isinstance(models, list) else []:
        if not isinstance(item, dict):
            continue
        for key in ("name", "model"):
            value = str(item.get(key, "")).strip()
            if value:
                names.add(value)

    target = str(expected_model or "").strip()
    present = not target or target in names or any(name.split(":", 1)[0] == target for name in names)
    return {"reachable": True, "model_present": present, "models": len(names), "reason": "ok"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only MaryV2 final handoff/build preflight")
    parser.add_argument("--build-ready", action="store_true", help="Require desktop build prerequisites/output")
    parser.add_argument("--runtime-ready", action="store_true", help="Require at least one configured/reachable normal LLM route")
    parser.add_argument("--strict-local", action="store_true", help="Require local Ollama and the configured model")
    parser.add_argument("--data-dir", type=Path, default=None, help="State directory to integrity-check instead of the configured default")
    args = parser.parse_args(argv)

    config = Config.from_environment()
    hard_failures = 0
    warnings = 0

    def report(label: str, ok: bool, detail: str, *, required: bool = False) -> None:
        nonlocal hard_failures, warnings
        if ok:
            status = "PASS"
        elif required:
            status = "FAIL"
            hard_failures += 1
        else:
            status = "WARN"
            warnings += 1
        print(f"{status:4}  {label}: {detail}")

    print("=" * 72)
    print("MARYV2 FINAL HANDOFF / BUILD PREFLIGHT")
    print(f"Version: {__version__} | Core release: {__release__}")
    print("=" * 72)

    report("Python 3.10+", sys.version_info >= (3, 10), sys.version.split()[0], required=True)
    report("64-bit Python", sys.maxsize > 2**32, "yes" if sys.maxsize > 2**32 else "no", required=args.build_ready)

    required_files = (
        "requirements.txt",
        "requirements-desktop.txt",
        "requirements-build.txt",
        "MaryV2.spec",
        "MaryLauncher.spec",
        ".env.example",
        "desktop/package-lock.json",
        "scripts/build_windows.ps1",
        "scripts/build_macos.sh",
    )
    for relative in required_files:
        report(f"Source file {relative}", (ROOT / relative).exists(), relative, required=True)

    for module in ("dotenv", "groq", "openai"):
        present = importlib.util.find_spec(module) is not None
        report(f"Python module {module}", present, "installed" if present else "missing", required=args.build_ready)

    pyside = importlib.util.find_spec("PySide6") is not None
    report("PySide6 desktop runtime", pyside, "installed" if pyside else "missing", required=args.build_ready)

    node_ok, node_version = _node_runtime()
    npm = shutil.which("npm")
    report("Node.js for Vite 8", node_ok, node_version, required=args.build_ready)
    report("npm", bool(npm), npm or "missing", required=args.build_ready)

    desktop_dist = ROOT / "desktop" / "dist" / "index.html"
    launcher_dist = ROOT / "desktop" / "dist" / "launcher.html"
    report("Desktop frontend build", desktop_dist.exists(), "desktop/dist/index.html" if desktop_dist.exists() else "not built yet", required=args.build_ready)
    report("Launcher frontend build", launcher_dist.exists(), "desktop/dist/launcher.html" if launcher_dist.exists() else "not built yet", required=args.build_ready)

    env_path = ROOT / ".env"
    report("Local .env", env_path.exists(), ".env present" if env_path.exists() else "missing; environment/secret store may still provide configuration")

    providers = {
        "Groq": _configured("GROQ_API_KEY"),
        "Gemini": _configured("GEMINI_API_KEY") or _configured("GOOGLE_API_KEY"),
        "OpenRouter": _configured("OPENROUTER_API_KEY"),
        "OpenAI expert": _configured("OPENAI_API_KEY"),
    }
    print("-" * 72)
    print("Provider configuration (values are never displayed)")
    for name, configured in providers.items():
        print(f"{'PASS' if configured else 'INFO':4}  {name}: {'configured' if configured else 'not configured'}")

    ollama_enabled = _truthy(os.getenv("MARY_OLLAMA_ENABLED"), default=True)
    ollama_model = os.getenv("MARY_OLLAMA_MODEL", "qwen3:4b-instruct").strip() or "qwen3:4b-instruct"
    ollama_base = os.getenv("MARY_OLLAMA_BASE_URL", "http://localhost:11434").strip() or "http://localhost:11434"
    ollama = _ollama_status(ollama_base, ollama_model) if ollama_enabled else {
        "reachable": False,
        "model_present": False,
        "models": 0,
        "reason": "disabled",
    }
    report(
        "Ollama service",
        bool(ollama["reachable"]),
        f"reachable; {ollama['models']} model(s) visible" if ollama["reachable"] else str(ollama["reason"]),
        required=args.strict_local,
    )
    if ollama["reachable"]:
        report(
            "Configured Ollama model",
            bool(ollama["model_present"]),
            f"{ollama_model} {'present' if ollama['model_present'] else 'missing'}",
            required=args.strict_local,
        )

    any_route = any(providers[name] for name in ("Groq", "Gemini", "OpenRouter")) or bool(ollama["reachable"] and ollama["model_present"])
    report("At least one normal LLM route", any_route, "available/configured" if any_route else "none detected", required=args.runtime_ready)

    print("-" * 72)
    state = inspect_state(args.data_dir or config.paths.data)
    report(
        "Persistent state JSON integrity",
        bool(state["healthy"]),
        (
            f"{state['valid_files']} current JSON file(s) valid"
            if state["exists"]
            else "no data directory yet"
        ),
        required=True,
    )
    print(f"INFO  Data root: {state['data_root']}")
    print("No stored values or secret values were displayed or modified.")
    print("=" * 72)
    print(f"Hard failures: {hard_failures} | Warnings: {warnings}")
    return 1 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
