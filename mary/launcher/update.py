"""Safe staged-update support for the MaryV2 launcher.

The launcher never overwrites Mary's persistent ``data`` directory.  Remote
updates are optional and disabled until MARY_UPDATE_MANIFEST_URL is configured.
Downloaded packages are SHA-256 verified and staged under Mary's local app-data
area for an explicit apply/rollback step in a later launcher phase.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from mary.core.config import PathConfig
from mary.runtime.release import APP_VERSION, RELEASE_CHANNEL


@dataclass(frozen=True)
class UpdateManifest:
    version: str
    package_url: str
    sha256: str
    notes: str = ""
    channel: str = RELEASE_CHANNEL

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UpdateManifest":
        version = str(payload.get("version") or "").strip()
        package_url = str(payload.get("package_url") or payload.get("download") or "").strip()
        sha256 = str(payload.get("sha256") or "").strip().lower()
        notes = str(payload.get("notes") or "").strip()
        channel = str(payload.get("channel") or RELEASE_CHANNEL).strip()
        if not version:
            raise ValueError("Update manifest is missing version.")
        parsed = urlparse(package_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("Update package_url must be http(s).")
        if len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256):
            raise ValueError("Update manifest sha256 must be a 64-character hexadecimal digest.")
        return cls(
            version=version,
            package_url=package_url,
            sha256=sha256,
            notes=notes,
            channel=channel,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "version": self.version,
            "package_url": self.package_url,
            "sha256": self.sha256,
            "notes": self.notes,
            "channel": self.channel,
        }


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for segment in str(value).strip().lstrip("v").split("."):
        digits = "".join(ch for ch in segment if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts or [0])


class UpdateService:
    def __init__(
        self,
        *,
        manifest_url: str | None = None,
        current_version: str = APP_VERSION,
        timeout: float = 12.0,
    ) -> None:
        self.manifest_url = (
            str(manifest_url).strip()
            if manifest_url is not None
            else os.getenv("MARY_UPDATE_MANIFEST_URL", "").strip()
        )
        self.current_version = str(current_version)
        self.timeout = float(timeout)
        self.last_manifest: UpdateManifest | None = None
        self.last_error: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.manifest_url)

    @property
    def updates_root(self) -> Path:
        # PathConfig.data is the canonical writable state root. Updates are a
        # sibling, never a child, so code packages cannot collide with memories.
        return PathConfig().data.parent / "updates"

    def status(self) -> dict[str, Any]:
        manifest = self.last_manifest
        return {
            "enabled": self.enabled,
            "current_version": self.current_version,
            "manifest_url_configured": bool(self.manifest_url),
            "latest_version": manifest.version if manifest else None,
            "update_available": bool(manifest and self.is_newer(manifest.version)),
            "notes": manifest.notes if manifest else "",
            "last_error": self.last_error,
            "staging_root": str(self.updates_root),
            "policy": "download+verify+stage; persistent Mary data is never overwritten",
        }

    def is_newer(self, version: str) -> bool:
        return _version_tuple(version) > _version_tuple(self.current_version)

    def check(self) -> UpdateManifest | None:
        self.last_error = None
        if not self.enabled:
            return None
        parsed = urlparse(self.manifest_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("MARY_UPDATE_MANIFEST_URL must be an http(s) URL.")
        try:
            request = Request(
                self.manifest_url,
                headers={"User-Agent": f"MaryV2-Launcher/{self.current_version}"},
            )
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - validated scheme
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Update manifest must be a JSON object.")
            manifest = UpdateManifest.from_dict(payload)
            self.last_manifest = manifest
            return manifest
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise

    def download_and_stage(self, manifest: UpdateManifest | None = None) -> Path:
        manifest = manifest or self.last_manifest
        if manifest is None:
            raise RuntimeError("No checked update manifest is available.")
        if not self.is_newer(manifest.version):
            raise RuntimeError(f"Version {manifest.version} is not newer than {self.current_version}.")

        self.updates_root.mkdir(parents=True, exist_ok=True)
        target = self.updates_root / f"MaryV2-{manifest.version}.zip"

        request = Request(
            manifest.package_url,
            headers={"User-Agent": f"MaryV2-Launcher/{self.current_version}"},
        )
        parsed = urlparse(manifest.package_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("Update package URL must be http(s).")

        digest = hashlib.sha256()
        with tempfile.NamedTemporaryFile(
            prefix="maryv2-update-",
            suffix=".part",
            dir=self.updates_root,
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            try:
                with urlopen(request, timeout=max(self.timeout, 30.0)) as response:  # noqa: S310
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                        handle.write(chunk)
            except Exception:
                temp_path.unlink(missing_ok=True)
                raise

        actual = digest.hexdigest().lower()
        if actual != manifest.sha256.lower():
            temp_path.unlink(missing_ok=True)
            raise ValueError(
                f"Update SHA-256 mismatch: expected {manifest.sha256}, got {actual}."
            )
        temp_path.replace(target)
        return target
