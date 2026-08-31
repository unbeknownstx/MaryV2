"""Local, non-serializable storage for durable node credentials."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import stat
import tempfile


class CredentialStoreError(RuntimeError):
    """The local device credential could not be read or safely stored."""


class NodeCredentialStore:
    """Store one credential per node without exposing it in application state."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else self._default_root()

    @staticmethod
    def _default_root() -> Path:
        if os.name == "nt":
            base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            if not base:
                raise CredentialStoreError("Windows local application data is unavailable.")
            return Path(base) / "MaryV2" / "device_credentials"
        base = os.environ.get("XDG_STATE_HOME")
        return Path(base) / "MaryV2" / "device_credentials" if base else (
            Path.home() / ".local" / "state" / "MaryV2" / "device_credentials"
        )

    def _path(self, node_id: str) -> Path:
        clean = str(node_id or "").strip()
        if not clean:
            raise CredentialStoreError("A node ID is required for credential storage.")
        # Avoid making a user-provided device ID part of a filesystem path.
        return self.root / (hashlib.sha256(clean.encode("utf-8")).hexdigest() + ".credential")

    def _require_private_posix_root(self) -> None:
        if os.name == "nt" or not self.root.exists():
            return
        try:
            info = self.root.lstat()
        except OSError as exc:
            raise CredentialStoreError("Could not access local credential storage.") from exc
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise CredentialStoreError("Local credential directory has unsafe permissions.")

    def load(self, node_id: str) -> str:
        path = self._path(node_id)
        self._require_private_posix_root()
        try:
            info = path.lstat()
        except FileNotFoundError:
            return ""
        except OSError as exc:
            raise CredentialStoreError("Could not access the local node credential.") from exc
        if not stat.S_ISREG(info.st_mode):
            raise CredentialStoreError("Local node credential is not a regular file.")
        if os.name != "nt" and stat.S_IMODE(info.st_mode) != 0o600:
            raise CredentialStoreError("Local node credential has unsafe permissions.")
        try:
            raw = path.read_bytes()
            plain = self._unprotect(raw) if os.name == "nt" else raw
            credential = plain.decode("utf-8")
        except CredentialStoreError:
            raise
        except Exception as exc:
            raise CredentialStoreError("Could not read the local node credential.") from exc
        if not credential:
            raise CredentialStoreError("Local node credential is invalid.")
        return credential

    def save(self, node_id: str, credential: str) -> None:
        clean = str(credential or "")
        if not clean:
            raise CredentialStoreError("Refusing to store an empty node credential.")
        path = self._path(node_id)
        try:
            self._require_private_posix_root()
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            if os.name != "nt":
                os.chmod(self.root, 0o700)
            raw = self._protect(clean.encode("utf-8")) if os.name == "nt" else clean.encode("utf-8")
            fd, temporary = tempfile.mkstemp(prefix=".credential-", dir=self.root)
            try:
                if os.name != "nt":
                    os.fchmod(fd, 0o600)
                with os.fdopen(fd, "wb") as output:
                    output.write(raw)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, path)
                if os.name != "nt":
                    os.chmod(path, 0o600)
            except Exception:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
                raise
        except CredentialStoreError:
            raise
        except Exception as exc:
            raise CredentialStoreError("Could not securely store the node credential.") from exc

    @staticmethod
    def _protect(value: bytes) -> bytes:
        return _dpapi(value, protect=True)

    @staticmethod
    def _unprotect(value: bytes) -> bytes:
        return _dpapi(value, protect=False)


# This spelling is intentionally available for callers that use the generic name.
DeviceCredentialStore = NodeCredentialStore


def _dpapi(value: bytes, *, protect: bool) -> bytes:
    """Use CurrentUser DPAPI directly, avoiding a pywin32 dependency."""
    if os.name != "nt":
        return value

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    source_buffer = ctypes.create_string_buffer(value)
    source = DATA_BLOB(len(value), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
    output = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    # CRYPTPROTECT_UI_FORBIDDEN keeps scheduled/headless execution non-interactive.
    ok = function(
        ctypes.byref(source),
        None,
        None,
        None,
        None,
        0x1,
        ctypes.byref(output),
    )
    if not ok:
        raise CredentialStoreError("Windows credential protection failed.")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)