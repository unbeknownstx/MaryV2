"""Bounded local personal-file search for creator-selected roots."""
from __future__ import annotations
from pathlib import Path
from typing import Iterable, Any

_TEXT_SUFFIXES = {".txt", ".md", ".py", ".json", ".yaml", ".yml", ".csv", ".rpy", ".html", ".css", ".js", ".ts"}
_SKIP = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".pytest_cache"}


class PersonalSearch:
    def __init__(self, roots: Iterable[str | Path] = ()) -> None:
        self.roots: list[Path] = []
        for value in roots: self.add_root(value)

    def add_root(self, value: str | Path) -> None:
        path = Path(value).expanduser().resolve()
        if path.exists() and path.is_dir() and path not in self.roots:
            self.roots.append(path)

    def search(self, query: str, *, limit: int = 30, max_files: int = 1200, max_file_bytes: int = 2_000_000) -> list[dict[str, Any]]:
        needle = " ".join(str(query or "").split()).casefold()
        if not needle: return []
        results: list[dict[str, Any]] = []; scanned = 0
        for root in self.roots:
            for path in root.rglob("*"):
                if scanned >= max_files: break
                if not path.is_file() or any(part in _SKIP for part in path.parts): continue
                scanned += 1
                name_hit = needle in path.name.casefold()
                snippet = ""; content_hit = False
                if path.suffix.lower() in _TEXT_SUFFIXES:
                    try:
                        if path.stat().st_size <= max_file_bytes:
                            text = path.read_text(encoding="utf-8", errors="ignore")
                            idx = text.casefold().find(needle)
                            if idx >= 0:
                                content_hit = True; snippet = " ".join(text[max(0, idx-120):idx+len(needle)+220].split())[:420]
                    except OSError: pass
                if name_hit or content_hit:
                    try: relative = str(path.relative_to(root))
                    except ValueError: relative = path.name
                    results.append({"name": path.name, "relative_path": relative, "root": str(root), "path": str(path),
                                    "kind": path.suffix.lower().lstrip(".") or "file", "snippet": snippet,
                                    "match": "name+content" if name_hit and content_hit else "name" if name_hit else "content"})
                    if len(results) >= limit: return results
        return results
