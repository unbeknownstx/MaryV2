"""Verify MaryV2 12.7 desktop game-shell invariants without network access."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from mary.core.mary import Mary
from mary.desktop.dashboard import build_desktop_dashboard_state
from mary.desktop.integrations import DesktopIntegrationRegistry
from mary.launcher.update import UpdateManifest, UpdateService

ROOT = Path(__file__).resolve().parents[1]


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS  {label}")


def text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def main() -> int:
    print("=" * 72)
    print("MARYV2 12.7 DESKTOP GAME SHELL")
    print("=" * 72)

    required = (
        "desktop/index.html",
        "desktop/launcher.html",
        "desktop/src/main.js",
        "desktop/src/style.css",
        "desktop/src/launcher.js",
        "desktop/src/launcher.css",
        "desktop/vite.config.js",
        "desktop/design/MARY_UI_TARGET.png",
        "desktop/public/assets/mary-reference.jpeg",
        "desktop/public/assets/mary_icon.png",
        "MaryV2.spec",
        "MaryLauncher.spec",
        "scripts/run_desktop.py",
        "scripts/run_launcher.py",
        "scripts/build_windows.ps1",
        "scripts/build_macos.sh",
    )
    for relative in required:
        check(f"desktop surface exists: {relative}", (ROOT / relative).exists())

    bridge = text("mary/desktop/bridge.py")
    window = text("mary/desktop/window.py")
    dashboard = text("mary/desktop/dashboard.py")
    integrations = text("mary/desktop/integrations.py")
    main_js = text("desktop/src/main.js")
    index_html = text("desktop/index.html")
    launcher_js = text("desktop/src/launcher.js")
    launcher_html = text("desktop/launcher.html")
    vite = text("desktop/vite.config.js")
    package = text("desktop/package.json")
    updater = text("mary/launcher/update.py")

    check(
        "desktop bridge remains a view over one canonical MaryApplication",
        "MaryApplication" in bridge and "build_desktop_dashboard_state" in bridge,
    )
    check(
        "desktop exposes real dashboard state through WebChannel",
        "dashboardStateChanged" in bridge and "getDashboardState" in bridge,
    )
    check(
        "desktop retains voice and microphone integration",
        "DesktopVoiceEngine" in bridge
        and "DesktopMicrophoneRecorder" in bridge
        and "DesktopSpeechToText" in bridge,
    )
    check(
        "desktop custom game window supports native window controls",
        "FramelessWindowHint" in window
        and "startSystemMove" in window
        and "maximizeWindow" in bridge,
    )
    check(
        "dashboard is bounded presentation state rather than a second memory store",
        "build_desktop_dashboard_state" in dashboard
        and "_MAX_HIGHLIGHTS" in dashboard
        and "text_has_test_probe_marker" in dashboard,
    )
    check(
        "creative applications use a finite explicit integration registry",
        "_APP_SPECS" in integrations
        and "Unsupported desktop integration" in integrations
        and "shell=True" not in integrations,
    )

    nav_labels = (
        "Chat",
        "Memories",
        "Personality",
        "Studio",
        "Gallery",
        "Media",
        "Voice & Avatar",
        "Settings",
    )
    check(
        "game shell exposes all primary Mary workspaces",
        all(label in index_html or label in main_js for label in nav_labels),
    )
    check(
        "chat remains persistent beside workspace modes",
        "composer-deck" in index_html
        and "chat-scroll" in index_html
        and "workspace-overlay" in index_html,
    )
    check(
        "Unbeknownst Studio and creative-tool hooks are present",
        "Studio · Unbeknownst" in main_js
        and "launchCreativeApp" in main_js
        and "Continuity Pass" in main_js,
    )
    check(
        "media surface has local audio plus explicit YouTube navigation",
        "chooseMediaFile" in main_js
        and "youtube.com/results" in main_js
        and "musicAudio" in main_js,
    )
    check(
        "command palette is present",
        "command-palette" in index_html and "event.key.toLowerCase() === 'k'" in main_js,
    )
    check(
        "VRM surface remains integrated",
        "@pixiv/three-vrm" in main_js and "MaryCosma.vrm" in main_js,
    )
    check(
        "approved visual target is kept with the desktop source",
        (ROOT / "desktop/design/MARY_UI_TARGET.png").stat().st_size > 10_000,
    )

    check(
        "launcher provides PLAY and staged verified updates",
        "PLAY MARY" in launcher_html
        and "checkForUpdates" in launcher_js
        and "stageUpdate" in launcher_js,
    )
    check(
        "launcher updater keeps code staging separate from persistent data",
        'PathConfig().data.parent / "updates"' in updater
        and "sha256" in updater.lower(),
    )
    check(
        "Vite emits both the game shell and launcher",
        "index.html" in vite and "launcher.html" in vite,
    )
    check(
        "frontend dependencies are local and pinned in package metadata",
        "@pixiv/three-vrm" in package and '"three"' in package and '"vite"' in package,
    )
    check(
        "desktop source does not require CDN scripts",
        "cdn.jsdelivr" not in index_html.lower()
        and "unpkg.com" not in index_html.lower()
        and "cdnjs" not in index_html.lower(),
    )

    original_data = os.environ.get("MARY_DATA_DIR")
    try:
        with tempfile.TemporaryDirectory(prefix="maryv2_desktop_12_7_") as directory:
            data_root = Path(directory) / "data"
            os.environ["MARY_DATA_DIR"] = str(data_root)
            mary = Mary()
            state = build_desktop_dashboard_state(mary)
            check(
                "dashboard state builds from a real Mary instance",
                isinstance(state, dict)
                and isinstance(state.get("live"), dict)
                and isinstance(state.get("emotion"), dict)
                and isinstance(state.get("relationship"), dict),
            )
            check(
                "dashboard exposes no provider credential values",
                not any(
                    token in repr(state).upper()
                    for token in ("GROQ_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY")
                ),
            )

            registry = DesktopIntegrationRegistry()
            try:
                registry.build_command("powershell -enc evil")
            except ValueError:
                rejected = True
            else:
                rejected = False
            check("arbitrary desktop commands are rejected", rejected)

            service = UpdateService(
                manifest_url="https://example.invalid/mary.json",
                current_version="12.7.0",
            )
            check(
                "update staging is outside Mary's persistent data directory",
                service.updates_root == data_root.parent / "updates"
                and data_root not in service.updates_root.parents,
            )
            manifest = UpdateManifest.from_dict(
                {
                    "version": "12.8.0",
                    "package_url": "https://example.invalid/MaryV2-12.8.0.zip",
                    "sha256": "a" * 64,
                    "notes": "offline verifier fixture",
                }
            )
            check(
                "launcher recognizes a newer signed-manifest candidate",
                service.is_newer(manifest.version) and manifest.sha256 == "a" * 64,
            )
    finally:
        if original_data is None:
            os.environ.pop("MARY_DATA_DIR", None)
        else:
            os.environ["MARY_DATA_DIR"] = original_data

    print("=" * 72)
    print("MARYV2 12.7 DESKTOP GAME SHELL VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
