"""
MaryV2 - Filesystem Tool

Controlled filesystem access for Mary.

SECURITY MODEL
--------------

The filesystem is treated as a capability, not an unrestricted
Python utility.

Mary may eventually be able to:

    - inspect permitted files
    - read text
    - list permitted directories
    - inspect metadata

Operations that modify state require explicit creator approval:

    - write
    - append
    - delete
    - move
    - create directories
    - modify files

The filesystem is also restricted to configured workspace roots.

This prevents a path such as:

    ../../../../somewhere/private

from automatically escaping Mary's permitted environment.

IMPORTANT
---------

Filesystem access is separate from code execution.

Reading a Python file does NOT mean Mary is allowed to execute it.

Writing a Python file does NOT mean Mary is allowed to execute it.

Changing Mary's own source code is considered creator-sensitive and
requires explicit approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .registry import (
    PermissionLevel,
    ToolRegistry,
)


# ================================================================
# CONFIGURATION
# ================================================================


@dataclass
class FilesystemConfig:
    """
    Configuration for Mary's filesystem capability.
    """

    workspace_roots: list[Path] = field(
        default_factory=list
    )

    max_read_bytes: int = (
        2_000_000
    )

    max_list_entries: int = 1_000

    allow_hidden_files: bool = True

    allow_symlinks: bool = False


@dataclass
class FileInfo:
    """
    Serializable information about a filesystem entry.
    """

    path: str

    name: str

    exists: bool

    is_file: bool

    is_directory: bool

    is_symlink: bool

    size: int = 0

    suffix: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "exists": self.exists,
            "is_file": self.is_file,
            "is_directory": self.is_directory,
            "is_symlink": self.is_symlink,
            "size": self.size,
            "suffix": self.suffix,
            "metadata": dict(
                self.metadata
            ),
        }


# ================================================================
# FILESYSTEM CLIENT
# ================================================================


class FilesystemClient:
    """
    Controlled filesystem interface.

    The client itself does not decide whether Mary is authorized
    to perform an operation.

    ToolRegistry provides the permission boundary.

    This class additionally enforces path boundaries.
    """

    def __init__(
        self,
        config: FilesystemConfig | None = None,
    ) -> None:

        self.config = (
            config
            if config is not None
            else FilesystemConfig()
        )

        self._roots = [
            self._resolve_root(root)
            for root
            in self.config.workspace_roots
        ]

    # ============================================================
    # CONFIGURATION
    # ============================================================

    def add_workspace_root(
        self,
        root: str | Path,
    ) -> Path:
        """
        Add an allowed workspace root.

        This changes filesystem policy and should normally be
        performed during application configuration, not by Mary's
        autonomous runtime.
        """

        resolved = self._resolve_root(
            root
        )

        if resolved not in self._roots:
            self._roots.append(
                resolved
            )

        return resolved

    def workspace_roots(
        self,
    ) -> list[Path]:
        """
        Return configured workspace roots.
        """

        return list(
            self._roots
        )

    # ============================================================
    # INSPECTION
    # ============================================================

    def exists(
        self,
        path: str,
    ) -> bool:
        """
        Determine whether a permitted path exists.
        """

        target = self._resolve_allowed_path(
            path,
            must_exist=False,
        )

        return target.exists()

    def info(
        self,
        path: str,
    ) -> FileInfo:
        """
        Return metadata about a permitted path.
        """

        target = self._resolve_allowed_path(
            path,
            must_exist=False,
        )

        if not target.exists():
            return FileInfo(
                path=str(
                    target
                ),
                name=target.name,
                exists=False,
                is_file=False,
                is_directory=False,
                is_symlink=target.is_symlink(),
            )

        if (
            target.is_symlink()
            and not self.config.allow_symlinks
        ):
            raise PermissionError(
                "Symbolic links are disabled."
            )

        stat = target.stat()

        return FileInfo(
            path=str(
                target
            ),
            name=target.name,
            exists=True,
            is_file=target.is_file(),
            is_directory=target.is_dir(),
            is_symlink=target.is_symlink(),
            size=stat.st_size,
            suffix=target.suffix,
        )

    # ============================================================
    # DIRECTORY LISTING
    # ============================================================

    def list_directory(
        self,
        path: str = ".",
    ) -> list[FileInfo]:
        """
        List entries in a permitted directory.
        """

        directory = self._resolve_allowed_path(
            path
        )

        if not directory.is_dir():
            raise NotADirectoryError(
                f"Not a directory: "
                f"{directory}"
            )

        entries: list[
            FileInfo
        ] = []

        for entry in directory.iterdir():

            if (
                not self.config.allow_hidden_files
                and entry.name.startswith(".")
            ):
                continue

            if (
                len(entries)
                >= self.config.max_list_entries
            ):
                break

            if (
                entry.is_symlink()
                and not self.config.allow_symlinks
            ):
                continue

            entries.append(
                self.info(
                    str(entry)
                )
            )

        entries.sort(
            key=lambda item: (
                not item.is_directory,
                item.name.lower(),
            )
        )

        return entries

    # ============================================================
    # READ
    # ============================================================

    def read_text(
        self,
        path: str,
        *,
        encoding: str = "utf-8",
    ) -> str:
        """
        Read a text file.

        Reading does not modify filesystem state.
        """

        target = self._resolve_allowed_path(
            path
        )

        if not target.is_file():
            raise IsADirectoryError(
                f"Not a file: "
                f"{target}"
            )

        if (
            target.is_symlink()
            and not self.config.allow_symlinks
        ):
            raise PermissionError(
                "Symbolic links are disabled."
            )

        size = target.stat().st_size

        if (
            size
            > self.config.max_read_bytes
        ):
            raise ValueError(
                "File exceeds the maximum "
                "allowed read size."
            )

        try:
            return target.read_text(
                encoding=encoding
            )
        except UnicodeDecodeError as exc:
            raise ValueError(
                "File could not be decoded "
                f"using {encoding}."
            ) from exc

    def read_bytes(
        self,
        path: str,
    ) -> bytes:
        """
        Read a binary file within the workspace boundary.
        """

        target = self._resolve_allowed_path(
            path
        )

        if not target.is_file():
            raise IsADirectoryError(
                f"Not a file: "
                f"{target}"
            )

        if (
            target.is_symlink()
            and not self.config.allow_symlinks
        ):
            raise PermissionError(
                "Symbolic links are disabled."
            )

        size = target.stat().st_size

        if (
            size
            > self.config.max_read_bytes
        ):
            raise ValueError(
                "File exceeds the maximum "
                "allowed read size."
            )

        return target.read_bytes()

    # ============================================================
    # WRITE
    # ============================================================

    def write_text(
        self,
        path: str,
        content: str,
        *,
        encoding: str = "utf-8",
        overwrite: bool = False,
    ) -> str:
        """
        Write a text file.

        IMPORTANT:

        This method changes filesystem state.

        ToolRegistry should expose it only as an
        APPROVAL_REQUIRED capability.
        """

        target = self._resolve_allowed_path(
            path,
            must_exist=False,
        )

        if target.exists():

            if (
                not overwrite
            ):
                raise FileExistsError(
                    f"File already exists: "
                    f"{target}"
                )

            if target.is_dir():
                raise IsADirectoryError(
                    f"Cannot overwrite "
                    f"directory: {target}"
                )

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        target.write_text(
            content,
            encoding=encoding,
        )

        return str(
            target
        )

    # ============================================================
    # APPEND
    # ============================================================

    def append_text(
        self,
        path: str,
        content: str,
        *,
        encoding: str = "utf-8",
    ) -> str:
        """
        Append text to an existing file.

        This is a state-changing operation and must be
        approval-gated by ToolRegistry.
        """

        target = self._resolve_allowed_path(
            path
        )

        if target.is_dir():
            raise IsADirectoryError(
                f"Cannot append to "
                f"directory: {target}"
            )

        with target.open(
            "a",
            encoding=encoding,
        ) as file:
            file.write(
                content
            )

        return str(
            target
        )

    # ============================================================
    # DIRECTORY CREATION
    # ============================================================

    def create_directory(
        self,
        path: str,
    ) -> str:
        """
        Create a directory.

        State-changing operation.
        """

        target = self._resolve_allowed_path(
            path,
            must_exist=False,
        )

        if target.exists():
            if target.is_dir():
                return str(
                    target
                )

            raise FileExistsError(
                f"Path already exists: "
                f"{target}"
            )

        target.mkdir(
            parents=True,
            exist_ok=True,
        )

        return str(
            target
        )

    # ============================================================
    # DELETE
    # ============================================================

    def delete(
        self,
        path: str,
    ) -> bool:
        """
        Delete a file.

        Directory deletion is intentionally not supported here.

        A dedicated recursive-delete capability would require a
        much stronger approval model.
        """

        target = self._resolve_allowed_path(
            path
        )

        if target.is_dir():
            raise IsADirectoryError(
                "Directory deletion is not "
                "supported by this capability."
            )

        target.unlink()

        return True

    # ============================================================
    # MOVE
    # ============================================================

    def move(
        self,
        source: str,
        destination: str,
    ) -> str:
        """
        Move a file within the allowed workspace.

        Both source and destination must remain within configured
        workspace roots.
        """

        source_path = (
            self._resolve_allowed_path(
                source
            )
        )

        destination_path = (
            self._resolve_allowed_path(
                destination,
                must_exist=False,
            )
        )

        if source_path.is_dir():
            raise IsADirectoryError(
                "Directory moves are not "
                "supported by this capability."
            )

        if destination_path.exists():
            raise FileExistsError(
                f"Destination already exists: "
                f"{destination_path}"
            )

        destination_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        source_path.rename(
            destination_path
        )

        return str(
            destination_path
        )

    # ============================================================
    # TOOL REGISTRATION
    # ============================================================

    def register_tools(
        self,
        registry: ToolRegistry,
    ) -> None:
        """
        Register filesystem capabilities.

        Read-only inspection operations are marked SAFE.

        State-changing operations require explicit creator
        approval.
        """

        # --------------------------------------------------------
        # SAFE READ OPERATIONS
        # --------------------------------------------------------

        registry.register(
            name="filesystem_exists",
            description=(
                "Check whether a permitted "
                "filesystem path exists."
            ),
            function=self.exists,
            category="filesystem",
            version="1.0",
            permission_level=(
                PermissionLevel.SAFE
            ),
            external_access=False,
            mutates_state=False,
            parameters={
                "path": {
                    "type": "string",
                    "required": True,
                },
            },
        )

        registry.register(
            name="filesystem_info",
            description=(
                "Inspect metadata about a "
                "permitted filesystem path."
            ),
            function=self.info,
            category="filesystem",
            version="1.0",
            permission_level=(
                PermissionLevel.SAFE
            ),
            external_access=False,
            mutates_state=False,
            parameters={
                "path": {
                    "type": "string",
                    "required": True,
                },
            },
        )

        registry.register(
            name="filesystem_list",
            description=(
                "List files and directories "
                "inside a permitted workspace."
            ),
            function=self.list_directory,
            category="filesystem",
            version="1.0",
            permission_level=(
                PermissionLevel.SAFE
            ),
            external_access=False,
            mutates_state=False,
            parameters={
                "path": {
                    "type": "string",
                    "required": False,
                },
            },
        )

        registry.register(
            name="filesystem_read",
            description=(
                "Read a text file from a "
                "permitted workspace."
            ),
            function=self.read_text,
            category="filesystem",
            version="1.0",
            permission_level=(
                PermissionLevel.SAFE
            ),
            external_access=False,
            mutates_state=False,
            parameters={
                "path": {
                    "type": "string",
                    "required": True,
                },
                "encoding": {
                    "type": "string",
                    "required": False,
                },
            },
        )

        # --------------------------------------------------------
        # APPROVAL-GATED WRITE OPERATIONS
        # --------------------------------------------------------

        registry.register(
            name="filesystem_write",
            description=(
                "Write or replace a text file "
                "inside a permitted workspace."
            ),
            function=self.write_text,
            category="filesystem",
            version="1.0",
            permission_level=(
                PermissionLevel.APPROVAL_REQUIRED
            ),
            external_access=False,
            mutates_state=True,
            creator_sensitive=True,
            parameters={
                "path": {
                    "type": "string",
                    "required": True,
                },
                "content": {
                    "type": "string",
                    "required": True,
                },
                "encoding": {
                    "type": "string",
                    "required": False,
                },
                "overwrite": {
                    "type": "boolean",
                    "required": False,
                },
            },
            metadata={
                "operation": "filesystem_write",
                "requires_creator_approval": True,
            },
        )

        registry.register(
            name="filesystem_append",
            description=(
                "Append text to a file inside "
                "a permitted workspace."
            ),
            function=self.append_text,
            category="filesystem",
            version="1.0",
            permission_level=(
                PermissionLevel.APPROVAL_REQUIRED
            ),
            external_access=False,
            mutates_state=True,
            creator_sensitive=True,
            parameters={
                "path": {
                    "type": "string",
                    "required": True,
                },
                "content": {
                    "type": "string",
                    "required": True,
                },
                "encoding": {
                    "type": "string",
                    "required": False,
                },
            },
            metadata={
                "operation": "filesystem_append",
                "requires_creator_approval": True,
            },
        )

        registry.register(
            name="filesystem_create_directory",
            description=(
                "Create a directory inside "
                "a permitted workspace."
            ),
            function=self.create_directory,
            category="filesystem",
            version="1.0",
            permission_level=(
                PermissionLevel.APPROVAL_REQUIRED
            ),
            external_access=False,
            mutates_state=True,
            creator_sensitive=True,
            parameters={
                "path": {
                    "type": "string",
                    "required": True,
                },
            },
            metadata={
                "operation": "filesystem_mkdir",
                "requires_creator_approval": True,
            },
        )

        registry.register(
            name="filesystem_delete",
            description=(
                "Delete a file inside a "
                "permitted workspace."
            ),
            function=self.delete,
            category="filesystem",
            version="1.0",
            permission_level=(
                PermissionLevel.APPROVAL_REQUIRED
            ),
            external_access=False,
            mutates_state=True,
            creator_sensitive=True,
            parameters={
                "path": {
                    "type": "string",
                    "required": True,
                },
            },
            metadata={
                "operation": "filesystem_delete",
                "requires_creator_approval": True,
            },
        )

        registry.register(
            name="filesystem_move",
            description=(
                "Move a file inside a "
                "permitted workspace."
            ),
            function=self.move,
            category="filesystem",
            version="1.0",
            permission_level=(
                PermissionLevel.APPROVAL_REQUIRED
            ),
            external_access=False,
            mutates_state=True,
            creator_sensitive=True,
            parameters={
                "source": {
                    "type": "string",
                    "required": True,
                },
                "destination": {
                    "type": "string",
                    "required": True,
                },
            },
            metadata={
                "operation": "filesystem_move",
                "requires_creator_approval": True,
            },
        )

    # ============================================================
    # PATH SECURITY
    # ============================================================

    def _resolve_root(
        self,
        root: str | Path,
    ) -> Path:
        """
        Resolve and normalize a workspace root.
        """

        path = Path(
            root
        ).expanduser().resolve()

        return path

    def _resolve_allowed_path(
        self,
        path: str | Path,
        *,
        must_exist: bool = True,
    ) -> Path:
        """
        Resolve a path and ensure it remains inside a configured
        workspace root.
        """

        if not self._roots:
            raise PermissionError(
                "No filesystem workspace roots "
                "have been configured."
            )

        candidate = Path(
            path
        ).expanduser()

        if not candidate.is_absolute():

            # Relative paths are interpreted relative to the first
            # configured workspace root.
            candidate = (
                self._roots[0]
                / candidate
            )

        candidate = candidate.resolve(
            strict=False
        )

        if (
            not self.config.allow_symlinks
            and self._contains_symlink(
                candidate
            )
        ):
            raise PermissionError(
                "Path contains a symbolic "
                "link and symbolic links "
                "are disabled."
            )

        allowed = any(
            self._is_within(
                candidate,
                root,
            )
            for root
            in self._roots
        )

        if not allowed:
            raise PermissionError(
                "Path is outside Mary's "
                "configured filesystem "
                "workspace."
            )

        if (
            must_exist
            and not candidate.exists()
        ):
            raise FileNotFoundError(
                f"Path does not exist: "
                f"{candidate}"
            )

        return candidate

    @staticmethod
    def _is_within(
        path: Path,
        root: Path,
    ) -> bool:
        """
        Determine whether path is contained by root.
        """

        try:
            path.relative_to(
                root
            )
            return True
        except ValueError:
            return False

    @staticmethod
    def _contains_symlink(
        path: Path,
    ) -> bool:
        """
        Check path components for symbolic links.

        This is intentionally conservative.
        """

        current = path

        parts = current.parts

        if not parts:
            return False

        if current.is_symlink():
            return True

        # Walk upward toward the filesystem root.
        while current != current.parent:

            if current.is_symlink():
                return True

            current = current.parent

        return False


# ================================================================
# FACTORY
# ================================================================


def create_filesystem_client(
    workspace_roots: list[str | Path] | None = None,
    config: FilesystemConfig | None = None,
) -> FilesystemClient:
    """
    Create a configured filesystem client.

    No filesystem tools are automatically registered.
    """

    if config is None:
        config = FilesystemConfig()

    if workspace_roots:
        for root in workspace_roots:
            config.workspace_roots.append(
                Path(root)
            )

    return FilesystemClient(
        config=config
    )


def register_filesystem_tools(
    registry: ToolRegistry,
    workspace_roots: list[str | Path] | None = None,
    config: FilesystemConfig | None = None,
) -> FilesystemClient:
    """
    Create a filesystem client and register its capabilities.

    Read operations are safe.

    Mutating operations remain approval-gated.
    """

    client = create_filesystem_client(
        workspace_roots=workspace_roots,
        config=config,
    )

    client.register_tools(
        registry
    )

    return client