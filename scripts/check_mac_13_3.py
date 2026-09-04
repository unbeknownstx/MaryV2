"""Offline Mac readiness report for MaryV2 13.3.

This checker never prints tokens, calls providers, changes permissions, or
connects to Mary Core.  It tells the creator which pieces are locally present
before launching the Mac surface/capability node.
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _present(command: str) -> bool:
    return shutil.which(command) is not None


def main() -> int:
    is_mac = platform.system() == "Darwin"
    checks = {
        "macos": is_mac,
        "python_3_11_plus": sys.version_info >= (3, 11),
        "repo_core": (ROOT / "mary" / "core" / "service.py").exists(),
        "desktop_surface": (ROOT / "mary" / "desktop").is_dir(),
        "native_ios_project": (ROOT / "mobile_native" / "MaryMobile.xcodeproj").exists(),
        "xcodebuild": _present("xcodebuild") if is_mac else False,
        "node": _present("node"),
        "llama_cpp": _present("llama-cli") or _present("llama-server"),
        "core_url_configured": bool(str(os.getenv("MARY_CORE_URL") or "").strip()),
        "core_token_configured": bool(str(os.getenv("MARY_CORE_TOKEN") or "").strip()),
    }
    print("MaryV2 13.3 Mac readiness (offline)")
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'INFO'}  {name}")
    print("\nSafety: no credentials were printed and no network call was made.")
    required = ("python_3_11_plus", "repo_core", "desktop_surface")
    return 0 if all(checks[name] for name in required) else 1


if __name__ == "__main__":
    raise SystemExit(main())
