"""Keep the generated Mary Desktop frontend synchronized with source.

The Qt Desktop and Launcher serve desktop/dist. Source checkouts intentionally
do not commit generated Vite output, so a pulled GUI change must rebuild the
bundle before Qt starts or the user can silently see an old interface.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


_SOURCE_FILES = (
    "index.html",
    "launcher.html",
    "vite.config.js",
    "package.json",
    "package-lock.json",
)


def _newest_source_mtime(desktop: Path) -> float:
    newest = 0.0
    for folder_name in ("src", "public"):
        folder = desktop / folder_name
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if path.is_file():
                newest = max(newest, path.stat().st_mtime)

    for name in _SOURCE_FILES:
        path = desktop / name
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
    return newest


def frontend_needs_build(root: Path, *, page: str = "index.html") -> bool:
    desktop = root / "desktop"
    built_page = desktop / "dist" / page
    if not built_page.is_file():
        return True
    newest_source = _newest_source_mtime(desktop)
    return bool(newest_source and newest_source > built_page.stat().st_mtime)


def ensure_desktop_frontend(root: Path, *, page: str = "index.html") -> Path:
    """Return a current generated page, rebuilding Vite output when stale."""

    desktop = root / "desktop"
    built_page = desktop / "dist" / page
    if not frontend_needs_build(root, page=page):
        return built_page

    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError(
            "Desktop source is newer than desktop/dist but npm is unavailable. "
            "Install Node/npm or run the platform setup script."
        )

    vite_name = "vite.cmd" if Path(npm).name.lower().endswith(".cmd") else "vite"
    vite = desktop / "node_modules" / ".bin" / vite_name
    if not vite.exists():
        print("MaryV2: installing Desktop frontend dependencies...", flush=True)
        subprocess.run([npm, "ci"], cwd=desktop, check=True)

    print("MaryV2: checking Desktop frontend...", flush=True)
    subprocess.run([npm, "run", "check"], cwd=desktop, check=True)
    print("MaryV2: rebuilding Desktop frontend...", flush=True)
    subprocess.run([npm, "run", "build"], cwd=desktop, check=True)

    if not built_page.is_file():
        raise RuntimeError(f"Desktop build completed without expected output: {built_page}")
    return built_page
