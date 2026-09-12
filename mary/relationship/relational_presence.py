"""Relational presence for MaryV2 13.8.

Durable relationship mode and completed shared activities are represented
through the existing canonical RelationshipManager/history. Active activities
and proactive-presence proposals remain bounded process-local state. The social
graph is a read-only derived projection.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

RELATIONSHIP_MODES = ("friend", "close", "romantic", "partner")
RELATIONAL_GUARDRAILS = (
    "no_exclusivity_demands",
    "no_guilt_for_absence",
    "no_fake_physical_suffering",
    "no_engagement_streak_pressure",
    "no_romance_as_identity_fork",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(text: Any, limit: int = 1200) -> str:
    return str(text or "").strip()[:limit]


@dataclass
class SharedActivity:
    activity_type: str
    title: str
    id: str = field(default_factory=lambda: f"activity_{uuid.uuid4().hex[:12]}")
    started_at: str = field(default_factory=_now)
    context: str = ""
    notable_moments: list[str] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "activity_type": self.activity_type,
            "title": self.title,
            "started_at": self.started_at,
            "context": self.context,
            "notable_moments": list(self.notable_moments),
        }


@dataclass(frozen=True)
class PresenceProposal:
    kind: str
    reason: str
    message_hint: str
    priority: float
    created_at: str

    def snapshot(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "reason": self.reason,
            "message_hint": self.message_hint,
            "priority": self.priority,
            "created_at": self.created_at,
        }


class RelationalPresenceRuntime:
    """Bounded shared-life behavior over the canonical relationship owner."""

    def __init__(self, relationship_manager: Any, *, proposal_capacity: int = 16) -> None:
        self.relationship = relationship_manager
        self.active_activity: SharedActivity | None = None
        self._proposals: deque[PresenceProposal] = deque(maxlen=max(1, min(64, proposal_capacity)))

    def relationship_mode(self) -> str:
        history = getattr(self.relationship, "history", None)
        events = list(getattr(history, "events", []) or [])
        for event in reversed(events):
            if event.get("type") != "relationship_mode_changed":
                continue
            mode = str((event.get("metadata") or {}).get("mode", "")).lower()
            if mode in RELATIONSHIP_MODES:
                return mode
        return "friend"

    def set_relationship_mode(self, mode: str, *, source: str = "creator_explicit") -> dict[str, Any]:
        normalized = str(mode or "").strip().lower()
        if normalized not in RELATIONSHIP_MODES:
            raise ValueError(f"relationship mode must be one of {RELATIONSHIP_MODES}")
        previous = self.relationship_mode()
        if normalized == previous:
            return {"mode": normalized, "previous": previous, "changed": False}
        event = self.relationship.history.record(
            "relationship_mode_changed",
            f"Relationship mode changed from {previous} to {normalized}.",
            importance=0.9,
            source=source,
            metadata={"mode": normalized, "previous": previous},
        )
        self.relationship.save()
        return {"mode": normalized, "previous": previous, "changed": True, "event_id": event.get("id")}

    def start_activity(self, activity_type: str, title: str, *, context: str = "") -> dict[str, Any]:
        if self.active_activity is not None:
            raise RuntimeError("a shared activity is already active")
        activity_type = _clip(activity_type, 64).lower() or "shared"
        title = _clip(title, 240)
        if not title:
            raise ValueError("activity title cannot be empty")
        self.active_activity = SharedActivity(activity_type=activity_type, title=title, context=_clip(context))
        return self.active_activity.snapshot()

    def note_activity(self, note: str) -> dict[str, Any]:
        if self.active_activity is None:
            raise RuntimeError("no shared activity is active")
        note = _clip(note, 480)
        if note and note not in self.active_activity.notable_moments:
            self.active_activity.notable_moments.append(note)
            del self.active_activity.notable_moments[:-12]
        return self.active_activity.snapshot()

    def complete_activity(self, *, summary: str = "", importance: float = 0.8) -> dict[str, Any]:
        if self.active_activity is None:
            raise RuntimeError("no shared activity is active")
        activity = self.active_activity
        description = _clip(summary, 900) or f"Mary and her creator shared: {activity.title}"
        event = self.relationship.history.record_shared_experience(
            description,
            importance=max(0.0, min(1.0, float(importance))),
            metadata={
                "activity_id": activity.id,
                "activity_type": activity.activity_type,
                "title": activity.title,
                "started_at": activity.started_at,
                "completed_at": _now(),
                "context": activity.context,
                "notable_moments": list(activity.notable_moments),
            },
        )
        self.active_activity = None
        self.relationship.save()
        return event

    def cancel_activity(self) -> dict[str, Any] | None:
        if self.active_activity is None:
            return None
        snapshot = self.active_activity.snapshot()
        self.active_activity = None
        return snapshot

    def propose_presence(self, reason: str, *, kind: str = "check_in", message_hint: str = "", priority: float = 0.5) -> dict[str, Any]:
        proposal = PresenceProposal(
            kind=_clip(kind, 64) or "check_in",
            reason=_clip(reason, 480),
            message_hint=_clip(message_hint, 480),
            priority=max(0.0, min(1.0, float(priority))),
            created_at=_now(),
        )
        if not proposal.reason:
            raise ValueError("presence proposal reason cannot be empty")
        self._proposals.append(proposal)
        return proposal.snapshot()

    def pending_proposals(self) -> list[dict[str, Any]]:
        return [p.snapshot() for p in sorted(self._proposals, key=lambda item: item.priority, reverse=True)]

    def pop_next_proposal(self, *, minimum_priority: float = 0.0) -> dict[str, Any] | None:
        eligible = [p for p in self._proposals if p.priority >= minimum_priority]
        if not eligible:
            return None
        chosen = max(eligible, key=lambda p: (p.priority, p.created_at))
        self._proposals.remove(chosen)
        return chosen.snapshot()

    def social_graph(self, *, recent_experience_limit: int = 24) -> dict[str, Any]:
        profile = self.relationship.profile() if callable(getattr(self.relationship, "profile", None)) else {}
        creator_name = str((profile.get("identity") or {}).get("name") or "creator")
        nodes = [
            {"id": "mary", "type": "person", "label": "Mary"},
            {"id": "creator", "type": "person", "label": creator_name},
        ]
        edges: list[dict[str, Any]] = [
            {"from": "mary", "to": "creator", "type": "relationship", "mode": self.relationship_mode()}
        ]
        for group, values in (("interest", list(profile.get("interests") or [])[:16]), ("goal", list(profile.get("goals") or [])[:16])):
            for index, value in enumerate(values):
                node_id = f"{group}_{index}"
                nodes.append({"id": node_id, "type": group, "label": _clip(value, 180)})
                edges.append({"from": "creator", "to": node_id, "type": f"has_{group}"})
        for index, (key, value) in enumerate(list(dict(profile.get("preferences") or {}).items())[:20]):
            node_id = f"preference_{index}"
            nodes.append({"id": node_id, "type": "preference", "label": f"{_clip(key, 80)}: {_clip(value, 120)}"})
            edges.append({"from": "creator", "to": node_id, "type": "prefers"})
        experiences = self.relationship.history.get_shared_experiences()[-max(0, recent_experience_limit):]
        for index, event in enumerate(experiences):
            node_id = f"experience_{index}"
            nodes.append({"id": node_id, "type": "shared_experience", "label": _clip(event.get("description"), 220)})
            edges.append({"from": "mary", "to": node_id, "type": "shared"})
            edges.append({"from": "creator", "to": node_id, "type": "shared"})
        return {"nodes": nodes, "edges": edges, "authority": "derived_projection_only", "source": "canonical_relationship_state"}

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": "13.8",
            "relationship_mode": self.relationship_mode(),
            "active_activity": self.active_activity.snapshot() if self.active_activity else None,
            "pending_presence_proposals": self.pending_proposals(),
            "guardrails": list(RELATIONAL_GUARDRAILS),
            "authority": "relationship history is canonical; active/proposal state is ephemeral",
        }
