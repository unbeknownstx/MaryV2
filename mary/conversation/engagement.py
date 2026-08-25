"""Adaptive intentional-conversation state for MaryV2 13.0.

This module solves a specific V2 tradeoff: low-latency reflexes are useful, but
Mary should not flatten an explicitly invited conversation into a sequence of
isolated short replies.  Engagement is a small, deterministic state machine
that sits above response generation and below identity/memory.

It never invents creator facts, never calls a model, and never becomes an
identity authority.  It only says how much conversational room the current
thread should receive and whether Mary has permission to carry initiative.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Any

from mary.runtime.persistence import atomic_write_json, load_json_recovering


_MODES = {"adaptive", "quick", "engaged", "deep"}

_ENGAGE_PATTERNS = (
    r"\b(?:let'?s|lets) (?:just )?(?:talk|chat)\b",
    r"\b(?:i )?(?:want|wanna) (?:to )?(?:talk|chat)(?: with you)?\b",
    r"\bhave (?:a |an )?(?:real |actual |intentional )?conversation\b",
    r"\bask me (?:some )?questions?\b",
    r"\bget to know me\b",
    r"\bwhat do you want to know\b",
    r"\bbe (?:more )?(?:curious|proactive|intentional)\b",
)

_DEEP_PATTERNS = (
    r"\bdeep conversation\b",
    r"\breally think\b",
    r"\bthink (?:with me|this through|about this)\b",
    r"\breflect (?:with me|on this|about this)\b",
    r"\bunpack (?:this|that|it)\b",
    r"\bgo deeper\b",
    r"\b(?:i want|i need) you to think\b",
)

_QUICK_PATTERNS = (
    r"\b(?:quick|short) answer\b",
    r"\bkeep it (?:short|brief|quick)\b",
    r"\bjust tell me\b",
)

_EXIT_PATTERNS = (
    r"\b(?:stop|end) (?:the )?(?:deep |intentional )?(?:conversation|talk mode)\b",
    r"\bback to (?:normal|auto|adaptive)\b",
)


@dataclass(frozen=True)
class EngagementPlan:
    configured_mode: str
    effective_mode: str
    initiative: str
    reasoning_depth: str
    target_length: str
    allow_follow_up_question: bool
    question_budget: int
    session_active: bool
    turns_remaining: int
    rationale: str
    thread_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConversationEngagement:
    """Process-local/persistable conversational depth state."""

    SCHEMA_VERSION = 1

    def __init__(self) -> None:
        configured = os.getenv("MARY_CONVERSATION_MODE", "adaptive")
        self.mode = self._normalize_mode(configured)
        self.session_mode: str | None = None
        self.turns_remaining = 0
        self.thread_id: str | None = None
        self.started_at: str | None = None
        self.last_plan: dict[str, Any] = {}
        self.last_question_asked = False
        self.total_engaged_turns = 0
        self.total_deep_turns = 0
        self.path: Path | None = None
        self.auto_save = False

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def configure(self, path: str | Path, *, auto_save: bool = True, load: bool = True) -> bool:
        self.path = Path(path)
        self.auto_save = bool(auto_save)
        if load:
            return self.load()
        return True

    def save(self) -> bool:
        if self.path is None:
            return True
        return atomic_write_json(self.path, self.to_dict(), backup_generations=3, indent=2)

    def load(self) -> bool:
        if self.path is None:
            return True
        payload, _ = load_json_recovering(self.path, backup_generations=3, restore_primary=False)
        if payload is None:
            return True
        if not isinstance(payload, dict):
            return False
        self.mode = self._normalize_mode(payload.get("mode", "adaptive"))
        active = payload.get("active_session", {})
        if isinstance(active, dict):
            session_mode = str(active.get("mode") or "").strip().lower()
            self.session_mode = session_mode if session_mode in {"engaged", "deep"} else None
            try:
                self.turns_remaining = max(0, min(20, int(active.get("turns_remaining", 0))))
            except (TypeError, ValueError):
                self.turns_remaining = 0
            self.thread_id = str(active.get("thread_id") or "").strip() or None
            self.started_at = str(active.get("started_at") or "").strip() or None
        stats = payload.get("stats", {})
        if isinstance(stats, dict):
            self.total_engaged_turns = int(stats.get("engaged_turns", 0) or 0)
            self.total_deep_turns = int(stats.get("deep_turns", 0) or 0)
        return True

    # ------------------------------------------------------------------
    # control
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_mode(value: Any) -> str:
        mode = str(value or "adaptive").strip().lower()
        return mode if mode in _MODES else "adaptive"

    def set_mode(self, mode: str) -> dict[str, Any]:
        self.mode = self._normalize_mode(mode)
        if self.mode in {"quick", "adaptive"}:
            self.session_mode = None
            self.turns_remaining = 0
            self.thread_id = None
        self._save_if_needed()
        return self.status()

    def begin_session(self, mode: str = "engaged", *, turns: int = 8, reason: str = "explicit") -> None:
        resolved = "deep" if str(mode).strip().lower() == "deep" else "engaged"
        self.session_mode = resolved
        self.turns_remaining = max(2, min(20, int(turns)))
        self.thread_id = f"thread_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.started_at = datetime.now().isoformat()
        self.last_plan = {"session_reason": str(reason or "explicit")[:160]}
        self._save_if_needed()

    def end_session(self) -> None:
        self.session_mode = None
        self.turns_remaining = 0
        self.thread_id = None
        self.started_at = None
        self._save_if_needed()

    # ------------------------------------------------------------------
    # turn planning
    # ------------------------------------------------------------------
    def begin_turn(self, text: str, *, intent_name: str = "") -> EngagementPlan:
        value = str(text or "").strip()
        lowered = value.lower()

        if self._matches(lowered, _EXIT_PATTERNS):
            self.end_session()

        if self.mode == "adaptive":
            if self._matches(lowered, _DEEP_PATTERNS):
                self.begin_session("deep", turns=8, reason="deep-conversation cue")
            elif self._matches(lowered, _ENGAGE_PATTERNS):
                self.begin_session("engaged", turns=8, reason="intentional-conversation cue")

        if self.mode != "adaptive":
            effective = self.mode
            rationale = f"creator-selected {self.mode} conversation mode"
        elif self.session_mode and self.turns_remaining > 0:
            effective = self.session_mode
            rationale = "active intentional-conversation thread"
        elif self._matches(lowered, _QUICK_PATTERNS):
            effective = "quick"
            rationale = "current turn explicitly asks for a brief answer"
        else:
            effective = "adaptive"
            rationale = "normal adaptive conversation"

        if effective == "deep":
            initiative, depth, length, questions = "proactive", "deep", "detailed", 1
            allow_question = True
        elif effective == "engaged":
            initiative, depth, length, questions = "balanced_proactive", "engaged", "medium", 1
            allow_question = True
        elif effective == "quick":
            initiative, depth, length, questions = "reactive", "quick", "brief", 0
            allow_question = False
        else:
            initiative, depth, length, questions = "adaptive", "normal", "adaptive", 1
            allow_question = True

        plan = EngagementPlan(
            configured_mode=self.mode,
            effective_mode=effective,
            initiative=initiative,
            reasoning_depth=depth,
            target_length=length,
            allow_follow_up_question=allow_question,
            question_budget=questions,
            session_active=bool(self.session_mode and self.turns_remaining > 0),
            turns_remaining=self.turns_remaining,
            rationale=rationale,
            thread_id=self.thread_id,
        )
        self.last_plan = plan.to_dict()
        return plan

    def complete_turn(self, response_text: str) -> None:
        response = str(response_text or "").strip()
        self.last_question_asked = response.endswith("?") or "?" in response[-240:]
        effective = str(self.last_plan.get("effective_mode") or "adaptive")
        if effective == "engaged":
            self.total_engaged_turns += 1
        elif effective == "deep":
            self.total_deep_turns += 1
        if self.session_mode and self.turns_remaining > 0:
            self.turns_remaining -= 1
            if self.turns_remaining <= 0:
                self.session_mode = None
                self.thread_id = None
                self.started_at = None
        self._save_if_needed()

    def status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "active_session": {
                "mode": self.session_mode,
                "turns_remaining": self.turns_remaining,
                "thread_id": self.thread_id,
                "started_at": self.started_at,
            },
            "last_plan": dict(self.last_plan),
            "last_question_asked": self.last_question_asked,
            "stats": {
                "engaged_turns": self.total_engaged_turns,
                "deep_turns": self.total_deep_turns,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.SCHEMA_VERSION, **self.status()}

    def _save_if_needed(self) -> None:
        if self.auto_save and self.path is not None:
            self.save()

    @staticmethod
    def _matches(text: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
