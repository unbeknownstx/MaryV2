"""Sandboxed creative-project access for MaryV2 Desktop Studio.

This module intentionally does not make Mary's general filesystem toolset a UI
primitive. Studio is limited to one creator-selected root and a small set of
editable text formats. Paths are always resolved back under that root before
read/write operations.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any


_TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".csv"}
_REFERENCE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".psd", ".psb", ".kra", ".clip", ".blend", ".xcf",
    ".wav", ".mp3", ".m4a", ".ogg", ".flac", ".mp4", ".mov", ".mkv",
}
_MAX_FILES = 500
_MAX_DEPTH = 8
_MAX_TEXT_BYTES = 2_000_000


@dataclass(frozen=True)
class CreativeFile:
    path: str
    name: str
    kind: str
    size: int
    editable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "kind": self.kind,
            "size": self.size,
            "editable": self.editable,
        }


class CreativeWorkspaceManager:
    """Read/write access confined to one explicitly configured project root."""

    def __init__(self, root: str | Path | None = None) -> None:
        configured = str(root or os.getenv("MARY_CREATIVE_WORKSPACE", "")).strip()
        self._root: Path | None = None
        if configured:
            self.set_root(configured)

    @property
    def root(self) -> Path | None:
        return self._root

    @property
    def configured(self) -> bool:
        return bool(self._root and self._root.exists() and self._root.is_dir())

    def set_root(self, root: str | Path) -> Path:
        candidate = Path(root).expanduser().resolve()
        if not candidate.exists() or not candidate.is_dir():
            raise NotADirectoryError(f"Creative workspace is not a directory: {candidate}")
        self._root = candidate
        return candidate

    def clear_root(self) -> None:
        self._root = None

    def _require_root(self) -> Path:
        if not self.configured or self._root is None:
            raise RuntimeError(
                "No creative workspace is selected. Choose the Unbeknownst/project folder "
                "in Studio or set MARY_CREATIVE_WORKSPACE in Mary's private .env."
            )
        return self._root

    def _resolve(self, relative_path: str | Path) -> Path:
        root = self._require_root()
        raw = Path(str(relative_path or "").strip())
        if not str(raw):
            raise ValueError("A project-relative path is required.")
        if raw.is_absolute():
            candidate = raw.expanduser().resolve()
        else:
            candidate = (root / raw).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise PermissionError("Creative project path escapes the selected workspace.") from exc
        return candidate

    @staticmethod
    def _kind(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in _TEXT_EXTENSIONS:
            return "text"
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            return "image"
        if suffix in {".wav", ".mp3", ".m4a", ".ogg", ".flac"}:
            return "audio"
        if suffix in {".mp4", ".mov", ".mkv"}:
            return "video"
        if suffix in {".psd", ".psb", ".kra", ".clip", ".blend", ".xcf"}:
            return "creative"
        return "other"

    def list_files(self) -> list[dict[str, Any]]:
        root = self._require_root()
        results: list[CreativeFile] = []
        try:
            candidates = root.rglob("*")
            for path in candidates:
                if len(results) >= _MAX_FILES:
                    break
                try:
                    if not path.is_file() or path.is_symlink():
                        continue
                    relative = path.relative_to(root)
                    if len(relative.parts) > _MAX_DEPTH:
                        continue
                    if any(part.startswith(".") for part in relative.parts):
                        continue
                    suffix = path.suffix.lower()
                    if suffix not in _TEXT_EXTENSIONS | _REFERENCE_EXTENSIONS:
                        continue
                    results.append(
                        CreativeFile(
                            path=relative.as_posix(),
                            name=path.name,
                            kind=self._kind(path),
                            size=int(path.stat().st_size),
                            editable=suffix in _TEXT_EXTENSIONS,
                        )
                    )
                except OSError:
                    continue
        except OSError:
            return []

        def key(item: CreativeFile) -> tuple[int, str]:
            lower = item.path.casefold()
            chapterish = 0 if ("chapter" in lower or "ch_" in lower or "/ch" in lower) else 1
            return chapterish, lower

        results.sort(key=key)
        return [item.to_dict() for item in results]

    def status(self) -> dict[str, Any]:
        if not self.configured or self._root is None:
            return {
                "configured": False,
                "root": "",
                "name": "No project selected",
                "files": [],
                "limits": {
                    "max_files": _MAX_FILES,
                    "max_depth": _MAX_DEPTH,
                    "max_text_bytes": _MAX_TEXT_BYTES,
                },
            }
        files = self.list_files()
        return {
            "configured": True,
            "root": str(self._root),
            "name": self._root.name,
            "files": files,
            "file_count": len(files),
            "editable_count": sum(1 for item in files if item["editable"]),
            "limits": {
                "max_files": _MAX_FILES,
                "max_depth": _MAX_DEPTH,
                "max_text_bytes": _MAX_TEXT_BYTES,
            },
        }

    def read_text(self, relative_path: str | Path) -> dict[str, Any]:
        path = self._resolve(relative_path)
        if path.suffix.lower() not in _TEXT_EXTENSIONS:
            raise ValueError(f"Studio text editor does not edit {path.suffix or 'extensionless'} files.")
        if not path.exists() or not path.is_file() or path.is_symlink():
            raise FileNotFoundError(f"Project text file does not exist: {path.name}")
        size = int(path.stat().st_size)
        if size > _MAX_TEXT_BYTES:
            raise ValueError(f"Project text file exceeds {_MAX_TEXT_BYTES} bytes.")
        content = path.read_text(encoding="utf-8")
        root = self._require_root()
        return {
            "path": path.relative_to(root).as_posix(),
            "name": path.name,
            "content": content,
            "size": size,
            "editable": True,
        }

    def save_text(self, relative_path: str | Path, content: str) -> dict[str, Any]:
        path = self._resolve(relative_path)
        if path.suffix.lower() not in _TEXT_EXTENSIONS:
            raise ValueError(f"Studio text editor does not write {path.suffix or 'extensionless'} files.")
        if path.is_symlink():
            raise PermissionError("Studio will not write through symbolic links.")
        encoded = str(content).encode("utf-8")
        if len(encoded) > _MAX_TEXT_BYTES:
            raise ValueError(f"Project text exceeds {_MAX_TEXT_BYTES} bytes.")
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".marytmp")
        temp.write_bytes(encoded)
        temp.replace(path)
        root = self._require_root()
        return {
            "saved": True,
            "path": path.relative_to(root).as_posix(),
            "size": len(encoded),
        }
