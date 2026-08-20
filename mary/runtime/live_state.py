"""Compact, safe live character/runtime state for terminal and desktop UI."""

from __future__ import annotations

from typing import Any


def _relationship_label(mary) -> str:
    """Return a deterministic familiarity label without claiming human feeling."""

    try:
        profile_records = len(mary.user_model.get_profile_records(current_only=False))
    except Exception:
        profile_records = 0
    try:
        history_events = int(mary.relationship_history.count())
    except Exception:
        history_events = 0
    try:
        milestones = int(mary.relationship_milestones.count())
    except Exception:
        milestones = 0

    score = profile_records + history_events + (milestones * 3)
    if score >= 40:
        return "Established"
    if score >= 10:
        return "Developing"
    if score > 0:
        return "Familiarizing"
    return "Beginning"


def build_live_character_state(mary, *, runtime_status: str | None = None) -> dict[str, Any]:
    """Build a display-safe snapshot from Mary's authoritative live systems.

    No prompt contents, API keys, raw memory bodies, or private file contents are
    included. The snapshot is intended to be safe for normal UI/terminal status.
    """

    memory = mary.memory.status()
    counts = dict(memory.get("counts", {}) or {})
    total_memories = int(counts.get("episodic", 0)) + int(counts.get("semantic", 0))

    try:
        emotion = dict(mary.emotion.snapshot() or {})
    except Exception:
        emotion = {}
    primary = str(emotion.get("primary", "neutral"))
    intensity = float(emotion.get("intensity", 0.0) or 0.0)
    arousal = float(emotion.get("arousal", 0.0) or 0.0)

    current_task = mary.task_workspace.current()
    last_generation = dict(getattr(mary, "_last_generation_metadata", None) or {})
    resources = (
        mary.llm.resource_governor.status()
        if hasattr(mary.llm, "resource_governor")
        else {"policy": "external_router"}
    )

    status = str(runtime_status or "idle").strip().lower() or "idle"
    if current_task is not None and status == "idle":
        status = "working"

    return {
        "character": {
            "name": str(getattr(mary.personality, "name", "Mary")),
            "continuity": "persistent_capable",
            "relationship": _relationship_label(mary),
            "memory_count": total_memories,
            "mood": primary,
            "mood_intensity": round(intensity, 3),
            "energy": "high" if arousal >= 0.7 else "engaged" if arousal >= 0.35 else "calm",
            "status": status,
            "current_task": current_task.objective if current_task is not None else None,
        },
        "memory": {
            "episodic": int(counts.get("episodic", 0)),
            "semantic": int(counts.get("semantic", 0)),
            "working": int(counts.get("working", 0)),
            "capacities": dict(memory.get("capacities", {}) or {}),
            "recovered_from_backup": bool(
                memory.get("persistence", {}).get("recovered_from_backup", False)
            ),
        },
        "model": {
            "provider": last_generation.get("provider", "local/system"),
            "model": last_generation.get("model", "n/a"),
            "finish_reason": last_generation.get("finish_reason"),
            "routing_strategy": (
                mary.llm.routing_strategy()
                if callable(getattr(mary.llm, "routing_strategy", None))
                else "configured"
            ),
        },
        "resources": resources,
        "orchestration": {
            "task_workspace": mary.task_workspace.status(),
            "last_plan": mary.task_orchestrator.status().get("last_plan"),
        },
        "privacy": {
            "private_route": "ollama_only",
            "paid_expert": "explicit_task_authorization",
        },
        "state_semantics": {
            "mood": "represented_expressive_state_not_claim_of_human_subjective_experience",
            "relationship": "deterministic_familiarity_label_not_human_emotion_claim",
        },
    }


def format_character_card(state: dict[str, Any]) -> str:
    character = dict(state.get("character", {}) or {})
    memory = dict(state.get("memory", {}) or {})
    return "\n".join(
        [
            "MY CHARACTERS",
            "────────────────────────────────",
            str(character.get("name", "Mary")),
            f"Continuity:   {character.get('continuity', 'unknown')}",
            f"Relationship: {character.get('relationship', 'unknown')}",
            f"Memories:     {character.get('memory_count', 0)} "
            f"(episodic {memory.get('episodic', 0)} / semantic {memory.get('semantic', 0)})",
            f"Mood:         {str(character.get('mood', 'neutral')).title()}",
            f"Energy:       {str(character.get('energy', 'calm')).title()}",
            f"Status:       {str(character.get('status', 'idle')).title()}",
            f"Current task: {character.get('current_task') or 'None'}",
        ]
    )
