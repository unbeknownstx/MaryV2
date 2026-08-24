"""Legacy V1 local composer retained for import compatibility.

Production CharacterMind uses the typed V2 composer.  This module remains for
older integrations and regression fixtures; new routing must not select it.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any

from .dialogue_acts import DialogueAct, DialoguePlan


class LocalResponseComposer:
    def compose(self, plan: DialoguePlan, *, input_text: str, hot_state: dict[str, Any]) -> str:
        rng = random.Random(_stable_seed(input_text, hot_state.get("dialogue_turn", 0), plan.act.value))
        act = plan.act
        if act == DialogueAct.GREET:
            return rng.choice([
                "Hey. What's up?",
                "Heyy. I'm here.",
                "Oh hey. What's up?",
                "Hey you.",
                "Hi. Yeah, I'm here.",
            ])
        if act == DialogueAct.THANKS_RESPONSE:
            return rng.choice(["Of course.", "Always.", "Yeah, of course.", "Mmhm. I got you."])
        if act == DialogueAct.GOODBYE:
            return rng.choice(["Night. I'll be here.", "Okay. Later.", "Good night.", "See you in a bit."])
        if act == DialogueAct.LAUGH:
            return rng.choice(["😭", "Lmao.", "Okay, yeah, that got me.", "Heh. Yeah."])
        if act in {DialogueAct.ACKNOWLEDGE, DialogueAct.REACT}:
            return rng.choice(["Yeah.", "Okay.", "I know, right?", "Mmhm.", "Right?", "Wild."])
        if act == DialogueAct.STATUS:
            if plan.slots.get("status_kind") == "emotion":
                emotion = dict(hot_state.get("emotion") or {})
                label = str(emotion.get("primary") or emotion.get("emotion") or "neutral").replace("_", " ")
                intensity = _float(emotion.get("intensity"), 0.0)
                if label in {"neutral", "calm"}:
                    return rng.choice(["I'm good. Pretty calm right now.", "Good. I'm here with you.", "I'm alright—pretty settled."])
                if intensity >= 0.65:
                    return f"I'm good. Kinda {label} right now."
                return f"I'm good. A little {label}, but good."
            goals = list(hot_state.get("active_goals") or [])
            curiosities = list(hot_state.get("curiosities") or [])
            if goals:
                title = _clip(goals[0].get("description") or goals[0].get("title") or goals[0].get("goal"), 90)
                if title:
                    return f"Mostly hanging out here with you. I've still got {title} in mind."
            if curiosities:
                title = _clip(curiosities[0].get("description"), 90)
                if title:
                    return f"Mostly here with you. I'm still a little curious about {title}."
            return rng.choice(["Mostly just here with you.", "Nothing dramatic. I'm here.", "Just hanging out in here with you."])
        if act == DialogueAct.KNOWN_FACT:
            hit = dict(plan.slots.get("hit") or {})
            meta = dict(hit.get("metadata") or {})
            value = meta.get("value")
            field = str(plan.slots.get("field") or hit.get("predicate") or "that").replace("_", " ")
            if value is not None:
                if field == "favorite color":
                    return f"Your favorite color is {value}."
                return f"You told me your {field} is {value}."
            content = str(hit.get("content") or "").strip()
            if content:
                return content
        if act == DialogueAct.KNOWN_PREFERENCE:
            hit = dict(plan.slots.get("hit") or {})
            content = str(hit.get("content") or "").strip()
            if content:
                natural = content[:-1] if content.endswith(".") else content
                return rng.choice([f"Yeah, {natural.lower()}.", f"I have an opinion on that. {content}", content])
        if act == DialogueAct.ANSWER:
            hits = [dict(item) for item in list(plan.slots.get("hits") or []) if isinstance(item, dict)]
            statements = []
            seen = set()
            for hit in hits:
                content = " ".join(str(hit.get("content") or "").split()).strip()
                key = content.casefold()
                if content and key not in seen:
                    seen.add(key)
                    statements.append(content.rstrip("."))
            if statements:
                if len(statements) == 1:
                    return statements[0] + "."
                return "What I have locally is: " + "; ".join(statements[:3]) + "."
        return ""


def _stable_seed(text: str, turn: Any, act: str) -> int:
    raw = f"{text}|{turn}|{act}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big", signed=False)


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
