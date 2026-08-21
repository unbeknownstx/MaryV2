"""Read-only MaryV2 installation doctor.

Reports local prerequisites and configuration presence without printing secrets
or mutating Mary's persistent state. The project .env is loaded into this
doctor process only so provider configuration can be reported accurately.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def _present_env(name: str) -> str:
    return "configured" if bool(os.getenv(name, "").strip()) else "not configured"


def main() -> int:
    env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)

    checks: list[tuple[str, bool, str]] = []

    checks.append(("Python 3.10+", sys.version_info >= (3, 10), sys.version.split()[0]))
    for module in ("dotenv", "groq", "openai"):
        installed = importlib.util.find_spec(module) is not None
        checks.append(
            (
                f"Python module: {module}",
                installed,
                "installed" if installed else "missing",
            )
        )

    checks.append(
        ("Node.js", shutil.which("node") is not None, shutil.which("node") or "missing")
    )
    checks.append(("npm", shutil.which("npm") is not None, shutil.which("npm") or "missing"))
    checks.append(
        (
            "Desktop package lock",
            (ROOT / "desktop" / "package-lock.json").exists(),
            "desktop/package-lock.json",
        )
    )
    checks.append(
        (
            "Desktop build",
            (ROOT / "desktop" / "dist" / "index.html").exists(),
            "desktop/dist/index.html",
        )
    )
    checks.append(
        (
            "Environment template",
            (ROOT / ".env.example").exists(),
            ".env.example",
        )
    )
    checks.append(
        (
            "Local environment file",
            env_path.exists(),
            ".env present" if env_path.exists() else ".env missing",
        )
    )

    print("=" * 64)
    print("MARYV2 INSTALLATION DOCTOR")
    print("=" * 64)

    warnings = 0
    for label, ok, detail in checks:
        print(f"{'PASS' if ok else 'WARN':4}  {label}: {detail}")
        if not ok:
            warnings += 1

    print("-" * 64)
    print("Provider configuration (values are never displayed)")
    for name in (
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
    ):
        print(f"      {name}: {_present_env(name)}")
    print(f"      Ollama enabled: {os.getenv('MARY_OLLAMA_ENABLED', 'default/auto')}")
    print("-" * 64)
    print(
        "Doctor is read-only; it loaded configuration into this process only "
        "and did not modify Mary's persistent memory or .env."
    )
    print(f"Warnings: {warnings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
