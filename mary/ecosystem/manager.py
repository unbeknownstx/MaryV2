"""Cohesive capability surface around the canonical Mary instance."""
from __future__ import annotations
from pathlib import Path
from typing import Any

from mary.productivity import CommandCenter, FocusManager, MaryInbox, PersonalSearch, RuntimeMetrics
from mary.productivity.research import ResearchNotebook
from mary.productivity.arcade import MaryArcade
from mary.study import StudyManager
from mary.creative import ProductionStudio
from mary.presence import PresenceManager, PresenceEventType
from mary.skills import SkillRegistry
from mary.integrations import twitch_policy_from_environment, obs_policy_from_environment
from mary.integrations.youtube import YouTubeSearch
from mary.knowledge import WorldContextStore, WorldPulsePlanner
from mary.learning import AdapterLab, ModelCandidateCatalog
from mary.streaming import StreamingPresenceCoordinator
from mary.mind.fast_brain import fast_brain_from_environment
from mary.conversation.cross_surface import CrossSurfaceAwareness
from mary.distributed.action_windows import ActionWindowRegistry
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
        self.production = ProductionStudio(self.root)
        self.arcade = MaryArcade()
        self.metrics = RuntimeMetrics()
        self.skills = SkillRegistry()
        self.presence = PresenceManager(
            self.root / "presence",
            attention=getattr(getattr(mary, "realtime", None), "attention", None),
        )
        self.world = WorldContextStore()
        self.world_pulse = WorldPulsePlanner()
        self.streaming = StreamingPresenceCoordinator(
            self.presence,
            fast_brain=fast_brain_from_environment(mary),
            speaker_scheduler=getattr(getattr(mary, "realtime", None), "speaker_scheduler", None),
        )
        self.adapter_lab = AdapterLab(self.root / "model_adapter_lab.json")
        self.cross_surface = CrossSurfaceAwareness()
        self.action_windows = ActionWindowRegistry(
            decision_trace=getattr(getattr(mary, "realtime", None), "decision_trace", None),
        )
        self.model_candidates = ModelCandidateCatalog(
            Path(mary.config.paths.root) / "assets" / "models" / "candidates" / "model_candidates.json"
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
            "production": self.production.snapshot(),
            "current_work": (
                self.mary.current_work_projection({
                    "command": {**self.command.summary(), "items": self.command.list(limit=12)},
                    "focus": self.focus.snapshot(),
                    "production": self.production.snapshot(),
                })
                if callable(getattr(self.mary, "current_work_projection", None))
                else {}
            ),
            "arcade": {"games": self.arcade.games()},
            "companion": self.companion_snapshot(),
            "metrics": self.metrics.snapshot(),
            "last_turn": self.metrics.last_turn(),
            "skills": self.skills.snapshot(),
            "presence": {**self.presence.snapshot(), "foreground_window": foreground_window()},
            "world_context": self.world.snapshot(),
            "world_pulse": self.world_pulse.snapshot(),
            "streaming": self.streaming.snapshot(),
            "adapter_lab": self.adapter_lab.snapshot(),
            "cross_surface": self.cross_surface.snapshot(),
            "action_windows": self.action_windows.snapshot(),
            "model_candidates": self.model_candidates.snapshot(),
            "character_runtime": {
                "live_scene": self.presence.scene.snapshot(),
                "realtime": (
                    self.mary.realtime.status()
                    if callable(getattr(getattr(self.mary, "realtime", None), "status", None))
                    else {}
                ),
            },
            "external": {
                "twitch": twitch_policy_from_environment().to_dict(),
                "obs": obs_policy_from_environment().to_dict(),
                "youtube": self.youtube.status(),
            },
            "paths": {
                "ecosystem_root": str(self.root),
                "search_roots": [str(x) for x in self.search.roots],
                "model_root": str(self.mary.config.paths.models),
            },
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
            production=self.production,
            inbox=self.inbox,
            presence=self.presence,
        )

    def workspace_snapshot(self) -> dict[str, Any]:
        """Return only canonical/shared workspace state.

        This is the remote-safe ecosystem view. It deliberately excludes
        machine-local capabilities such as PersonalSearch roots, foreground
        windows, host paths, and local integration availability.
        """

        snapshot = {
            "command": {
                **self.command.summary(),
                "items": self.command.list(limit=60),
            },
            "focus": self.focus.snapshot(),
            "inbox": {
                **self.inbox.summary(),
                "items": self.inbox.list(limit=50),
            },
            "study": {
                **self.study.summary(),
                "due_cards": self.study.due_cards(limit=20),
            },
            "research": {
                **self.research.summary(),
                "threads": self.research.list(30),
            },
            "production": self.production.snapshot(),
            "arcade": {
                "games": self.arcade.games(),
            },
            "companion": self.companion_snapshot(),
            "presence": self.presence.snapshot(),
            "world_context": self.world.snapshot(),
            "world_pulse": self.world_pulse.snapshot(),
            "streaming": self.streaming.snapshot(),
            "adapter_lab": self.adapter_lab.snapshot(),
            "cross_surface": self.cross_surface.snapshot(),
            "action_windows": self.action_windows.snapshot(),
            "model_candidates": self.model_candidates.snapshot(),
            "character_runtime": {
                "live_scene": self.presence.scene.snapshot(),
                "realtime": (
                    self.mary.realtime.status()
                    if callable(getattr(getattr(self.mary, "realtime", None), "status", None))
                    else {}
                ),
            },
            "semantics": {
                "authority": "canonical_workspace",
                "identity_owner": False,
                "device_local_capabilities_included": False,
            },
        }
        snapshot["current_work"] = (
            self.mary.current_work_projection(snapshot)
            if callable(getattr(self.mary, "current_work_projection", None))
            else {}
        )
        return snapshot

    def apply_workspace_action(
        self,
        action: str,
        args: dict[str, Any] | None = None,
        *,
        source: str = "mary_protocol",
    ) -> dict[str, Any]:
        """Apply one bounded canonical workspace mutation.

        The action vocabulary is intentionally small. Device-local operations
        (filesystem search, foreground window, OBS, microphone, Ollama, etc.)
        are not valid workspace actions and belong to capability nodes.
        """

        name = str(action or "").strip().lower()
        values = dict(args or {})

        def publish(
            event_type: PresenceEventType,
            summary: str,
            *,
            importance: float = .55,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            try:
                self.presence.publish(
                    event_type,
                    summary,
                    source=source,
                    importance=importance,
                    metadata=metadata,
                )
            except Exception:
                # Workspace state must never fail merely because ephemeral
                # Presence publication failed.
                pass

        if name == "command.add":
            item = self.command.add(
                str(values.get("title") or ""),
                kind=str(values.get("kind") or "task"),
                priority=int(values.get("priority", 2)),
                notes=str(values.get("notes") or ""),
            )
            publish(
                PresenceEventType.COMMAND_CHANGED,
                f"Command Center added {item.get('title', '')}",
                importance=.58,
                metadata={
                    "item_id": item.get("id"),
                    "status": item.get("status"),
                },
            )
            return {"ok": True, "item": item}

        if name == "command.update":
            item_id = str(values.get("item_id") or "")
            changes = {
                key: values[key]
                for key in ("title", "notes", "status", "priority")
                if key in values
            }
            if not changes:
                raise ValueError("command.update requires at least one change.")
            item = self.command.update(item_id, **changes)
            publish(
                PresenceEventType.COMMAND_CHANGED,
                f"Command Center updated {item.get('title', '')}",
                importance=.54,
                metadata={
                    "item_id": item.get("id"),
                    "status": item.get("status"),
                },
            )
            return {"ok": True, "item": item}

        if name == "focus.start":
            minutes = int(values.get("minutes", 45))
            task = str(values.get("task") or "")
            state = self.focus.start(minutes, task=task)
            publish(
                PresenceEventType.FOCUS_CHANGED,
                f"Focus started for {minutes} minutes" + (f" on {task}" if task else ""),
                importance=.44,
                metadata={"active": True, "minutes": minutes},
            )
            return {"ok": True, "focus": state}

        if name == "focus.stop":
            state = self.focus.stop(
                completed=bool(values.get("completed", True))
            )
            publish(
                PresenceEventType.FOCUS_CHANGED,
                "Focus session stopped",
                importance=.42,
                metadata={"active": False},
            )
            return {"ok": True, "focus": state}

        if name == "study.create_project":
            project = self.study.create_project(
                str(values.get("title") or ""),
                objective=str(values.get("objective") or ""),
            )
            publish(
                PresenceEventType.STUDY_CHANGED,
                f"Study project created: {project.get('title', '')}",
                importance=.58,
                metadata={"project_id": project.get("id")},
            )
            return {"ok": True, "project": project}

        if name == "study.add_card":
            project_id = str(values.get("project_id") or "")
            card = self.study.add_card(
                project_id,
                str(values.get("prompt") or ""),
                str(values.get("answer") or ""),
                tags=list(values.get("tags") or [])[:10],
            )
            publish(
                PresenceEventType.STUDY_CHANGED,
                "A study card was added",
                importance=.46,
                metadata={
                    "project_id": project_id,
                    "card_id": card.get("id"),
                },
            )
            return {"ok": True, "card": card}

        if name == "study.review_card":
            project_id = str(values.get("project_id") or "")
            card_id = str(values.get("card_id") or "")
            score = int(values.get("score", 0))
            card = self.study.review(project_id, card_id, score)
            publish(
                PresenceEventType.STUDY_CHANGED,
                f"A study review was scored {max(0, min(5, score))}/5",
                importance=.5,
                metadata={
                    "project_id": project_id,
                    "card_id": card_id,
                    "score": score,
                },
            )
            return {"ok": True, "card": card}

        if name == "research.create_thread":
            thread = self.research.create(
                str(values.get("title") or ""),
                question=str(values.get("question") or ""),
            )
            publish(
                PresenceEventType.PROJECT_CHANGED,
                f"Research thread created: {thread.get('title', '')}",
                importance=.54,
                metadata={"thread_id": thread.get("id")},
            )
            return {"ok": True, "thread": thread}

        if name == "arcade.play":
            return {
                "ok": True,
                **self.arcade.play(
                    str(values.get("game") or ""),
                    str(values.get("payload") or ""),
                ),
            }

        if name == "research.add_note":
            thread_id = str(values.get("thread_id") or "")
            note = self.research.add_note(
                thread_id,
                str(values.get("text") or ""),
                source=str(values.get("source") or ""),
                url=str(values.get("url") or ""),
            )
            publish(
                PresenceEventType.PROJECT_CHANGED,
                "A research note was added",
                importance=.48,
                metadata={
                    "thread_id": thread_id,
                    "note_id": note.get("id"),
                },
            )
            return {"ok": True, "note": note}

        if name == "production.create":
            shots = values.get("shots") or []
            characters = values.get("characters") or []
            references = values.get("references") or []
            if not isinstance(shots, list) or not isinstance(characters, list) or not isinstance(references, list):
                raise ValueError("production.create shots, characters, and references must be lists")
            project = self.production.create(
                title=str(values.get("title") or ""),
                objective=str(values.get("objective") or ""),
                shots=shots,
                characters=characters,
                format=str(values.get("format") or "short_video"),
                aspect_ratio=str(values.get("aspect_ratio") or "9:16"),
                target_seconds=int(values.get("target_seconds", 30) or 30),
                deliverables=list(values.get("deliverables") or ("master_video", "thumbnail", "caption")),
                provider_preferences=dict(values.get("provider_preferences") or {}),
                references=references,
                creative_intent=list(values.get("creative_intent") or []),
                style_constraints=list(values.get("style_constraints") or []),
                budget_ceiling_usd=values.get("budget_ceiling_usd"),
                source=source,
            )
            publish(
                PresenceEventType.PROJECT_CHANGED,
                f"Production created: {project.get('title', '')}",
                importance=.6,
                metadata={"production_id": project.get("production_id"), "stage": project.get("stage")},
            )
            return {"ok": True, "production": project}

        if name == "production.set_stage":
            project = self.production.set_stage(
                str(values.get("production_id") or ""),
                str(values.get("stage") or ""),
            )
            publish(
                PresenceEventType.PROJECT_CHANGED,
                f"Production stage changed: {project.get('title', '')} → {project.get('stage', '')}",
                importance=.52,
                metadata={"production_id": project.get("production_id"), "stage": project.get("stage")},
            )
            return {"ok": True, "production": project}

        if name == "production.add_asset":
            asset = self.production.add_asset(
                str(values.get("production_id") or ""),
                kind=str(values.get("kind") or ""),
                uri=str(values.get("uri") or ""),
                shot_id=str(values.get("shot_id") or ""),
                provider=str(values.get("provider") or ""),
                model=str(values.get("model") or ""),
                status=str(values.get("status") or "candidate"),
                metadata=values.get("metadata") if isinstance(values.get("metadata"), dict) else {},
            )
            publish(
                PresenceEventType.PROJECT_CHANGED,
                "A production asset was registered",
                importance=.46,
                metadata={"production_id": values.get("production_id"), "asset_id": asset.get("id")},
            )
            return {"ok": True, "asset": asset}

        if name == "production.review":
            review = self.production.review(
                str(values.get("production_id") or ""),
                rating=str(values.get("rating") or "neutral"),
                note=str(values.get("note") or ""),
                asset_id=str(values.get("asset_id") or ""),
            )
            return {"ok": True, "review": review}

        if name == "inbox.mark_read":
            notice_id = str(values.get("notice_id") or "")
            changed = self.inbox.mark_read(
                notice_id,
                bool(values.get("read", True)),
            )
            return {"ok": True, "changed": bool(changed)}

        raise ValueError(f"Unsupported canonical workspace action: {name}")

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

    def ingest_stream_chat(self, message: Any, *, creator_speaking: bool = False) -> dict[str, Any]:
        """Feed one untrusted social chat message into shared Presence."""
        return self.streaming.ingest_chat(message, creator_speaking=creator_speaking)

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
