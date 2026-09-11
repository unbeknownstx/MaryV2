"""MaryV2 - bounded current-work projection.

This module does not create a new project database.  It derives a tiny,
display/prompt-safe view from Mary's existing canonical workspace and durable
shared-work relationship history so every surface can answer "what are we
working on?" without asking a model to guess.
"""
from __future__ import annotations

import re
from typing import Any, Mapping


def _clip(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _project_label(texts: list[str]) -> str:
    joined = " ".join(texts).casefold()
    mary_runtime_terms = ("core", "iphone", "ios", "mac", "node", "app", "voice", "resident hearing")
    if (
        "maryv2" in joined
        or (re.search(r"\bmary\b", joined) and any(word in joined for word in mary_runtime_terms))
        or "capability node" in joined
        or "iphone app" in joined
        or ("core" in joined and "node" in joined)
    ):
        return "MaryV2"
    if "unbeknownst" in joined:
        return "Unbeknownst"
    return "Shared work"


def _workspace_candidates(workspace: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    source = dict(workspace or {})
    values: list[dict[str, Any]] = []

    # Raw workspace snapshot shape.
    production = source.get("production")
    if isinstance(production, dict):
        for item in list(production.get("recent") or [])[:4]:
            if not isinstance(item, dict):
                continue
            title = _clip(item.get("title"), 180)
            if title:
                values.append({
                    "summary": title,
                    "kind": "production",
                    "project": title,
                    "stage": _clip(item.get("stage"), 48),
                    "source": "workspace.production",
                })

    command = source.get("command")
    if isinstance(command, dict):
        for item in list(command.get("items") or command.get("top") or [])[:4]:
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "active").casefold() == "done":
                continue
            title = _clip(item.get("title"), 180)
            if title:
                values.append({
                    "summary": title,
                    "kind": str(item.get("kind") or "task")[:48],
                    "project": "",
                    "stage": str(item.get("status") or "active")[:48],
                    "source": "workspace.command",
                })

    focus = source.get("focus")
    if isinstance(focus, dict) and bool(focus.get("active")):
        task = _clip(focus.get("task") or "Focus session", 180)
        values.insert(0, {
            "summary": task,
            "kind": "focus",
            "project": "",
            "stage": "active",
            "source": "workspace.focus",
        })

    # Sanitized companion/workspace-context shape.
    for item in list(source.get("productions") or [])[:4]:
        if not isinstance(item, dict):
            continue
        title = _clip(item.get("title"), 180)
        if title:
            values.append({
                "summary": title,
                "kind": "production",
                "project": title,
                "stage": _clip(item.get("stage"), 48),
                "source": "workspace_context.production",
            })
    for item in list(source.get("top_tasks") or [])[:4]:
        if not isinstance(item, dict):
            continue
        title = _clip(item.get("title"), 180)
        if title:
            values.append({
                "summary": title,
                "kind": str(item.get("kind") or "task")[:48],
                "project": "",
                "stage": str(item.get("status") or "active")[:48],
                "source": "workspace_context.command",
            })

    return values


def build_current_work_projection(
    mary: Any,
    workspace: Mapping[str, Any] | None = None,
    *,
    limit: int = 6,
) -> dict[str, Any]:
    """Derive one bounded current-work view from existing authoritative state.

    The result is a projection only: it cannot mutate relationship history,
    workspace state, memory, identity, or agency.
    """

    candidates = _workspace_candidates(workspace)
    seen: set[str] = set()
    recent: list[dict[str, Any]] = []

    def add(summary: Any, *, source: str, kind: str = "shared_work", project: str = "", stage: str = "") -> None:
        text = _clip(summary, 260)
        key = text.casefold()
        if not text or key in seen:
            return
        seen.add(key)
        recent.append({
            "summary": text,
            "source": source,
            "kind": _clip(kind, 48),
            "project": _clip(project, 120),
            "stage": _clip(stage, 48),
        })

    for item in candidates:
        add(
            item.get("summary"),
            source=str(item.get("source") or "workspace"),
            kind=str(item.get("kind") or "work"),
            project=str(item.get("project") or ""),
            stage=str(item.get("stage") or ""),
        )

    # Relationship shared-work history is durable creator-owned evidence.
    try:
        events = list(mary.relationship_history.get_recent(limit=32))
    except Exception:
        events = []
    for event in events:
        if not isinstance(event, dict):
            continue
        meta = event.get("metadata")
        meta = meta if isinstance(meta, dict) else {}
        if str(event.get("type") or "").casefold() != "shared_experience" or meta.get("kind") != "shared_work":
            continue
        summary = event.get("description")
        if meta.get("owner") == "creator" and callable(getattr(mary, "_render_creator_owned_shared_work", None)):
            summary = mary._render_creator_owned_shared_work(summary)
        add(summary, source="relationship.shared_work")

    # Milestones are allowed as supporting context, but never outrank explicit
    # active workspace items or shared-work events.
    try:
        milestones = list(mary.relationship_milestones.get_recent(limit=8))
    except Exception:
        milestones = []
    for item in milestones:
        if isinstance(item, dict):
            add(item.get("description") or item.get("title"), source="relationship.milestone", kind="milestone")

    recent = recent[: max(1, int(limit))]
    summaries = [str(item.get("summary") or "") for item in recent if item.get("summary")]
    project = next((str(item.get("project") or "") for item in recent if item.get("project")), "")
    if not project and summaries:
        project = _project_label(summaries)
    stage = next((str(item.get("stage") or "") for item in recent if item.get("stage")), "")

    return {
        "active": bool(recent),
        "project": project or "",
        "stage": stage or ("current" if recent else "idle"),
        "summary": summaries[0] if summaries else "",
        "recent": recent,
        "sources": sorted({str(item.get("source") or "") for item in recent if item.get("source")}),
        "authority": "derived_current_work_projection",
        "persistence": "projection_only",
        "semantics": (
            "derived from canonical workspace/shared-work evidence; context/display only; "
            "never identity, memory, relationship, or execution authority"
        ),
    }
