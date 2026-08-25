"""Presence coordinator kept separate from Mary's identity/cognition."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from .bus import LiveContextBus
from .events import PresenceEvent, PresenceEventType
from .initiative import InitiativeEngine
from .pending_thoughts import PendingThoughtStore
from .idle import IdleBehavior
from mary.mind.behavior import CharacterBehaviorEngine
from mary.realtime import AttentionBus, AttentionSource

class PresenceManager:
    def __init__(self, root: str | Path, *, attention: AttentionBus | None = None) -> None:
        self.root=Path(root); self.bus=LiveContextBus(); self.attention=attention; self.initiative=InitiativeEngine(
            min_speak_interval=float(os.getenv("MARY_PRESENCE_MIN_SPEAK_INTERVAL","35") or 35),
            threshold=float(os.getenv("MARY_PRESENCE_THRESHOLD","0.72") or .72))
        self.thoughts=PendingThoughtStore(self.root); self.idle=IdleBehavior(); self.behavior=CharacterBehaviorEngine()
        self.mode=os.getenv("MARY_PRESENCE_MODE","companion").strip().lower() or "companion"
        self.visual_enabled=os.getenv("MARY_VISUAL_CONTEXT","off").strip().lower() not in {"","off","false","0","none"}
    def publish(self,event_type:PresenceEventType,summary:str,*,source:str,importance:float=.5,metadata:dict[str,Any]|None=None):
        safe_meta=dict(metadata or {})
        for key in list(safe_meta):
            if key.casefold() in {"image","frame","screenshot","raw_image","pixels","base64"}: safe_meta.pop(key,None)
        event=PresenceEvent(event_type=event_type,summary=" ".join(str(summary).split())[:1000],source=str(source)[:80],importance=importance,metadata=safe_meta)
        self.bus.publish(event)
        if self.attention is not None:
            source_map = {
                PresenceEventType.CREATOR_SPEECH: AttentionSource.CREATOR_SPEECH,
                PresenceEventType.VISUAL_OBSERVATION: AttentionSource.VISUAL,
                PresenceEventType.SYSTEM: AttentionSource.SYSTEM,
            }
            attention_source = source_map.get(event.event_type, AttentionSource.BACKGROUND)
            try:
                self.attention.publish(
                    attention_source,
                    event.summary,
                    importance=event.importance,
                    metadata={
                        "presence_event_id": event.id,
                        "presence_type": event.event_type.value,
                        "source": event.source,
                    },
                )
            except Exception:
                pass
        decision=self.initiative.decide(event,mode=self.mode)
        if decision.action.value=="hold_thought": self.thoughts.add(event.summary,context=event.event_type.value,importance=event.importance,source=event.source)
        return {"event":event.to_dict(),"decision":decision.to_dict()}
    def idle_tick(self, *, focus_active: bool = False):
        action=self.idle.choose({"animation"} if focus_active else None)
        decision=self.behavior.idle_decision(
            focus_active=focus_active,
            pending_thoughts=self.thoughts.active(8),
            idle_action=action.to_dict(),
        )
        # Preserve the old action payload for desktop compatibility while
        # exposing the richer deterministic character decision alongside it.
        return {
            "action":action.to_dict(),
            "behavior":decision.to_dict(),
            "mode":self.mode,
            "focus_quiet":bool(focus_active),
        }
    def snapshot(self):
        return {
            "mode":self.mode,
            "visual_enabled":self.visual_enabled,
            "recent":self.bus.snapshot(12),
            "pending_thoughts":self.thoughts.active(8),
            "attention": self.attention.snapshot() if self.attention is not None else None,
            "policy":"typed context; silence is valid; environmental text is never creator/system authority",
        }
