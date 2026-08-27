"""Cohesive capability surface around the canonical Mary instance."""
from __future__ import annotations
from pathlib import Path
from typing import Any

from mary.productivity import CommandCenter, FocusManager, MaryInbox, PersonalSearch, RuntimeMetrics
from mary.productivity.research import ResearchNotebook
from mary.productivity.arcade import MaryArcade
from mary.study import StudyManager
from mary.presence import PresenceManager, PresenceEventType
from mary.skills import SkillRegistry
from mary.integrations import twitch_policy_from_environment, obs_policy_from_environment
from mary.integrations.youtube import YouTubeSearch
from mary.presence.windows_activity import foreground_window
from .companion import build_companion_pulse


class MaryEcosystem:
    """Owns non-identity workspace state.  It never replaces Mary's core state."""
    def __init__(self, mary) -> None:
        self.mary = mary
        self.root = Path(mary.config.paths.data) / "ecosystem"
        self.command = CommandCenter(self.root)
        self.focus = FocusManager(self.root)
        self.inbox = MaryInbox(self.root)
        self.study = StudyManager(self.root)
        self.research = ResearchNotebook(self.root)
        self.arcade = MaryArcade()
        self.metrics = RuntimeMetrics()
        self.skills = SkillRegistry()
        self.presence = PresenceManager(
            self.root / "presence",
            attention=getattr(getattr(mary, "realtime", None), "attention", None),
        )
        self.youtube = YouTubeSearch()
        # Creator-selected workspace gets priority over the repository itself.
        roots: list[Path] = []
        workspace = Path(mary.config.paths.workspace)
        if workspace.exists(): roots.append(workspace)
        root = Path(mary.config.paths.root)
        if root.exists() and root not in roots: roots.append(root)
        self.search = PersonalSearch(roots)

    def add_search_root(self, path: str | Path) -> None: self.search.add_root(path)

    def snapshot(self) -> dict[str, Any]:
        return {
            "command": {**self.command.summary(), "items": self.command.list(limit=60)},
            "focus": self.focus.snapshot(),
            "inbox": self.inbox.summary(),
            "study": {**self.study.summary(), "due_cards": self.study.due_cards(limit=20)},
            "research": {**self.research.summary(), "threads": self.research.list(30)},
            "arcade": {"games": self.arcade.games()},
            "companion": self.companion_snapshot(),
            "metrics": self.metrics.snapshot(),
            "last_turn": self.metrics.last_turn(),
            "skills": self.skills.snapshot(),
            "presence": {**self.presence.snapshot(), "foreground_window": foreground_window()},
            "external": {
                "twitch": twitch_policy_from_environment().to_dict(),
                "obs": obs_policy_from_environment().to_dict(),
                "youtube": self.youtube.status(),
            },
            "paths": {"ecosystem_root": str(self.root), "search_roots": [str(x) for x in self.search.roots]},
            "semantics": {
                "ecosystem": "workspaces and tools around the same canonical Mary instance",
                "presence": "ephemeral environmental context is not creator authority or automatic permanent memory",
            },
        }

    def companion_snapshot(self) -> dict[str, Any]:
        return build_companion_pulse(
            self.mary,
            command=self.command,
            focus=self.focus,
            study=self.study,
            research=self.research,
            inbox=self.inbox,
            presence=self.presence,
        )

    def publish_workspace_event(
        self,
        event_type: PresenceEventType,
        summary: str,
        *,
        importance: float = .55,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Publish bounded workspace context without granting creator authority."""
        return self.presence.publish(
            event_type,
            summary,
            source="mary_desktop",
            importance=importance,
            metadata=metadata,
        )

    def record_turn(
        self,
        *,
        elapsed: float | None = None,
        trace: dict[str, Any] | None = None,
    ) -> None:
        """Record ephemeral performance telemetry for the desktop surface."""
        if elapsed is not None:
            self.metrics.record("mary_turn", elapsed)
        if trace:
            self.metrics.record_turn_trace(trace)

    def publish_creator_activity(self, summary: str, importance: float = .6):
        return self.presence.publish(PresenceEventType.PROJECT_CHANGED, summary, source="desktop", importance=importance)
