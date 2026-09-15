"""Read-only discovery of recoverable local Mary continuity state.

Remote Mary Core is canonical, but older standalone/Desktop builds may have left
valid creator-owned state under a Windows/macOS application data root or the
historical repository ``data`` directory.  This module never imports, merges,
or rewrites that state.  It only reports content-free counts so the creator can
see whether an older root is worth reviewing before an explicit recovery.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, dict) else {}


def _list_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _dict_count(value: Any) -> int:
    return len(value) if isinstance(value, dict) else 0


def _relationship_counts(payload: dict[str, Any]) -> dict[str, int]:
    """Extract only coarse counts across old/new relationship schemas."""

    history = payload.get("history", {})
    milestones = payload.get("milestones", {})
    user_model = payload.get("user_model", payload.get("profile", {}))

    history_count = 0
    if isinstance(history, list):
        history_count = len(history)
    elif isinstance(history, dict):
        for key in ("events", "history", "records", "items"):
            if isinstance(history.get(key), list):
                history_count = max(history_count, len(history[key]))

    milestone_count = 0
    if isinstance(milestones, list):
        milestone_count = len(milestones)
    elif isinstance(milestones, dict):
        for key in ("milestones", "records", "items"):
            if isinstance(milestones.get(key), list):
                milestone_count = max(milestone_count, len(milestones[key]))

    profile_count = 0
    if isinstance(user_model, list):
        profile_count = len(user_model)
    elif isinstance(user_model, dict):
        for key in ("profile_records", "records", "history"):
            if isinstance(user_model.get(key), list):
                profile_count = max(profile_count, len(user_model[key]))
        if not profile_count:
            for key in ("preferences", "facts", "communication_style"):
                profile_count += _dict_count(user_model.get(key))
            for key in ("interests", "goals", "values", "general"):
                profile_count += _list_count(user_model.get(key))

    return {
        "relationship_history": history_count,
        "relationship_milestones": milestone_count,
        "creator_profile_records": profile_count,
    }


def inspect_continuity_root(root: str | Path) -> dict[str, Any]:
    """Return content-free continuity counts for one possible Mary data root."""

    path = Path(root).expanduser().resolve()
    memory_path = path / "memory" / "memory.json"
    relationship_path = path / "relationship" / "relationship.json"
    developed_self_path = path / "personality" / "developed_self.json"
    journal_path = path / "development" / "experience_journal.json"

    memory = _load_json(memory_path)
    relationship = _load_json(relationship_path)
    developed = _load_json(developed_self_path)
    journal = _load_json(journal_path)

    relationship_counts = _relationship_counts(relationship)
    counts = {
        "episodic": _list_count(memory.get("episodic")),
        "semantic": _list_count(memory.get("semantic")),
        **relationship_counts,
        "developed_preferences": _list_count(developed.get("developed_preferences")),
        "growth_entries": max(
            _list_count(journal.get("entries")),
            _list_count(journal.get("experiences")),
            _list_count(journal.get("events")),
        ),
    }
    existing_files = sum(
        int(item.is_file())
        for item in (memory_path, relationship_path, developed_self_path, journal_path)
    )
    return {
        "root": str(path),
        "exists": path.is_dir(),
        "state_files": existing_files,
        "counts": counts,
        "continuity_records": sum(counts.values()),
        "recoverable_candidate": bool(existing_files and sum(counts.values()) > 0),
        "read_only": True,
    }


def candidate_continuity_roots(project_root: str | Path) -> list[Path]:
    """Return bounded conventional local roots without crawling the machine."""

    project = Path(project_root).expanduser().resolve()
    candidates: list[Path] = []

    explicit = os.getenv("MARY_DATA_DIR", "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())

    if os.name == "nt":
        local_app_data = os.getenv("LOCALAPPDATA", "").strip()
        app_data = os.getenv("APPDATA", "").strip()
        if local_app_data:
            candidates.append(Path(local_app_data) / "MaryV2" / "data")
        if app_data:
            candidates.append(Path(app_data) / "MaryV2" / "data")
    else:
        candidates.extend(
            (
                Path.home() / "Library" / "Application Support" / "MaryV2" / "data",
                Path.home() / ".local" / "share" / "MaryV2" / "data",
            )
        )

    candidates.extend((project / "data", project / ".data"))

    output: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = os.path.normcase(str(resolved))
        if key in seen:
            continue
        seen.add(key)
        output.append(resolved)
    return output


def discover_local_continuity(project_root: str | Path) -> list[dict[str, Any]]:
    return [inspect_continuity_root(path) for path in candidate_continuity_roots(project_root)]
