"""Read-only companion pulse for the MaryV2 desktop.

This module intentionally does not own identity, memory, or task state. It
builds a small bounded view over existing authoritative subsystems so the
Desktop Home surface can answer "what is going on with us right now?" without
asking an LLM or creating another planner.
"""
from __future__ import annotations

from typing import Any


def _clip(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _curiosity_items(mary, limit: int = 3) -> list[dict[str, Any]]:
    try:
        exploring = list(mary.agency.curiosities.get_exploring_curiosities())
        open_items = list(mary.agency.curiosities.get_open_curiosities())
    except Exception:
        return []

    ordered = exploring + [item for item in open_items if item not in exploring]
    results: list[dict[str, Any]] = []
    for item in ordered:
        if not isinstance(item, dict):
            continue
        description = _clip(item.get("description"), 180)
        if not description or str(item.get("source") or "").strip().lower() == "test":
            continue
        try:
            importance = float(item.get("importance", 0.5) or 0.5)
        except (TypeError, ValueError):
            importance = 0.5
        results.append(
            {
                "id": str(item.get("id") or ""),
                "description": description,
                "status": str(item.get("status") or "open"),
                "importance": max(0.0, min(1.0, importance)),
            }
        )
        if len(results) >= max(1, int(limit)):
            break
    return results


def build_companion_pulse(
    mary,
    *,
    command,
    focus,
    study,
    research=None,
    inbox,
    presence,
) -> dict[str, Any]:
    """Return a bounded, display-safe cross-workspace snapshot.

    The pulse contains references and summaries only. It never promotes an
    item into memory, changes Mary's personality, or starts external work.
    """

    command_summary = dict(command.summary() or {})
    focus_state = dict(focus.snapshot() or {})
    study_summary = dict(study.summary() or {})
    research_summary = (
        dict(research.summary() or {})
        if research is not None
        else {}
    )
    inbox_summary = dict(inbox.summary() or {})
    presence_state = dict(presence.snapshot() or {})

    top_tasks = []
    for item in list(command_summary.get("top", []) or [])[:3]:
        if not isinstance(item, dict):
            continue
        top_tasks.append(
            {
                "id": str(item.get("id") or ""),
                "kind": str(item.get("kind") or "task"),
                "title": _clip(item.get("title"), 160),
                "priority": int(item.get("priority", 0) or 0),
                "status": str(item.get("status") or "active"),
            }
        )

    study_projects = []
    for item in list(study_summary.get("project_list", []) or [])[:3]:
        if not isinstance(item, dict):
            continue
        study_projects.append(
            {
                "id": str(item.get("id") or ""),
                "title": _clip(item.get("title"), 160),
                "cards": int(item.get("cards", 0) or 0),
                "due": int(item.get("due", 0) or 0),
            }
        )

    research_threads = []
    for item in list(research_summary.get("recent", []) or [])[:3]:
        if not isinstance(item, dict):
            continue
        research_threads.append(
            {
                "id": str(item.get("id") or ""),
                "title": _clip(item.get("title"), 180),
                "notes": int(item.get("notes", 0) or 0),
            }
        )

    notices = []
    for item in list(inbox_summary.get("recent", []) or [])[:3]:
        if not isinstance(item, dict):
            continue
        try:
            importance = float(item.get("importance", 0.5) or 0.5)
        except (TypeError, ValueError):
            importance = 0.5
        notices.append(
            {
                "id": str(item.get("id") or ""),
                "title": _clip(item.get("title"), 160),
                "category": str(item.get("category") or "general"),
                "importance": max(0.0, min(1.0, importance)),
                "read": bool(item.get("read")),
            }
        )

    thoughts = []
    for item in list(presence_state.get("pending_thoughts", []) or [])[:3]:
        if not isinstance(item, dict):
            continue
        try:
            importance = float(item.get("importance", 0.5) or 0.5)
        except (TypeError, ValueError):
            importance = 0.5
        thoughts.append(
            {
                "id": str(item.get("id") or ""),
                "text": _clip(item.get("text"), 200),
                "context": _clip(item.get("context"), 80),
                "importance": max(0.0, min(1.0, importance)),
            }
        )

    due_count = int(study_summary.get("due", 0) or 0)
    active_tasks = int(command_summary.get("active", 0) or 0)
    unread = int(inbox_summary.get("unread", 0) or 0)
    focus_active = bool(focus_state.get("active"))

    if focus_active:
        headline = "Focus mode is active"
        detail = _clip(focus_state.get("task") or "Mary is keeping the desktop quieter while you work.")
        primary = {"kind": "focus", "label": "Open Focus", "screen": "focus"}
        mode = "focus"
    elif due_count > 0:
        headline = f"{due_count} study review{'s' if due_count != 1 else ''} ready"
        detail = "Pick up a due card or keep talking with Mary."
        primary = {"kind": "study", "label": "Study with Mary", "screen": "study"}
        mode = "companion"
    elif active_tasks > 0:
        headline = f"{active_tasks} active command item{'s' if active_tasks != 1 else ''}"
        detail = top_tasks[0]["title"] if top_tasks else "Your active work is ready in Command Center."
        primary = {"kind": "command", "label": "Open Command Center", "screen": "command"}
        mode = "companion"
    elif unread > 0:
        headline = f"Mary Inbox has {unread} unread item{'s' if unread != 1 else ''}"
        detail = notices[0]["title"] if notices else "There is something waiting without interrupting you."
        primary = {"kind": "presence", "label": "Open Presence", "screen": "stream"}
        mode = "companion"
    else:
        headline = "Nothing urgent is pulling at the system"
        detail = "Talk, create, study, focus, or just hang out."
        primary = {"kind": "chat", "label": "Talk to Mary", "screen": "chat"}
        mode = "companion"

    return {
        "mode": mode,
        "headline": headline,
        "detail": detail,
        "primary_action": primary,
        "counts": {
            "active_tasks": active_tasks,
            "waiting": int(command_summary.get("waiting", 0) or 0),
            "study_due": due_count,
            "study_projects": int(study_summary.get("projects", 0) or 0),
            "research_open": int(research_summary.get("open", 0) or 0),
            "inbox_unread": unread,
            "pending_thoughts": len(thoughts),
        },
        "focus": {
            "active": focus_active,
            "task": _clip(focus_state.get("task"), 180),
            "minutes": int(focus_state.get("minutes", 0) or 0),
            "remaining_seconds": int(focus_state.get("remaining_seconds", 0) or 0),
            "due": bool(focus_state.get("due")),
        },
        "top_tasks": top_tasks,
        "study_projects": study_projects,
        "research_threads": research_threads,
        "notices": notices,
        "pending_thoughts": thoughts,
        "curiosities": _curiosity_items(mary),
        "presence_mode": str(presence_state.get("mode") or "companion"),
        "semantics": (
            "read-only cross-workspace pulse assembled from existing authoritative state; "
            "not memory, not hidden reasoning, and not an autonomous planner"
        ),
    }
