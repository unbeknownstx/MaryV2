"""Bounded read-only repository orientation for Mary's code tools.

The repository map helps a planner locate likely files/symbols before opening a
specific source file. It never executes source, follows no symlinks, and only
walks FilesystemClient workspace roots.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

from .filesystem import FilesystemClient
from .registry import PermissionLevel, ToolRegistry

VERSION = "13.48"

_SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".swift",
    ".json", ".toml", ".yaml", ".yml", ".sql", ".html", ".css", ".md",
}
_SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", ".next",
    ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache", "coverage",
}
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")
_JS_SYMBOL_RE = re.compile(
    r"(?:^|\n)\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|type)\s+([A-Za-z_$][A-Za-z0-9_$]*)",
    re.MULTILINE,
)
_SWIFT_SYMBOL_RE = re.compile(
    r"(?:^|\n)\s*(?:public\s+|private\s+|internal\s+|final\s+)*(?:class|struct|enum|protocol|func)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)
_RUST_SYMBOL_RE = re.compile(
    r"(?:^|\n)\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:fn|struct|enum|trait|type)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


@dataclass(frozen=True)
class RepositoryMapEntry:
    path: str
    suffix: str
    size: int
    symbols: tuple[str, ...] = ()
    parse_status: str = "not_parsed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "suffix": self.suffix,
            "size": self.size,
            "symbols": list(self.symbols),
            "parse_status": self.parse_status,
        }


class RepositoryMapClient:
    """Create a compact source map under configured workspace roots."""

    def __init__(
        self,
        filesystem: FilesystemClient,
        *,
        max_files_scanned: int = 1200,
        max_file_bytes: int = 256_000,
    ) -> None:
        self.filesystem = filesystem
        self.max_files_scanned = max(50, min(5000, int(max_files_scanned)))
        self.max_file_bytes = max(8_192, min(1_000_000, int(max_file_bytes)))

    @staticmethod
    def _query_tokens(query: str) -> set[str]:
        return {token.casefold() for token in _TOKEN_RE.findall(str(query or ""))}

    @staticmethod
    def _relative(root: Path, path: Path) -> str:
        return path.relative_to(root).as_posix()

    @staticmethod
    def _symbols(path: Path, text: str) -> tuple[tuple[str, ...], str]:
        suffix = path.suffix.casefold()
        symbols: list[str] = []
        if suffix == ".py":
            try:
                tree = ast.parse(text, filename=path.name)
            except SyntaxError:
                return (), "syntax_error"
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name not in symbols:
                        symbols.append(node.name)
                        if len(symbols) >= 48:
                            break
            return tuple(symbols), "parsed"
        pattern = None
        if suffix in {".js", ".jsx", ".ts", ".tsx"}:
            pattern = _JS_SYMBOL_RE
        elif suffix == ".swift":
            pattern = _SWIFT_SYMBOL_RE
        elif suffix == ".rs":
            pattern = _RUST_SYMBOL_RE
        if pattern is None:
            return (), "not_parsed"
        for match in pattern.finditer(text):
            name = match.group(1)
            if name not in symbols:
                symbols.append(name)
            if len(symbols) >= 48:
                break
        return tuple(symbols), "parsed"

    def _iter_source_files(self):
        scanned = 0
        for root in self.filesystem.workspace_roots():
            root = Path(root).resolve()
            for current, dirs, files in os.walk(root, followlinks=False):
                dirs[:] = sorted(
                    name for name in dirs
                    if name not in _SKIP_DIRS
                    and not Path(current, name).is_symlink()
                )
                for name in sorted(files):
                    if scanned >= self.max_files_scanned:
                        return
                    path = Path(current, name)
                    if path.is_symlink() or path.suffix.casefold() not in _SOURCE_SUFFIXES:
                        continue
                    scanned += 1
                    yield root, path

    def build(self, query: str = "", limit: int = 120) -> dict[str, Any]:
        """Return a bounded file/symbol map, optionally ranked by a query."""
        limit = max(1, min(300, int(limit)))
        tokens = self._query_tokens(query)
        ranked: list[tuple[float, RepositoryMapEntry]] = []
        skipped_large = 0
        parse_errors = 0

        for root, path in self._iter_source_files():
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_size > self.max_file_bytes:
                skipped_large += 1
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            symbols, parse_status = self._symbols(path, text)
            if parse_status == "syntax_error":
                parse_errors += 1
            relative = self._relative(root, path)
            entry = RepositoryMapEntry(
                path=relative[:500],
                suffix=path.suffix.casefold()[:20],
                size=max(0, int(stat.st_size)),
                symbols=symbols,
                parse_status=parse_status,
            )
            if not tokens:
                score = 0.0
            else:
                path_words = {token.casefold() for token in _TOKEN_RE.findall(relative)}
                symbol_words = {token.casefold() for symbol in symbols for token in _TOKEN_RE.findall(symbol)}
                exact_symbol = sum(1 for token in tokens if token in symbol_words)
                path_hits = sum(1 for token in tokens if token in path_words or token in relative.casefold())
                if exact_symbol == 0 and path_hits == 0:
                    continue
                score = exact_symbol * 5.0 + path_hits * 2.0
            ranked.append((score, entry))

        ranked.sort(key=lambda pair: (-pair[0], pair[1].path))
        entries = [entry.to_dict() for _score, entry in ranked[:limit]]
        return {
            "version": VERSION,
            "query": str(query or "")[:240],
            "files": entries,
            "returned": len(entries),
            "matched": len(ranked),
            "skipped_large": skipped_large,
            "parse_errors": parse_errors,
            "execution": False,
            "mutation": False,
            "policy": "read-only bounded workspace source orientation; no source execution",
        }


def register_repository_map_tool(
    registry: ToolRegistry,
    *,
    filesystem: FilesystemClient,
) -> RepositoryMapClient:
    client = RepositoryMapClient(filesystem)
    registry.register(
        name="code_repository_map",
        description="Build a bounded read-only map of source files and symbols in the permitted workspace.",
        function=client.build,
        category="code",
        version=VERSION,
        permission_level=PermissionLevel.SAFE,
        external_access=False,
        mutates_state=False,
        parameters={
            "query": {"type": "string", "required": False},
            "limit": {"type": "integer", "required": False},
        },
        metadata={
            "operation": "repository_orientation",
            "execution": False,
            "mutation": False,
        },
    )
    return client
