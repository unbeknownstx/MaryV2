"""MaryV2 bounded workspace context for cognition.

This module converts the application-owned MaryEcosystem companion pulse into a
small read-only snapshot that Mary may use during one turn.  The snapshot is
not a new state owner: Command Center, Focus, Study, Research, Inbox, Presence,
and Agency continue to own their own data.
"""

from __future__ import annotations

from typing import Any, Mapping


_SENSITIVE_CONTEXT_KEYS = {
    "audio", "audio_bytes", "raw_audio", "image", "frame", "screenshot",
    "raw_image", "pixels", "base64", "token", "authorization", "api_key",
    "password", "secret",
}


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

    current_source = source.get("current_work")
    current_source = current_source if isinstance(current_source, dict) else {}
    current_work = {
        "active": bool(current_source.get("active")),
        "project": _clip(current_source.get("project"), 120),
        "stage": _clip(current_source.get("stage"), 48),
        "summary": _clip(current_source.get("summary"), 260),
        "authority": "derived_current_work_projection",
        "persistence": "projection_only",
    }
    current_work["recent"] = _items(
        current_source.get("recent"),
        limit=4,
        text_fields={"summary": 240, "project": 120, "stage": 48},
        passthrough=("kind", "source"),
    )
    current_work = {
        key: value for key, value in current_work.items()
        if value not in (None, "", [], {}) or key in {"active", "authority", "persistence"}
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

    scene_source = source.get("live_scene")
    scene_source = scene_source if isinstance(scene_source, dict) else {}
    live_scene: dict[str, Any] = {}
    if scene_source:
        live_scene = {
            "mode": _clip(scene_source.get("mode"), 32),
            "activity": _clip(scene_source.get("activity"), 160),
            "project": _clip(scene_source.get("project"), 160),
            "workspace": _clip(scene_source.get("workspace"), 160),
            "selected_asset": _clip(scene_source.get("selected_asset"), 260),
            "floor_owner": _clip(scene_source.get("floor_owner"), 24),
            "realtime_phase": _clip(scene_source.get("realtime_phase"), 32),
            "mary_target": _clip(scene_source.get("mary_target"), 100),
            "mary_goal": _clip(scene_source.get("mary_goal"), 220),
        }
        environment = scene_source.get("environment")
        if isinstance(environment, dict):
            live_scene["environment"] = {
                _clip(key, 48): _clip(value, 140)
                for key, value in list(environment.items())[:8]
                if _clip(key, 48) and str(key).casefold() not in _SENSITIVE_CONTEXT_KEYS
            }
        live_scene["recent_events"] = _items(
            scene_source.get("recent_events"),
            limit=4,
            text_fields={"summary": 220},
            passthrough=("event_id", "kind", "source"),
            float_fields=("importance",),
        )
        live_scene = {
            key: value for key, value in live_scene.items()
            if value not in (None, "", [], {})
        }

    world_relevant = _items(
        source.get("world_relevant"),
        limit=4,
        text_fields={"topic": 160, "summary": 420, "source": 140, "lane": 48, "url": 360},
        passthrough=("id", "observed_at", "expires_at"),
        float_fields=("confidence",),
    )

    streaming_source = source.get("streaming")
    streaming_source = streaming_source if isinstance(streaming_source, dict) else {}
    streaming: dict[str, Any] = {}
    if streaming_source:
        stats = streaming_source.get("stats")
        chat = streaming_source.get("chat")
        if isinstance(stats, dict):
            streaming["stats"] = {
                key: _bounded_int(stats.get(key))
                for key in ("received", "ignored", "noticed", "respond_candidates")
            }
        if isinstance(chat, dict):
            streaming["buffered"] = _bounded_int(chat.get("buffered"), maximum=100000)
            streaming["repeated_phrases"] = [
                [_clip(pair[0], 100), _bounded_int(pair[1], maximum=100000)]
                for pair in list(chat.get("repeated_phrases") or [])[:4]
                if isinstance(pair, (list, tuple)) and len(pair) >= 2
            ]

    peripheral_awareness = _items(
        source.get("peripheral_awareness"),
        limit=4,
        text_fields={"summary": 260, "source": 48},
        passthrough=("note_id", "created_at", "times_seen"),
        float_fields=("importance",),
    )

    cross_surface_notes = _items(
        source.get("cross_surface_notes"),
        limit=4,
        text_fields={"surface": 64, "direction": 24, "role": 32, "summary": 300},
        passthrough=("note_id", "conversation_id", "created_at"),
    )

    action_windows_source = source.get("action_windows")
    action_windows_source = action_windows_source if isinstance(action_windows_source, dict) else {}
    action_windows: list[dict[str, Any]] = []
    for window in list(action_windows_source.get("windows") or [])[:3]:
        if not isinstance(window, dict):
            continue
        actions = []
        for action in list(window.get("actions") or [])[:10]:
            if not isinstance(action, dict):
                continue
            actions.append({
                "name": _clip(action.get("name"), 80),
                "description": _clip(action.get("description"), 240),
                "capability": _clip(action.get("capability"), 120),
                "disposable": bool(action.get("disposable")),
            })
        item = {
            "window_id": _clip(window.get("window_id"), 120),
            "surface": _clip(window.get("surface"), 64),
            "context": _clip(window.get("context"), 300),
            "revision": _bounded_int(window.get("revision"), maximum=1000000),
            "actions": [value for value in actions if value.get("name")],
        }
        if item["window_id"] and item["actions"]:
            action_windows.append(item)

    has_activity = bool(
        focus["active"]
        or any(counts.values())
        or top_tasks
        or study_projects
        or research_threads
        or productions
        or current_work.get("active")
        or notices
        or pending_thoughts
        or curiosities
        or live_scene
        or world_relevant
        or streaming
        or peripheral_awareness
        or cross_surface_notes
        or action_windows
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
        "current_work": current_work,
        "notices": notices,
        "pending_thoughts": pending_thoughts,
        "curiosities": curiosities,
        "live_scene": live_scene,
        "world_relevant": world_relevant,
        "streaming": streaming,
        "peripheral_awareness": peripheral_awareness,
        "cross_surface_notes": cross_surface_notes,
        "action_windows": action_windows,
        "presence_mode": _clip(source.get("presence_mode"), 32) or "companion",
        "guidance": (
            "Use current workspace state only when it is relevant to the creator's turn. "
            "Do not force project/task references into unrelated conversation. "
            "Live Scene, peripheral awareness, cross-surface notes and world items are ephemeral context, not creator truth or Mary memory. "
            "Cross-surface notes describe what Mary was just doing elsewhere; use them only when relevant. "
            "Action windows list only currently valid high-level actions; selecting one still requires the existing typed capability/tool authorization path. "
            "This snapshot does not prove that Mary performed an action."
        ),
    }
