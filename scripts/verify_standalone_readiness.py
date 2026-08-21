"""Verify source-level readiness for MaryV2 standalone desktop builds."""
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
    config_path = ROOT / "mary" / "core" / "config.py"
    spec_path = ROOT / "MaryV2.spec"
    windows_build_path = ROOT / "scripts" / "build_windows.ps1"
    macos_build_path = ROOT / "scripts" / "build_macos.sh"
    gitignore_path = ROOT / ".gitignore"
    env_example_path = ROOT / ".env.example"

    check("standalone build spec exists", spec_path.exists())
    check("Windows build script exists", windows_build_path.exists())
    check("macOS build script exists", macos_build_path.exists())
    check("source-control ignore policy exists", gitignore_path.exists())
    check("canonical environment template exists", env_example_path.exists())

    config = config_path.read_text(encoding="utf-8")
    spec = spec_path.read_text(encoding="utf-8")
    windows_build = windows_build_path.read_text(encoding="utf-8")
    macos_build = macos_build_path.read_text(encoding="utf-8")
    gitignore = gitignore_path.read_text(encoding="utf-8")

    check("Windows build script runs the offline release gate", "run_release_verification --offline" in windows_build)
    check("macOS build script runs the offline release gate", "run_release_verification --offline" in macos_build)
    check("Windows frontend is rebuilt before the release gate", windows_build.index("npm run build") < windows_build.index("run_release_verification --offline"))
    check("macOS frontend is rebuilt before the release gate", macos_build.index("npm run build") < macos_build.index("run_release_verification --offline"))
    check("Windows frontend is rebuilt before executable packaging", windows_build.index("npm run build") < windows_build.index("PyInstaller"))
    check("macOS frontend is rebuilt before executable packaging", macos_build.index("npm run build") < macos_build.index("PyInstaller"))
    check("frontend dependencies are rebuilt per host", "npm ci" in windows_build and "npm ci" in macos_build)
    check("frozen resources are separated from writable persistent data", "LOCALAPPDATA" in config and "Application Support" in config and "XDG_DATA_HOME" in config and "_MEIPASS" in config)
    check("portable and custom data locations are supported", "MARY_PORTABLE" in config and "MARY_DATA_DIR" in config)
    check("packaged app reads secrets outside bundled source", "MARY_ENV_FILE" in config and ".env" in config)
    check("desktop assets are included by the spec", '"desktop/dist"' in spec)
    check("macOS app bundle is defined by the spec", "BUNDLE(" in spec and "MaryV2.app" in spec)
    check("environment template is included by the spec", "ENV_EXAMPLE" in spec)
    check("personal data and .env are ignored by source control", "data/" in gitignore and ".env" in gitignore)
    print("=" * 72)
    print("STANDALONE SOURCE READINESS VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
