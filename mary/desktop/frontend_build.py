"""Keep the generated Mary Desktop frontend synchronized with source.

The Qt Desktop and Launcher serve ``desktop/dist``. Source checkouts intentionally
do not commit generated Vite output, so a pulled GUI change must rebuild the
bundle before Qt starts or the user can silently see an old interface.

Mary's personal VRM/VRoid assets are intentionally gitignored. Vite used to
empty ``desktop/dist`` before every build, which could delete a perfectly good
local ``dist/models/MaryCosma.vrm`` and make a UI update look like an avatar
renderer regression. This module therefore preserves/restores local avatar
assets across a generated frontend rebuild and can stage an explicitly
configured VRM from ``MARY_DESKTOP_VRM_PATH``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


_SOURCE_FILES = (
    "index.html",
    "launcher.html",
    "vite.config.js",
    "package.json",
    "package-lock.json",
)

_AVATAR_FILENAMES = (
    "MaryCosma.vrm",
    "maryvrm1.vroid",
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


def _configured_vrm_path(root: Path) -> Path | None:
    """Resolve an explicitly configured or conventional local Mary VRM.

    No broad filesystem crawl is performed. Personal model assets stay outside
    source control and Mary only checks bounded, creator-owned locations.
    """

    explicit = os.getenv("MARY_DESKTOP_VRM_PATH", "").strip()
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())

    model_root = os.getenv("MARY_MODEL_DIR", "").strip()
    if model_root:
        base = Path(model_root).expanduser()
        candidates.extend((base / "MaryCosma.vrm", base / "avatar" / "MaryCosma.vrm"))

    candidates.extend(
        (
            root / "desktop" / "public" / "models" / "MaryCosma.vrm",
            root / "desktop" / "dist" / "models" / "MaryCosma.vrm",
            root / "models" / "MaryCosma.vrm",
            root / "assets" / "models" / "MaryCosma.vrm",
        )
    )

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file() and resolved.stat().st_size > 1024:
            return resolved
    return None


def _preserve_local_avatar_assets(root: Path, staging_root: Path) -> list[Path]:
    """Copy gitignored avatar assets somewhere Vite cannot erase."""

    desktop = root / "desktop"
    sources: list[Path] = []
    for folder in (desktop / "public" / "models", desktop / "dist" / "models"):
        for filename in _AVATAR_FILENAMES:
            candidate = folder / filename
            if candidate.is_file() and candidate.stat().st_size > 1024:
                sources.append(candidate)

    configured = _configured_vrm_path(root)
    if configured is not None and configured not in sources:
        sources.append(configured)

    preserved: list[Path] = []
    staging_root.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    for source in sources:
        key = source.name.lower()
        if key in seen:
            continue
        seen.add(key)
        target = staging_root / source.name
        shutil.copy2(source, target)
        preserved.append(target)
    return preserved


def _restore_local_avatar_assets(root: Path, preserved: list[Path]) -> None:
    """Restore personal avatar assets into both source-public and built output.

    Keeping a copy under the gitignored ``desktop/public/models`` directory
    means the *next* Vite build naturally carries it forward too.
    """

    if not preserved:
        return
    desktop = root / "desktop"
    destinations = (desktop / "public" / "models", desktop / "dist" / "models")
    for folder in destinations:
        folder.mkdir(parents=True, exist_ok=True)
        for source in preserved:
            target = folder / source.name
            if target.exists() and target.stat().st_size == source.stat().st_size:
                continue
            shutil.copy2(source, target)


def avatar_asset_status(root: Path) -> dict[str, object]:
    """Return path-free presentation readiness for diagnostics/UI."""

    vrm = _configured_vrm_path(root)
    public = root / "desktop" / "public" / "models" / "MaryCosma.vrm"
    built = root / "desktop" / "dist" / "models" / "MaryCosma.vrm"
    return {
        "configured": vrm is not None,
        "public_ready": public.is_file() and public.stat().st_size > 1024,
        "built_ready": built.is_file() and built.stat().st_size > 1024,
        "filename": "MaryCosma.vrm",
        "source": (
            "public_models"
            if public.is_file()
            else ("built_models" if built.is_file() else ("configured_path" if vrm else "missing"))
        ),
    }


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

    # Personal avatar assets are deliberately not in Git. Preserve the current
    # host copy before Vite touches generated output, then restore it after a
    # successful or failed build so an interface update cannot erase Mary's body.
    with tempfile.TemporaryDirectory(prefix="maryv2-avatar-build-") as temp_dir:
        preserved = _preserve_local_avatar_assets(root, Path(temp_dir))
        try:
            print("MaryV2: checking Desktop frontend...", flush=True)
            subprocess.run([npm, "run", "check"], cwd=desktop, check=True)
            print("MaryV2: rebuilding Desktop frontend...", flush=True)
            subprocess.run([npm, "run", "build"], cwd=desktop, check=True)
        finally:
            _restore_local_avatar_assets(root, preserved)

    if not built_page.is_file():
        raise RuntimeError(f"Desktop build completed without expected output: {built_page}")
    return built_page
