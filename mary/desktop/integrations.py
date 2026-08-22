"""Explicit desktop integrations used by MaryV2's creative-workstation UI.

Only known, locally configured applications are launchable.  The frontend never
passes an arbitrary shell command into Python.  This keeps the convenience of
"Open in Photoshop" / "Open in Blender" without turning the Qt bridge into an
unrestricted command-execution surface.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterable


@dataclass(frozen=True)
class DesktopAppIntegration:
    key: str
    label: str
    environment_variable: str
    executable: Path | None

    @property
    def available(self) -> bool:
        return bool(self.executable and self.executable.exists())

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "available": self.available,
            # Path is intentionally exposed only to this private local desktop
            # UI.  No credentials or file contents are included.
            "path": str(self.executable) if self.executable else None,
            "environment_variable": self.environment_variable,
        }


_APP_SPECS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "photoshop",
        "Adobe Photoshop",
        "MARY_PHOTOSHOP_PATH",
        (
            r"Adobe/Adobe Photoshop */Photoshop.exe",
            r"Adobe/Adobe Photoshop*/Photoshop.exe",
        ),
    ),
    (
        "clip_studio",
        "Clip Studio Paint",
        "MARY_CLIP_STUDIO_PATH",
        (
            r"CELSYS/CLIP STUDIO 1.5/CLIP STUDIO PAINT/CLIPStudioPaint.exe",
            r"CELSYS/CLIP STUDIO/CLIP STUDIO PAINT/CLIPStudioPaint.exe",
        ),
    ),
    (
        "krita",
        "Krita",
        "MARY_KRITA_PATH",
        (r"Krita (x64)/bin/krita.exe", r"Krita/bin/krita.exe"),
    ),
    (
        "blender",
        "Blender",
        "MARY_BLENDER_PATH",
        (r"Blender Foundation/Blender */blender.exe",),
    ),
    (
        "davinci",
        "DaVinci Resolve",
        "MARY_DAVINCI_PATH",
        (r"Blackmagic Design/DaVinci Resolve/Resolve.exe",),
    ),
    (
        "audacity",
        "Audacity",
        "MARY_AUDACITY_PATH",
        (r"Audacity/Audacity.exe",),
    ),
)


def _program_roots() -> list[Path]:
    values = [
        os.getenv("ProgramFiles", ""),
        os.getenv("ProgramFiles(x86)", ""),
        os.getenv("LOCALAPPDATA", ""),
    ]
    roots: list[Path] = []
    for value in values:
        if not value:
            continue
        path = Path(value).expanduser()
        if path not in roots:
            roots.append(path)
    return roots


def _first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        try:
            if path.exists() and path.is_file():
                return path.resolve()
        except OSError:
            continue
    return None


def _discover_windows(patterns: tuple[str, ...]) -> Path | None:
    if sys.platform != "win32":
        return None
    for root in _program_roots():
        for pattern in patterns:
            try:
                matches = sorted(root.glob(pattern), reverse=True)
            except OSError:
                continue
            found = _first_existing(matches)
            if found is not None:
                return found
    return None


def _discover_path_command(key: str) -> Path | None:
    executable_names = {
        "krita": ("krita", "krita.exe"),
        "blender": ("blender", "blender.exe"),
        "audacity": ("audacity", "audacity.exe"),
    }.get(key, ())
    for name in executable_names:
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    return None


class DesktopIntegrationRegistry:
    """Resolve and launch a finite set of explicitly supported creative apps."""

    def __init__(self) -> None:
        self._apps: dict[str, DesktopAppIntegration] = {}
        self.refresh()

    def refresh(self) -> None:
        discovered: dict[str, DesktopAppIntegration] = {}
        for key, label, env_name, patterns in _APP_SPECS:
            explicit = os.getenv(env_name, "").strip()
            executable = Path(explicit).expanduser().resolve() if explicit else None
            if executable is None or not executable.exists():
                executable = _discover_windows(patterns) or _discover_path_command(key)
            discovered[key] = DesktopAppIntegration(
                key=key,
                label=label,
                environment_variable=env_name,
                executable=executable,
            )
        self._apps = discovered

    def status(self) -> list[dict[str, object]]:
        return [self._apps[key].to_dict() for key in sorted(self._apps)]

    def get(self, key: str) -> DesktopAppIntegration | None:
        return self._apps.get(str(key or "").strip().lower())

    def build_command(self, key: str, file_path: str | Path | None = None) -> list[str]:
        app = self.get(key)
        if app is None:
            raise ValueError(f"Unsupported desktop integration: {key}")
        if not app.available or app.executable is None:
            raise FileNotFoundError(
                f"{app.label} is not configured. Set {app.environment_variable} "
                "to the executable path in Mary's private .env."
            )

        command = [str(app.executable)]
        if file_path is not None and str(file_path).strip():
            target = Path(file_path).expanduser().resolve()
            if not target.exists():
                raise FileNotFoundError(f"Creative file does not exist: {target}")
            command.append(str(target))
        return command

    def launch(self, key: str, file_path: str | Path | None = None) -> None:
        command = self.build_command(key, file_path=file_path)
        subprocess.Popen(  # noqa: S603 - finite explicit executable registry
            command,
            close_fds=(sys.platform != "win32"),
        )
