"""Cheap initiative policy. Silence is the default, valid outcome."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from time import monotonic
from .events import PresenceEvent, PresenceEventType

class InitiativeAction(str, Enum):
    SILENCE="silence"; REACT="react"; OPINE="opine"; TEASE="tease"; QUESTION="question"; REMEMBER="remember"; HELP="help"; HOLD_THOUGHT="hold_thought"

@dataclass(frozen=True)
class InitiativeDecision:
    action: InitiativeAction
    score: float
    reason: str
    speak: bool = False
    def to_dict(self):
        d=asdict(self); d["action"]=self.action.value; return d

class InitiativeEngine:
    def __init__(self, *, min_speak_interval: float = 35.0, threshold: float = 0.72) -> None:
        self.min_speak_interval=max(5,float(min_speak_interval)); self.threshold=max(.1,min(1,float(threshold))); self._last_spoke_at=0.0
    def decide(self,event:PresenceEvent,*,mode:str="companion",creator_active:bool=True)->InitiativeDecision:
        if mode in {"off","listen"}: return InitiativeDecision(InitiativeAction.SILENCE,0,"presence mode does not permit initiation")
        score=max(0,min(1,float(event.importance)))
        if event.event_type==PresenceEventType.TWITCH_MENTION: score=max(score,.82)
        elif event.event_type==PresenceEventType.CREATOR_SPEECH: score=max(score,.78)
        elif event.event_type in {PresenceEventType.OBS_SCENE,PresenceEventType.FOREGROUND_APP}: score*=.62
        elif event.event_type==PresenceEventType.IDLE_TICK: score*=.45
        elif event.event_type==PresenceEventType.FOCUS_CHANGED: score*=.35
        elif event.event_type in {PresenceEventType.COMMAND_CHANGED,PresenceEventType.STUDY_CHANGED}: score*=.82
        elif event.event_type==PresenceEventType.CREATIVE_CHANGED: score*=.90
        if creator_active and monotonic()-self._last_spoke_at<self.min_speak_interval: score*=.45
        if score < self.threshold:
            hold_types={PresenceEventType.VISUAL_OBSERVATION,PresenceEventType.PROJECT_CHANGED,PresenceEventType.CREATIVE_CHANGED,PresenceEventType.COMMAND_CHANGED,PresenceEventType.STUDY_CHANGED}
            action=InitiativeAction.HOLD_THOUGHT if score>=self.threshold*.72 and event.event_type in hold_types else InitiativeAction.SILENCE
            return InitiativeDecision(action,round(score,3),"not salient enough to interrupt",False)
        action=InitiativeAction.REACT
        if event.event_type==PresenceEventType.TWITCH_MENTION: action=InitiativeAction.REACT
        elif event.event_type==PresenceEventType.VISUAL_OBSERVATION: action=InitiativeAction.OPINE
        elif event.event_type in {PresenceEventType.PROJECT_CHANGED,PresenceEventType.CREATIVE_CHANGED,PresenceEventType.COMMAND_CHANGED,PresenceEventType.STUDY_CHANGED}: action=InitiativeAction.HELP
        return InitiativeDecision(action,round(score,3),"salient live-context event",True)
    def mark_spoken(self):
        self._last_spoke_at=monotonic()

    def seconds_since_spoken(self) -> float | None:
        if self._last_spoke_at <= 0.0:
            return None
        return max(0.0, monotonic() - self._last_spoke_at)

    def cooldown_ready(self) -> bool:
        elapsed = self.seconds_since_spoken()
        return elapsed is None or elapsed >= self.min_speak_interval
