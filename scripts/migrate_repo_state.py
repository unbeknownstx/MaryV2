"""Safely migrate legacy repository-local Mary state to the canonical data root.

Dry-run is the default. Apply mode stages a verified copy before atomically
installing it, preserves an existing destination beside the canonical data
directory, and retains the legacy source unless ``--remove-source`` is given.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
from typing import Callable
from uuid import uuid4

from mary.core.config import PathConfig


_SQLITE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
_SQLITE_SIDECARS = ("-wal", "-shm", "-journal")
_WINDOWS_REPARSE_POINT = 0x0400


@dataclass(frozen=True)
class FileRecord:
    relative_path: Path
    size: int
    sha256: str
    sqlite: bool = False


class _ParentGuard:
    """Pin a transaction parent against path redirection during replacement."""

    def __init__(self, path: Path) -> None:
        self.path = _normalized(path)
        self._descriptor: int | None = None
        self._windows_handle: int | None = None
        self._identity: tuple[int, int] | None = None

    def __enter__(self) -> "_ParentGuard":
        _reject_symlink_components(self.path, label="Transaction parent")
        details = os.lstat(self.path)
        if not stat.S_ISDIR(details.st_mode):
            raise ValueError(f"Transaction parent is not a directory: {self.path}")
        self._identity = (details.st_dev, details.st_ino)
        if os.name == "nt":
            self._windows_handle = _open_windows_directory_guard(self.path)
        else:
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            self._descriptor = os.open(self.path, flags)
            opened = os.fstat(self._descriptor)
            if (opened.st_dev, opened.st_ino) != self._identity:
                self.close()
                raise ValueError("Transaction parent changed while it was opened.")
        self.assert_current()
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.close()
        return False

    def close(self) -> None:
        if self._descriptor is not None:
            os.close(self._descriptor)
            self._descriptor = None
        if self._windows_handle is not None:
            _close_windows_handle(self._windows_handle)
            self._windows_handle = None

    def assert_current(self) -> None:
        _reject_symlink_components(self.path, label="Transaction parent")
        details = os.lstat(self.path)
        if (
            not stat.S_ISDIR(details.st_mode)
            or (details.st_dev, details.st_ino) != self._identity
        ):
            raise ValueError("Transaction parent changed during migration.")

    @property
    def identity(self) -> tuple[int, int]:
        if self._identity is None:
            raise RuntimeError("Transaction parent is not open.")
        return self._identity

    def child_identity(self, name: str) -> os.stat_result:
        if Path(name).name != name:
            raise ValueError("Transaction child name must be a single path component.")
        if os.name != "nt" and self._descriptor is not None:
            details = os.stat(
                name,
                dir_fd=self._descriptor,
                follow_symlinks=False,
            )
        else:
            details = os.lstat(self.path / name)
        attributes = getattr(details, "st_file_attributes", 0)
        if stat.S_ISLNK(details.st_mode) or attributes & _WINDOWS_REPARSE_POINT:
            raise ValueError("Transaction child cannot be a symlink or reparse point.")
        return details

    def replace_from(
        self,
        source_guard: "_ParentGuard",
        source_name: str,
        destination_name: str,
        *,
        validate_paths: bool = True,
    ) -> None:
        if validate_paths:
            source_guard.assert_current()
            self.assert_current()
        source_guard.child_identity(source_name)
        if (
            os.name == "nt"
            and source_guard._windows_handle is not None
            and self._windows_handle is not None
        ):
            _windows_replace_relative(
                source_guard,
                source_name,
                self,
                destination_name,
            )
        elif (
            source_guard._descriptor is not None
            and self._descriptor is not None
        ):
            os.replace(
                source_name,
                destination_name,
                src_dir_fd=source_guard._descriptor,
                dst_dir_fd=self._descriptor,
            )
        else:
            raise RuntimeError("No safe directory-relative replacement is available.")


def _open_windows_directory_guard(path: Path) -> int:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    file_list_directory = 0x0001
    file_read_attributes = 0x0080
    share_read_write = 0x00000001 | 0x00000002
    open_existing = 3
    backup_semantics = 0x02000000
    open_reparse_point = 0x00200000
    handle = create_file(
        str(path),
        file_list_directory | file_read_attributes,
        share_read_write,
        None,
        open_existing,
        backup_semantics | open_reparse_point,
        None,
    )
    invalid = wintypes.HANDLE(-1).value
    if handle == invalid:
        raise OSError(ctypes.get_last_error(), "Could not lock transaction parent.")
    return int(handle)


def _windows_replace_relative(
    source_guard: _ParentGuard,
    source_name: str,
    destination_guard: _ParentGuard,
    destination_name: str,
) -> None:
    import ctypes
    from ctypes import wintypes

    if (
        source_guard._windows_handle is None
        or destination_guard._windows_handle is None
    ):
        raise RuntimeError("Windows transaction parent handles are not open.")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    delete_access = 0x00010000
    file_read_attributes = 0x0080
    share_all = 0x00000001 | 0x00000002 | 0x00000004
    open_existing = 3
    backup_semantics = 0x02000000
    open_reparse_point = 0x00200000
    source_handle = create_file(
        str(source_guard.path / source_name),
        delete_access | file_read_attributes,
        share_all,
        None,
        open_existing,
        backup_semantics | open_reparse_point,
        None,
    )
    invalid = wintypes.HANDLE(-1).value
    if source_handle == invalid:
        raise OSError(
            ctypes.get_last_error(),
            "Could not open transaction child for relative replacement.",
        )

    class FileRenameInfo(ctypes.Structure):
        _fields_ = [
            ("ReplaceIfExists", ctypes.c_ubyte),
            ("RootDirectory", wintypes.HANDLE),
            ("FileNameLength", wintypes.DWORD),
            ("FileName", wintypes.WCHAR * 1),
        ]

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("FileAttributes", wintypes.DWORD),
            ("CreationTime", wintypes.FILETIME),
            ("LastAccessTime", wintypes.FILETIME),
            ("LastWriteTime", wintypes.FILETIME),
            ("VolumeSerialNumber", wintypes.DWORD),
            ("FileSizeHigh", wintypes.DWORD),
            ("FileSizeLow", wintypes.DWORD),
            ("NumberOfLinks", wintypes.DWORD),
            ("FileIndexHigh", wintypes.DWORD),
            ("FileIndexLow", wintypes.DWORD),
        ]

    try:
        expected = source_guard.child_identity(source_name)
        get_information = kernel32.GetFileInformationByHandle
        get_information.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ByHandleFileInformation),
        ]
        get_information.restype = wintypes.BOOL
        opened = ByHandleFileInformation()
        if not get_information(source_handle, ctypes.byref(opened)):
            raise OSError(
                ctypes.get_last_error(),
                "Could not verify Windows transaction child identity.",
            )
        opened_index = (opened.FileIndexHigh << 32) | opened.FileIndexLow
        if (
            opened.FileAttributes & _WINDOWS_REPARSE_POINT
            or expected.st_ino == 0
            or opened_index != expected.st_ino
        ):
            raise ValueError(
                "Windows transaction child changed or is a reparse point."
            )
        encoded_name = destination_name.encode("utf-16-le")
        buffer_size = max(
            ctypes.sizeof(FileRenameInfo),
            FileRenameInfo.FileName.offset + len(encoded_name),
        )
        buffer = ctypes.create_string_buffer(buffer_size)
        rename_info = FileRenameInfo.from_buffer(buffer)
        rename_info.ReplaceIfExists = 0
        rename_info.RootDirectory = wintypes.HANDLE(
            destination_guard._windows_handle
        )
        rename_info.FileNameLength = len(encoded_name)
        ctypes.memmove(
            ctypes.addressof(buffer) + FileRenameInfo.FileName.offset,
            encoded_name,
            len(encoded_name),
        )
        set_information = kernel32.SetFileInformationByHandle
        set_information.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        set_information.restype = wintypes.BOOL
        file_rename_info_class = 3
        if not set_information(
            source_handle,
            file_rename_info_class,
            buffer,
            buffer_size,
        ):
            raise OSError(
                ctypes.get_last_error(),
                "Windows directory-relative replacement failed.",
            )
    finally:
        _close_windows_handle(int(source_handle))


def _close_windows_handle(handle: int) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    if not close_handle(wintypes.HANDLE(handle)):
        raise OSError(ctypes.get_last_error(), "Could not close transaction parent.")


def _reject_symlink_components(path: Path, *, label: str) -> None:
    candidate = Path(path).expanduser().absolute()
    parts = candidate.parts
    current = Path(parts[0])
    for part in parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} cannot contain symlink path components.")
        try:
            attributes = getattr(os.lstat(current), "st_file_attributes", 0)
        except FileNotFoundError:
            continue
        if attributes & _WINDOWS_REPARSE_POINT:
            raise ValueError(
                f"{label} cannot contain Windows reparse-point path components."
            )


def _regular_identity(path: Path, *, label: str) -> os.stat_result:
    _reject_symlink_components(path, label=label)
    try:
        details = os.lstat(path)
    except OSError:
        raise
    if not stat.S_ISREG(details.st_mode):
        raise ValueError(f"{label} is not a regular file: {path.name}")
    return details


def _stable_hash(
    path: Path,
    *,
    destination: Path | None = None,
    label: str = "State file",
) -> tuple[int, str]:
    before = _regular_identity(path, label=label)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    digest = hashlib.sha256()
    copied = 0
    output = None
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            opened = os.fstat(handle.fileno())
            if (
                opened.st_dev != before.st_dev
                or opened.st_ino != before.st_ino
                or not stat.S_ISREG(opened.st_mode)
            ):
                raise ValueError(f"{label} changed while it was being opened.")
            if destination is not None:
                destination.parent.mkdir(parents=True, exist_ok=True)
                output = destination.open("xb")
            try:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
                    copied += len(chunk)
                    if output is not None:
                        output.write(chunk)
                after_open = os.fstat(handle.fileno())
            finally:
                if output is not None:
                    output.close()
    except Exception:
        if destination is not None:
            destination.unlink(missing_ok=True)
        raise

    after_path = _regular_identity(path, label=label)
    stable_identity = (
        after_path.st_dev == before.st_dev
        and after_path.st_ino == before.st_ino
        and after_open.st_dev == before.st_dev
        and after_open.st_ino == before.st_ino
    )
    stable_content = (
        copied == before.st_size
        and after_path.st_size == before.st_size
        and after_open.st_size == before.st_size
        and after_path.st_mtime_ns == before.st_mtime_ns
        and after_open.st_mtime_ns == before.st_mtime_ns
    )
    if not stable_identity or not stable_content:
        if destination is not None:
            destination.unlink(missing_ok=True)
        raise ValueError(f"{label} changed during migration.")
    return copied, digest.hexdigest()


def _sha256(path: Path) -> str:
    _, digest = _stable_hash(path, label="Verification file")
    return digest


def _normalized(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _sqlite_source_identity(path: Path) -> os.stat_result:
    return _regular_identity(path, label="SQLite source")


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _retirement_path(source: Path, moment: datetime) -> Path:
    stamp = moment.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    nonce = uuid4().hex[:12]
    base = source.with_name(
        f".{source.name}.migration-removal_{stamp}_{nonce}"
    )
    candidate = base
    counter = 1
    while candidate.exists() or candidate.is_symlink():
        candidate = base.with_name(f"{base.name}_{counter}")
        counter += 1
    return candidate


def _retire_source(
    source: Path,
    moment: datetime,
    *,
    expected_parent: tuple[int, int],
    expected_source: tuple[int, int],
    expected_records: dict[Path, FileRecord],
) -> tuple[bool, Path | None, str]:
    retirement = _retirement_path(source, moment)
    with _ParentGuard(source.parent) as source_guard:
        if source_guard.identity != expected_parent:
            return False, None, "SourceParentChanged"
        source_details = source_guard.child_identity(source.name)
        if (
            not stat.S_ISDIR(source_details.st_mode)
            or (source_details.st_dev, source_details.st_ino) != expected_source
        ):
            return False, None, "SourceIdentityChanged"
        try:
            source_guard.replace_from(
                source_guard,
                source.name,
                retirement.name,
            )
        except OSError as exc:
            return False, None, type(exc).__name__
        try:
            source_guard.assert_current()
        except (OSError, ValueError) as exc:
            return True, None, type(exc).__name__
    if _snapshot_matches(retirement, expected_records):
        return True, retirement, ""
    return True, retirement, "SourceChangedAfterCopy"


def _is_secret_path(relative: Path) -> bool:
    return any(part.lower().startswith(".env") for part in relative.parts)


def _sqlite_main_for_sidecar(path: Path) -> Path | None:
    name = path.name
    for suffix in _SQLITE_SIDECARS:
        if name.endswith(suffix):
            return path.with_name(name[: -len(suffix)])
    return None


def _is_sqlite_path(path: Path) -> bool:
    return path.suffix.lower() in _SQLITE_SUFFIXES


def _resolve(path: Path) -> Path:
    candidate = _normalized(path)
    _reject_symlink_components(candidate, label="State directory")
    return candidate


def _inside(candidate: Path, parent: Path) -> bool:
    return candidate == parent or parent in candidate.parents


def _inventory(root: Path) -> tuple[dict[Path, FileRecord], list[Path], list[Path]]:
    records: dict[Path, FileRecord] = {}
    excluded: list[Path] = []
    sidecars: list[Path] = []
    if not root.exists():
        return records, excluded, sidecars
    if not root.is_dir():
        raise ValueError(f"State path is not a directory: {root}")

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if path.is_symlink() or _is_secret_path(relative):
            excluded.append(relative)
            continue
        sidecar_main = _sqlite_main_for_sidecar(path)
        if sidecar_main is not None and _is_sqlite_path(sidecar_main):
            sidecars.append(relative)
            continue
        size, digest = _stable_hash(path)
        records[relative] = FileRecord(
            relative_path=relative,
            size=size,
            sha256=digest,
            sqlite=_is_sqlite_path(path),
        )
    return records, excluded, sidecars


def _sqlite_integrity(path: Path) -> None:
    _regular_identity(path, label="SQLite database")
    try:
        connection = sqlite3.connect(
            f"{path.absolute().as_uri()}?mode=ro",
            uri=True,
            timeout=5.0,
        )
        try:
            rows = connection.execute("PRAGMA quick_check").fetchall()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise ValueError(f"SQLite verification failed for {path.name}.") from exc
    if rows != [("ok",)]:
        raise ValueError(f"SQLite integrity check failed for {path.name}.")


def _copy_sqlite_snapshot(source: Path, destination: Path) -> None:
    before = _sqlite_source_identity(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        source_connection = sqlite3.connect(
            f"{source.absolute().as_uri()}?mode=ro",
            uri=True,
            timeout=5.0,
        )
        destination_connection = sqlite3.connect(destination, timeout=5.0)
        try:
            source_connection.execute("PRAGMA query_only=ON")
            source_connection.backup(destination_connection)
            destination_connection.commit()
            destination_connection.execute("PRAGMA journal_mode=DELETE")
            destination_connection.commit()
        finally:
            destination_connection.close()
            source_connection.close()
    except sqlite3.Error as exc:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise ValueError(
            f"Could not create a consistent SQLite snapshot for {source.name}. "
            "Close Mary and try again."
        ) from exc
    after = _sqlite_source_identity(source)
    if not _same_identity(before, after):
        destination.unlink(missing_ok=True)
        raise ValueError(
            f"SQLite source changed identity during migration: {source.name}."
        )
    _sqlite_integrity(destination)


def _copy_to_staging(
    source: Path,
    staging: Path,
    source_records: dict[Path, FileRecord],
) -> dict[Path, FileRecord]:
    staged_records: dict[Path, FileRecord] = {}
    for relative, record in source_records.items():
        source_path = source / relative
        destination_path = staging / relative
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if record.sqlite:
            _copy_sqlite_snapshot(source_path, destination_path)
        else:
            copied_size, copied_hash = _stable_hash(
                source_path,
                destination=destination_path,
            )
            if (
                copied_size != record.size
                or copied_hash != record.sha256
            ):
                destination_path.unlink(missing_ok=True)
                raise ValueError(
                    f"Source file changed after inspection: {relative.as_posix()}."
                )
        staged_records[relative] = FileRecord(
            relative_path=relative,
            size=destination_path.stat().st_size,
            sha256=_sha256(destination_path),
            sqlite=record.sqlite,
        )
    return staged_records


def _verify_tree(root: Path, expected: dict[Path, FileRecord]) -> None:
    actual, excluded, sidecars = _inventory(root)
    if excluded or sidecars:
        raise ValueError("Verified migration output contains unexpected excluded files.")
    if set(actual) != set(expected):
        raise ValueError("Migration verification failed: file set mismatch.")
    for relative, expected_record in expected.items():
        actual_record = actual[relative]
        if (
            actual_record.size != expected_record.size
            or actual_record.sha256 != expected_record.sha256
        ):
            raise ValueError(
                f"Migration verification failed for {relative.as_posix()}."
            )
        if expected_record.sqlite:
            _sqlite_integrity(root / relative)


def _records_match(
    left: dict[Path, FileRecord],
    right: dict[Path, FileRecord],
) -> bool:
    if set(left) != set(right):
        return False
    return all(
        left[path].size == right[path].size
        and left[path].sha256 == right[path].sha256
        and left[path].sqlite == right[path].sqlite
        for path in left
    )


def _snapshot_matches(
    source: Path,
    expected: dict[Path, FileRecord],
) -> bool:
    try:
        current, _, _ = _inventory(source)
        with tempfile.TemporaryDirectory(
            prefix="maryv2_source_recheck_",
        ) as temporary:
            snapshot = Path(temporary) / "data"
            copied = _copy_to_staging(source, snapshot, current)
            _verify_tree(snapshot, copied)
        return _records_match(copied, expected)
    except (OSError, ValueError, sqlite3.Error):
        return False


def _preservation_path(destination: Path, moment: datetime) -> Path:
    stamp = moment.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    nonce = uuid4().hex[:12]
    base = destination.with_name(
        f"{destination.name}.before_repo_migration_{stamp}_{nonce}"
    )
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = base.with_name(f"{base.name}_{counter}")
        counter += 1
    return candidate


def _failed_install_path(destination: Path, moment: datetime) -> Path:
    stamp = moment.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    nonce = uuid4().hex[:12]
    base = destination.with_name(
        f"{destination.name}.failed_repo_migration_{stamp}_{nonce}"
    )
    candidate = base
    counter = 1
    while candidate.exists() or candidate.is_symlink():
        candidate = base.with_name(f"{base.name}_{counter}")
        counter += 1
    return candidate


def _verify_installed_directory(
    guard: _ParentGuard,
    name: str,
    expected: os.stat_result,
) -> None:
    guard.assert_current()
    installed = guard.child_identity(name)
    if (
        not stat.S_ISDIR(installed.st_mode)
        or installed.st_dev != expected.st_dev
        or installed.st_ino != expected.st_ino
    ):
        raise ValueError("Installed migration directory identity verification failed.")
    guard.assert_current()


def inspect_migration(source: Path, destination: Path) -> dict:
    source_root = _resolve(source)
    destination_root = _resolve(destination)
    same_path = source_root == destination_root
    if not same_path and (
        _inside(source_root, destination_root)
        or _inside(destination_root, source_root)
    ):
        raise ValueError("Source and destination state directories must be separate.")

    source_records, source_excluded, source_sidecars = _inventory(source_root)
    if same_path:
        destination_records = source_records
        destination_excluded = source_excluded
        destination_sidecars = source_sidecars
    else:
        (
            destination_records,
            destination_excluded,
            destination_sidecars,
        ) = _inventory(destination_root)
    shared = sorted(set(source_records) & set(destination_records))
    identical = [
        path
        for path in shared
        if (
            source_records[path].size == destination_records[path].size
            and source_records[path].sha256 == destination_records[path].sha256
        )
    ]
    conflicts = [path for path in shared if path not in identical]
    return {
        "source": source_root,
        "destination": destination_root,
        "already_canonical": same_path,
        "source_exists": source_root.is_dir(),
        "source_file_count": len(source_records) + len(source_sidecars),
        "source_copy_count": len(source_records),
        "source_sqlite_count": sum(
            1 for record in source_records.values() if record.sqlite
        ),
        "source_sqlite_sidecar_count": len(source_sidecars),
        "source_excluded_count": len(source_excluded),
        "destination_file_count": len(destination_records)
        + len(destination_sidecars),
        "destination_excluded_count": len(destination_excluded),
        "identical_count": len(identical),
        "conflict_count": len(conflicts),
        "conflicts": [path.as_posix() for path in conflicts],
        "_source_records": source_records,
    }


def migrate_repo_state(
    source: Path,
    destination: Path,
    *,
    apply: bool = False,
    remove_source: bool = False,
    repository_root: Path | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict:
    report = inspect_migration(source, destination)
    report["applied"] = False
    report["source_removed"] = False
    report["preserved_destination"] = None

    if not report["source_exists"]:
        raise FileNotFoundError(f"Legacy repository state was not found: {report['source']}")
    if report["source_copy_count"] == 0:
        raise ValueError("Legacy repository state contains no eligible files.")
    if report["already_canonical"]:
        if remove_source:
            raise ValueError(
                "Cannot remove the source because it is already the canonical data directory."
            )
        return report
    if not apply:
        return report

    source_root = report["source"]
    destination_root = report["destination"]
    repository = _resolve(
        repository_root or Path(__file__).resolve().parents[1]
    )
    expected_legacy_source = repository / "data"
    if remove_source and source_root != expected_legacy_source:
        raise ValueError(
            "--remove-source is allowed only for the repository's legacy data directory."
        )
    source_parent_details = os.lstat(source_root.parent)
    source_details = os.lstat(source_root)
    source_parent_identity = (
        source_parent_details.st_dev,
        source_parent_details.st_ino,
    )
    source_identity = (source_details.st_dev, source_details.st_ino)

    destination_root.parent.mkdir(parents=True, exist_ok=True)
    moment = (now or (lambda: datetime.now(timezone.utc)))()
    preservation: Path | None = None
    destination_installed = False

    with tempfile.TemporaryDirectory(
        prefix="maryv2_repo_migration_",
        dir=str(destination_root.parent),
    ) as temporary:
        staging = Path(temporary) / "data"
        staging.mkdir()
        staged_records = _copy_to_staging(
            source_root,
            staging,
            report["_source_records"],
        )
        _verify_tree(staging, staged_records)

        staging_identity = os.lstat(staging)
        with (
            _ParentGuard(destination_root.parent) as destination_guard,
            _ParentGuard(staging.parent) as staging_guard,
        ):
            try:
                if destination_root.exists():
                    destination_guard.child_identity(destination_root.name)
                    preservation = _preservation_path(destination_root, moment)
                    destination_guard.replace_from(
                        destination_guard,
                        destination_root.name,
                        preservation.name,
                    )

                destination_guard.replace_from(
                    staging_guard,
                    staging.name,
                    destination_root.name,
                )
                destination_installed = True
                _verify_installed_directory(
                    destination_guard,
                    destination_root.name,
                    staging_identity,
                )
            except Exception as migration_error:
                failed_install: Path | None = None
                try:
                    if destination_installed:
                        failed_install = _failed_install_path(
                            destination_root,
                            moment,
                        )
                        destination_guard.replace_from(
                            destination_guard,
                            destination_root.name,
                            failed_install.name,
                            validate_paths=False,
                        )
                    if preservation is not None:
                        destination_guard.replace_from(
                            destination_guard,
                            preservation.name,
                            destination_root.name,
                            validate_paths=False,
                        )
                except Exception as rollback_error:
                    raise RuntimeError(
                        "Migration failed and automatic destination rollback "
                        "could not complete; all retained locations must be "
                        "reviewed before retrying."
                    ) from rollback_error
                raise migration_error

    report["applied"] = True
    report["preserved_destination"] = preservation
    report["installed_file_count"] = len(staged_records)
    report["installed_sqlite_count"] = sum(
        1 for record in staged_records.values() if record.sqlite
    )
    report["source_cleanup_pending"] = None
    report["source_cleanup_error"] = ""
    if remove_source:
        removed, pending, error_type = _retire_source(
            source_root,
            moment,
            expected_parent=source_parent_identity,
            expected_source=source_identity,
            expected_records=staged_records,
        )
        report["source_removed"] = removed
        report["source_cleanup_pending"] = pending
        report["source_cleanup_error"] = error_type
    return report


def _print_report(report: dict) -> None:
    print("=" * 72)
    print("MARYV2 REPOSITORY STATE MIGRATION")
    print("=" * 72)
    print(f"Legacy source:       {report['source']}")
    print(f"Canonical data root: {report['destination']}")
    print(
        "Source files:       "
        f"{report['source_file_count']} "
        f"({report['source_copy_count']} copied; "
        f"{report['source_excluded_count']} secret/symlink excluded)"
    )
    print(f"Destination files:  {report['destination_file_count']}")
    print(f"Conflicts:          {report['conflict_count']}")
    for conflict in report["conflicts"][:20]:
        print(f"  - {conflict}")
    if len(report["conflicts"]) > 20:
        print(f"  ... {len(report['conflicts']) - 20} more")
    if report["source_sqlite_count"]:
        print(
            "SQLite databases:  "
            f"{report['source_sqlite_count']} "
            f"({report['source_sqlite_sidecar_count']} live sidecars detected)"
        )
    if report["applied"]:
        print(f"PASS  Installed {report['installed_file_count']} verified files.")
        if report["preserved_destination"] is not None:
            print(
                "Preserved previous destination: "
                f"{report['preserved_destination']}"
            )
        if report["source_removed"]:
            if report["source_cleanup_pending"] is not None:
                print(
                    "WARNING  Legacy source left in cleanup quarantine: "
                    f"{report['source_cleanup_pending']}"
                )
            else:
                print("Legacy repository source removed by explicit request.")
        elif report["source_cleanup_error"]:
            print(
                "WARNING  Migration succeeded, but the explicitly requested "
                "source cleanup did not run."
            )
        else:
            print("Legacy repository source was not deleted or modified.")
    else:
        if report["already_canonical"]:
            print("NO MIGRATION NEEDED - source is already the canonical data root.")
        else:
            print("DRY RUN ONLY - no files changed. Add --apply to migrate state.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Safely migrate legacy repository-local Mary state to the "
            "configured canonical data directory"
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Legacy source; defaults to this repository's data directory",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Canonical destination; defaults to MARY_DATA_DIR or host-native MaryV2 data",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Stage, verify, and install the migration",
    )
    parser.add_argument(
        "--remove-source",
        action="store_true",
        help="After successful verification, remove the repository's legacy data directory",
    )
    args = parser.parse_args(argv)

    repository_root = Path(__file__).resolve().parents[1]
    source = args.source or (repository_root / "data")
    destination = args.data_dir or PathConfig().data
    if args.remove_source and not args.apply:
        parser.error("--remove-source requires --apply")

    try:
        report = migrate_repo_state(
            source,
            destination,
            apply=args.apply,
            remove_source=args.remove_source,
            repository_root=repository_root,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"FAIL  {exc}")
        return 1

    _print_report(report)
    return 2 if report.get("source_cleanup_error") else 0


if __name__ == "__main__":
    raise SystemExit(main())