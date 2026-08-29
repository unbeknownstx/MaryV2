"""MaryV2 bounded workspace context for cognition.

This module converts the application-owned MaryEcosystem companion pulse into a
small read-only snapshot that Mary may use during one turn.  The snapshot is
not a new state owner: Command Center, Focus, Study, Research, Inbox, Presence,
and Agency continue to own their own data.
"""

from __future__ import annotations

from typing import Any, Mapping


def _clip(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _bounded_int(value: Any, *, minimum: int = 0, maximum: int = 100000) -> int:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        number = 0
    return max(minimum, min(maximum, number))


def _bounded_float(value: Any) -> float:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        number = 0.0
    return max(0.0, min(1.0, number))


def _items(
    raw: Any,
    *,
    limit: int,
    text_fields: Mapping[str, int],
    passthrough: tuple[str, ...] = (),
    integer_fields: tuple[str, ...] = (),
    float_fields: tuple[str, ...] = (),
    boolean_fields: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []

    for item in list(raw or [])[: max(0, int(limit))]:
        if not isinstance(item, dict):
            continue

        value: dict[str, Any] = {}

        for key, text_limit in text_fields.items():
            text = _clip(item.get(key), text_limit)
            if text:
                value[key] = text

        for key in passthrough:
            raw_value = item.get(key)
            if raw_value not in (None, "", [], {}):
                value[key] = str(raw_value)[:120]

        for key in integer_fields:
            value[key] = _bounded_int(item.get(key))

        for key in float_fields:
            value[key] = _bounded_float(item.get(key))

        for key in boolean_fields:
            value[key] = bool(item.get(key))

        if value:
            values.append(value)

    return values


def build_workspace_context(
    pulse: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a cognition-safe view of one canonical companion pulse.

    Only known fields are copied.  This keeps UI-only data and arbitrary
    metadata out of Mary's prompt while preserving useful current-work context.
    """

    source = dict(pulse or {})
    counts_source = source.get("counts")
    counts_source = counts_source if isinstance(counts_source, dict) else {}

    counts = {
        "active_tasks": _bounded_int(counts_source.get("active_tasks")),
        "waiting": _bounded_int(counts_source.get("waiting")),
        "study_due": _bounded_int(counts_source.get("study_due")),
        "study_projects": _bounded_int(counts_source.get("study_projects")),
        "research_open": _bounded_int(counts_source.get("research_open")),
        "production_projects": _bounded_int(counts_source.get("production_projects")),
        "inbox_unread": _bounded_int(counts_source.get("inbox_unread")),
        "pending_thoughts": _bounded_int(counts_source.get("pending_thoughts")),
    }

    focus_source = source.get("focus")
    focus_source = focus_source if isinstance(focus_source, dict) else {}
    focus = {
        "active": bool(focus_source.get("active")),
        "task": _clip(focus_source.get("task"), 180),
        "minutes": _bounded_int(focus_source.get("minutes"), maximum=24 * 60),
        "remaining_seconds": _bounded_int(
            focus_source.get("remaining_seconds"),
            maximum=7 * 24 * 60 * 60,
        ),
        "due": bool(focus_source.get("due")),
    }

    top_tasks = _items(
        source.get("top_tasks"),
        limit=3,
        text_fields={"title": 160},
        passthrough=("id", "kind", "status"),
        integer_fields=("priority",),
    )

    study_projects = _items(
        source.get("study_projects"),
        limit=3,
        text_fields={"title": 160},
        passthrough=("id",),
        integer_fields=("cards", "due"),
    )

    research_threads = _items(
        source.get("research_threads"),
        limit=3,
        text_fields={"title": 180},
        passthrough=("id",),
        integer_fields=("notes",),
    )

    productions = _items(
        source.get("productions"),
        limit=3,
        text_fields={"title": 180},
        passthrough=("id", "stage", "format"),
        integer_fields=("shots", "assets"),
    )

    notices = _items(
        source.get("notices"),
        limit=2,
        text_fields={"title": 160},
        passthrough=("id", "category"),
        float_fields=("importance",),
        boolean_fields=("read",),
    )

    pending_thoughts = _items(
        source.get("pending_thoughts"),
        limit=2,
        text_fields={"text": 200, "context": 80},
        passthrough=("id",),
        float_fields=("importance",),
    )

    curiosities = _items(
        source.get("curiosities"),
        limit=2,
        text_fields={"description": 180},
        passthrough=("id", "status"),
        float_fields=("importance",),
    )

    has_activity = bool(
        focus["active"]
        or any(counts.values())
        or top_tasks
        or study_projects
        or research_threads
        or productions
        or notices
        or pending_thoughts
        or curiosities
    )

    if not has_activity:
        return {}

    return {
        "authority": "canonical_workspace_context",
        "snapshot_persistence": "ephemeral",
        "mode": _clip(source.get("mode"), 32) or "companion",
        "headline": _clip(source.get("headline"), 180),
        "detail": _clip(source.get("detail"), 220),
        "counts": counts,
        "focus": focus,
        "top_tasks": top_tasks,
        "study_projects": study_projects,
        "research_threads": research_threads,
        "productions": productions,
        "notices": notices,
        "pending_thoughts": pending_thoughts,
        "curiosities": curiosities,
        "presence_mode": _clip(source.get("presence_mode"), 32) or "companion",
        "guidance": (
            "Use current workspace state only when it is relevant to the creator's turn. "
            "Do not force project/task references into unrelated conversation. "
            "This snapshot is not memory and does not prove that Mary performed an action."
        ),
    }
