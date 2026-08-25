"""Display-safe dashboard state for the MaryV2 desktop shell.

The dashboard is a *view* over Mary's canonical systems.  It never owns or
persists identity, memory, relationship, emotion, agency, provider, or project
state.  This module deliberately builds bounded presentation payloads so the
frontend can feel rich without exposing API keys, prompts, raw provider
responses, or unbounded private files.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from mary.relationship.provenance import text_has_test_probe_marker
from mary.runtime.live_state import build_live_character_state


_MAX_TEXT = 180
_MAX_HIGHLIGHTS = 6
_MAX_ACTIVITIES = 8
_MAX_CURIOSITIES = 6
_MAX_TRAITS = 8
_MAX_VALUES = 6
_MAX_PREFERENCES = 8


def _clip(value: Any, limit: int = _MAX_TEXT) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _safe_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _iso_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _relative_label(timestamp: Any) -> str:
    """Return a coarse relative timestamp without requiring frontend parsing."""

    raw = str(timestamp or "").strip()
    if not raw:
        return "recently"

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age = max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return "recently"

    if age < 60:
        return "just now"
    if age < 3600:
        return f"{max(1, int(age // 60))}m ago"
    if age < 86400:
        return f"{max(1, int(age // 3600))}h ago"
    if age < 604800:
        return f"{max(1, int(age // 86400))}d ago"
    return parsed.date().isoformat()


def _connection_index(mary) -> dict[str, Any]:
    """Build a deterministic continuity index, not a claim of human feeling."""

    try:
        records = len(mary.user_model.get_profile_records(current_only=True))
    except Exception:
        records = 0
    try:
        history = int(mary.relationship_history.count())
    except Exception:
        history = 0
    try:
        milestones = int(mary.relationship_milestones.count())
    except Exception:
        milestones = 0

    # Saturates gradually.  The number is a UI continuity index only and the
    # semantics field below makes that explicit to future surfaces.
    score = min(100, round((records * 2.0) + (history * 1.2) + (milestones * 8.0)))
    if score >= 85:
        label = "Deep continuity"
    elif score >= 60:
        label = "Established"
    elif score >= 30:
        label = "Developing"
    elif score > 0:
        label = "Getting familiar"
    else:
        label = "Beginning"

    return {
        "score": score,
        "label": label,
        "profile_records": records,
        "history_events": history,
        "milestones": milestones,
        "semantics": "derived relationship-continuity index; not a claim of human affection",
    }


def _memory_highlights(mary) -> list[dict[str, Any]]:
    """Use current, source-aware creator profile records as safe highlights."""

    try:
        records = list(mary.user_model.get_profile_records(current_only=True))
    except Exception:
        records = []

    records.sort(
        key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""),
        reverse=True,
    )

    results: list[dict[str, Any]] = []
    for item in records:
        value = _clip(item.get("value"))
        if not value or text_has_test_probe_marker(value):
            continue
        category = str(item.get("category") or "memory").strip().lower()
        key = _clip(item.get("key"), 72)
        results.append(
            {
                "id": str(item.get("id") or f"profile-{len(results)}"),
                "category": category,
                "label": category.replace("_", " ").title(),
                "title": value,
                "key": key,
                "confidence": round(_safe_number(item.get("confidence"), 1.0), 3),
                "explicitly_shared": bool(item.get("explicitly_shared")),
                "updated_at": _iso_or_none(item.get("updated_at")),
            }
        )
        if len(results) >= _MAX_HIGHLIGHTS:
            break

    return results


def _recent_activities(mary) -> list[dict[str, Any]]:
    candidates: list[tuple[str, dict[str, Any]]] = []

    try:
        for event in mary.relationship_history.get_recent(limit=12):
            description = _clip(event.get("description"))
            if not description or text_has_test_probe_marker(description):
                continue
            candidates.append(
                (
                    str(event.get("created_at") or ""),
                    {
                        "kind": str(event.get("type") or "relationship"),
                        "title": description,
                        "timestamp": _iso_or_none(event.get("created_at")),
                    },
                )
            )
    except Exception:
        pass

    try:
        for milestone in mary.relationship_milestones.get_recent(limit=8):
            title = _clip(milestone.get("title") or milestone.get("description"))
            if not title or text_has_test_probe_marker(title):
                continue
            candidates.append(
                (
                    str(milestone.get("created_at") or ""),
                    {
                        "kind": "milestone",
                        "title": title,
                        "timestamp": _iso_or_none(milestone.get("created_at")),
                    },
                )
            )
    except Exception:
        pass

    try:
        for decision in mary.agency.decisions.get_recent(count=6):
            data = decision.to_dict() if hasattr(decision, "to_dict") else {}
            title = _clip(data.get("description") or data.get("decision") or data.get("content"))
            if not title or text_has_test_probe_marker(title):
                continue
            candidates.append(
                (
                    str(data.get("updated_at") or data.get("created_at") or ""),
                    {
                        "kind": "decision",
                        "title": title,
                        "timestamp": _iso_or_none(data.get("updated_at") or data.get("created_at")),
                    },
                )
            )
    except Exception:
        pass

    candidates.sort(key=lambda item: item[0], reverse=True)
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, item in candidates:
        key = item["title"].casefold()
        if key in seen:
            continue
        seen.add(key)
        item["when"] = _relative_label(item.get("timestamp"))
        output.append(item)
        if len(output) >= _MAX_ACTIVITIES:
            break
    return output


def _curiosities(mary) -> list[dict[str, Any]]:
    try:
        exploring = list(mary.agency.curiosities.get_exploring_curiosities())
        open_items = list(mary.agency.curiosities.get_open_curiosities())
    except Exception:
        return []

    active = exploring + [item for item in open_items if item not in exploring]
    active.sort(
        key=lambda item: (
            _safe_number(item.get("importance")),
            str(item.get("updated_at") or item.get("created_at") or ""),
        ),
        reverse=True,
    )

    output: list[dict[str, Any]] = []
    for item in active:
        description = _clip(item.get("description"))
        if not description or str(item.get("source") or "").strip().lower() == "test":
            continue
        output.append(
            {
                "id": str(item.get("id") or ""),
                "description": description,
                "status": str(item.get("status") or "open"),
                "importance": round(_safe_number(item.get("importance"), 0.5), 3),
                "source": str(item.get("source") or "unknown"),
            }
        )
        if len(output) >= _MAX_CURIOSITIES:
            break
    return output


def _personality(mary) -> dict[str, Any]:
    try:
        traits = dict(mary.personality.get_traits() or {})
    except Exception:
        traits = {}
    trait_items = sorted(traits.items(), key=lambda item: _safe_number(item[1]), reverse=True)[:_MAX_TRAITS]

    try:
        values = list(mary.values.get_priorities(limit=_MAX_VALUES))
    except Exception:
        values = []

    try:
        preferences = list(mary.preferences.get_strongest(limit=_MAX_PREFERENCES))
    except TypeError:
        try:
            preferences = list(mary.preferences.get_strongest())[:_MAX_PREFERENCES]
        except Exception:
            preferences = []
    except Exception:
        preferences = []

    safe_preferences: list[dict[str, Any]] = []
    for item in preferences:
        if not isinstance(item, dict):
            continue
        name = _clip(item.get("name") or item.get("key") or item.get("value"), 96)
        if not name:
            continue
        safe_preferences.append(
            {
                "name": name,
                "category": str(item.get("category") or "general"),
                "polarity": round(_safe_number(item.get("polarity")), 3),
                "strength": round(_safe_number(item.get("strength"), 0.5), 3),
            }
        )

    return {
        "traits": [
            {"name": str(name), "value": round(_safe_number(value), 3)}
            for name, value in trait_items
        ],
        "values": [
            {
                "name": str(item.get("name") or "value"),
                "strength": round(_safe_number(item.get("strength"), 0.5), 3),
                "description": _clip(item.get("description"), 140),
            }
            for item in values
            if isinstance(item, dict)
        ],
        "preferences": safe_preferences,
    }


def _provider_state(mary) -> dict[str, Any]:
    try:
        environment = dict(mary.runtime_environment.snapshot() or {})
    except Exception:
        environment = {}

    providers = []
    for name, info in dict(environment.get("providers", {}) or {}).items():
        if not isinstance(info, dict):
            continue
        providers.append(
            {
                "name": str(name),
                "available": bool(info.get("available")),
                "model": str(info.get("model") or "unknown"),
            }
        )

    return {
        "host": str(environment.get("host_type") or "unknown"),
        "platform": str(environment.get("platform") or "unknown"),
        "conversation_policy": list(environment.get("conversation_policy", []) or []),
        "effective_conversation_route": list(environment.get("effective_conversation_route", []) or []),
        "task_policy": list(environment.get("task_policy", []) or []),
        "effective_task_route": list(environment.get("effective_task_route", []) or []),
        "providers": providers,
    }


def build_desktop_dashboard_state(
    mary,
    *,
    runtime_status: str | None = None,
) -> dict[str, Any]:
    """Return the complete bounded payload used by the game-like desktop shell."""

    live = build_live_character_state(mary, runtime_status=runtime_status)
    try:
        emotion = dict(mary.emotion.snapshot() or {})
    except Exception:
        emotion = {}

    return {
        "live": live,
        "emotion": {
            "primary": str(emotion.get("primary") or "neutral"),
            "intensity": round(_safe_number(emotion.get("intensity")), 3),
            "intensity_level": str(emotion.get("intensity_level") or "very_low"),
            "valence": round(_safe_number(emotion.get("valence")), 3),
            "arousal": round(_safe_number(emotion.get("arousal")), 3),
            "secondary": {
                str(key): round(_safe_number(value), 3)
                for key, value in dict(emotion.get("secondary", {}) or {}).items()
            },
        },
        "relationship": _connection_index(mary),
        "memory_highlights": _memory_highlights(mary),
        "recent_activities": _recent_activities(mary),
        "curiosities": _curiosities(mary),
        "personality": _personality(mary),
        "growth": mary.growth.status() if hasattr(mary, "growth") else {},
        "engagement": mary.engagement.status() if hasattr(mary, "engagement") else {},
        "realtime": mary.realtime.status() if hasattr(mary, "realtime") else {},
        "nodes": mary.node_registry.snapshot() if hasattr(mary, "node_registry") else {},
        "retrieval": (mary.mind.retrieval.status() if hasattr(getattr(mary, "mind", None), "retriever") else {}),
        "perception": mary.perception_director.snapshot() if hasattr(mary, "perception_director") else {},
        "training_feedback": mary.training_feedback.status() if hasattr(mary, "training_feedback") else {},
        "providers": _provider_state(mary),
        "agency": {
            "active_goals": int(mary.agency.goals.count_active()),
            "active_intentions": int(mary.agency.intentions.count_active()),
            "pending_intentions": int(mary.agency.intentions.count_pending()),
            "open_curiosities": int(mary.agency.curiosities.count_open()),
            "exploring_curiosities": int(mary.agency.curiosities.count_exploring()),
        },
        "paths": {
            "data_root": str(mary.config.paths.data),
            "workspace_root": str(mary.config.paths.workspace),
        },
        "semantics": {
            "emotion": "Mary's represented expressive state; not a claim of human subjective experience",
            "relationship_score": "derived continuity/familiarity index for UI presentation",
            "memory_highlights": "current source-aware creator profile items, not arbitrary raw episodic memory",
        },
    }
