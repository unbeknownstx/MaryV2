"""Verify source-level readiness for a Windows MaryV2 standalone build."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS  {label}")


def main() -> int:
    print("=" * 72)
    print("MARYV2 STANDALONE READINESS")
    print("=" * 72)
    config = (ROOT / "mary" / "core" / "config.py").read_text(encoding="utf-8")
    spec = (ROOT / "MaryV2.spec").read_text(encoding="utf-8")
    build = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    check("Windows build spec exists", (ROOT / "MaryV2.spec").exists())
    check("Windows build script runs the offline release gate", "run_release_verification --offline" in build)
    check("frontend is rebuilt before the release gate", build.index("npm run build") < build.index("run_release_verification --offline"))
    check("frontend is rebuilt before executable packaging", build.index("npm run build") < build.index("PyInstaller"))
    check("frozen resources are separated from writable persistent data", "LOCALAPPDATA" in config and "_MEIPASS" in config)
    check("portable and custom data locations are supported", "MARY_PORTABLE" in config and "MARY_DATA_DIR" in config)
    check("packaged app reads secrets outside bundled source", "MARY_ENV_FILE" in config and ".env" in config)
    check("desktop assets are included by the spec", '"desktop/dist"' in spec)
    check("personal data and .env are ignored by source control", "data/" in gitignore and ".env" in gitignore)
    print("=" * 72)
    print("STANDALONE SOURCE READINESS VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
