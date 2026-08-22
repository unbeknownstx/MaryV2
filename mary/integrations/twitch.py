"""Twitch configuration boundary for the later external-integration pass.

No network calls are made here. Credentials stay in the environment/OAuth
store when the live Twitch client is enabled later; they are never persisted
inside Mary relationship/memory state.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class TwitchPolicy:
    enabled: bool
    account_name: str
    approved_channels: tuple[str,...]
    mode: str
    read_chat: bool
    write_chat: bool
    def to_dict(self): return asdict(self)

def twitch_policy_from_environment() -> TwitchPolicy:
    enabled=os.getenv("MARY_SKILL_TWITCH","").strip().lower() in {"1","true","yes","on"}
    channels=tuple(x.strip().lower().lstrip('#') for x in os.getenv("MARY_TWITCH_APPROVED_CHANNELS","").split(',') if x.strip())
    mode=os.getenv("MARY_TWITCH_MODE","listen").strip().lower() or "listen"
    return TwitchPolicy(enabled,os.getenv("MARY_TWITCH_ACCOUNT","").strip(),channels,mode,True,mode in {"mention","companion","cohost"})
