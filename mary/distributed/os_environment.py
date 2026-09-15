"""Read-only operating-environment projection for Mary capability hosts.

MaryOS uses this module to understand the host it is running on without turning
host discovery into execution authority. Detection uses Python/OS metadata only:
no child-process execution, shell commands, package mutation, service mutation, or
privilege escalation occur here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import platform
import shutil
from typing import Any


def _clean(value: str, limit: int = 160) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().upper()
            if key not in {"ID", "NAME", "VERSION_ID", "PRETTY_NAME"}:
                continue
            values[key] = _clean(value.strip().strip('"').strip("'"))
    except OSError:
        return {}
    return values


@dataclass(frozen=True)
class MaryOSEnvironmentProfile:
    platform: str
    distro_id: str
    distro_name: str
    distro_version: str
    init_system: str
    systemd_available: bool
    desktop_session: str
    display_protocol: str
    hyprland_session: bool
    quickshell_available: bool
    package_managers: tuple[str, ...]
    omarchy_detected: bool

    @classmethod
    def detect(cls, *, home: Path | None = None) -> "MaryOSEnvironmentProfile":
        system = platform.system().lower()
        release = _os_release() if system == "linux" else {}
        systemctl = bool(shutil.which("systemctl"))
        systemd = bool(system == "linux" and (Path("/run/systemd/system").exists() or systemctl))
        desktop = _clean(
            os.getenv("XDG_CURRENT_DESKTOP", "")
            or os.getenv("DESKTOP_SESSION", "")
            or ("headless" if system == "linux" else "")
        )
        if os.getenv("WAYLAND_DISPLAY", "").strip():
            display_protocol = "wayland"
        elif os.getenv("DISPLAY", "").strip():
            display_protocol = "x11"
        else:
            display_protocol = "headless"

        hyprland = bool(
            "hyprland" in desktop.casefold()
            or os.getenv("HYPRLAND_INSTANCE_SIGNATURE", "").strip()
        )
        managers = tuple(
            name for name in ("pacman", "apt", "dnf", "zypper", "apk", "brew")
            if shutil.which(name)
        )
        host_home = (home or Path.home()).expanduser()
        omarchy = bool(
            shutil.which("omarchy")
            or (host_home / ".local" / "share" / "omarchy").exists()
            or (host_home / ".config" / "omarchy").exists()
        )
        return cls(
            platform=system or "unknown",
            distro_id=_clean(release.get("ID", "unknown")).casefold() or "unknown",
            distro_name=_clean(release.get("PRETTY_NAME") or release.get("NAME") or "unknown"),
            distro_version=_clean(release.get("VERSION_ID", "")),
            init_system="systemd" if systemd else "unknown",
            systemd_available=systemd,
            desktop_session=desktop or "unknown",
            display_protocol=display_protocol,
            hyprland_session=hyprland,
            quickshell_available=bool(shutil.which("quickshell")),
            package_managers=managers,
            omarchy_detected=omarchy,
        )

    @property
    def maryos_candidate(self) -> bool:
        return bool(self.platform == "linux" and self.systemd_available)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["package_managers"] = list(self.package_managers)
        payload["maryos_candidate"] = self.maryos_candidate
        payload["authority"] = "diagnostic_projection_only"
        payload["execution_authority"] = False
        return payload
