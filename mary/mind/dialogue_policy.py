"""Fast deterministic conversational policy above Mary's local reservoir."""
from __future__ import annotations

import re
from typing import Any

from mary.cognition.intent import Intent, IntentType
from .dialogue_acts import DialogueAct, DialoguePlan
from .reservoir import CognitiveReservoir, ReservoirHit


_GREETING_RE = re.compile(r"^\s*(?:hey+|hi+|hello+|yo+|hiya|sup)(?:\s+mary)?[!.?\s]*$", re.I)
_THANKS_RE = re.compile(r"^\s*(?:thanks|thank you|thx|appreciate it|ty)[!.?\s]*$", re.I)
_GOODBYE_RE = re.compile(r"^\s*(?:bye|goodbye|good night|night mary|later|see ya|see you)[!.?\s]*$", re.I)
_LAUGH_RE = re.compile(r"^\s*(?:lol+|lmao+|haha+|hehe+|😂+|😭+)[!.?\s]*$", re.I)
_ACK_RE = re.compile(r"^\s*(?:ok|okay|yeah|yep|yup|nah|nope|nice|cool|got it)[!.?\s]*$", re.I)
_REACT_RE = re.compile(r"^\s*(?:damn|wow|wild)[!.?\s]*$", re.I)
_MILESTONE_RE = re.compile(
    r"\b(?:finally|all (?:the )?tests? passed|tests? (?:all )?passed|"
    r"fixed (?:it|that|the)|solved (?:it|that|the)|got (?:it|that) working|"
    r"finished (?:it|that|the)|shipped|deployed|completed|done now|it works)\b",
    re.I,
)
_HOW_ARE_YOU_RE = re.compile(r"\b(?:how are you|how're you|how you doing|how you feel|you good)\b", re.I)
_WHAT_UP_RE = re.compile(r"\b(?:what are you up to|what're you up to|what are you doing|whats up with you|what's up with you)\b", re.I)
_COMPOUND_FOLLOWUP_RE = re.compile(r"[,;]?\s+(?:and|but|also)\s+(?:what|why|how|where|when|who|can|could|would|do|does|did|are|is|have|has|will|should)\b", re.I)
_CREATOR_FACT_RE = re.compile(r"\bwhat(?:'s| is) my (?P<field>[a-z0-9 _-]{2,50})\??$", re.I)
_MARY_PREFERENCE_RE = re.compile(r"\b(?:do you like|how do you feel about|what do you think of) (?P<topic>[^?!.]{2,80})[?!.]*$", re.I)
_LOCAL_KNOWLEDGE_RE = re.compile(r"\b(?:what do you know about|tell me what you know about) (?P<topic>[^?!.]{2,100})[?!.]*$", re.I)


class LocalDialoguePolicy:
    def plan(
        self,
        text: str,
        *,
        intent: Intent | None,
        hot_state: dict[str, Any],
        reservoir: CognitiveReservoir,
    ) -> DialoguePlan:
        value = str(text or "").strip()
        intent_type = intent.intent_type if intent is not None else IntentType.UNKNOWN

        # Explicit subsystem/tool/research intents keep their authoritative
        # paths.  The local dialogue layer never swallows them.
        if intent_type in {
            IntentType.MEMORY_STORE,
            IntentType.MEMORY_RECALL,
            IntentType.CONVERSATION_RECALL,
            IntentType.WEB_SEARCH,
            IntentType.TOOL_USE,
            IntentType.CREATOR_DIRECTIVE,
            IntentType.RELATIONSHIP_SHARE,
            IntentType.RELATIONSHIP_QUERY,
            IntentType.SELF_QUERY,
        }:
            return DialoguePlan(DialogueAct.ESCALATE, 1.0, "authoritative subsystem intent", local=False)

        if _GREETING_RE.search(value):
            return DialoguePlan(DialogueAct.GREET, 0.99, "simple greeting", local=True)
        if _THANKS_RE.search(value):
            return DialoguePlan(DialogueAct.THANKS_RESPONSE, 0.99, "simple thanks", local=True)
        if _GOODBYE_RE.search(value):
            return DialoguePlan(DialogueAct.GOODBYE, 0.99, "simple goodbye", local=True)
        if _LAUGH_RE.search(value):
            return DialoguePlan(DialogueAct.LAUGH, 0.98, "laughter/reaction", local=True)
        if _MILESTONE_RE.search(value) and intent_type in {
            IntentType.CONVERSATION, IntentType.FEEDBACK, IntentType.UNKNOWN
        }:
            return DialoguePlan(
                DialogueAct.REACT,
                0.97,
                "creator shared a bounded completion/milestone that Mary can react to without model reasoning",
                local=True,
                slots={"reaction_kind": "milestone"},
                target_length="micro",
            )
        if _ACK_RE.search(value):
            return DialoguePlan(DialogueAct.ACKNOWLEDGE, 0.94, "short acknowledgement", local=True)
        if _REACT_RE.search(value):
            return DialoguePlan(DialogueAct.REACT, 0.94, "short reaction", local=True)
        how_are_you = _HOW_ARE_YOU_RE.search(value)
        if how_are_you:
            if _COMPOUND_FOLLOWUP_RE.search(value, how_are_you.end()):
                return DialoguePlan(DialogueAct.ESCALATE, 1.0, "compound Mary-status question requires full reasoning", local=False)
            return DialoguePlan(DialogueAct.STATUS, 0.97, "represented Mary-state question", local=True, slots={"status_kind": "emotion"})
        what_up = _WHAT_UP_RE.search(value)
        if what_up:
            if _COMPOUND_FOLLOWUP_RE.search(value, what_up.end()):
                return DialoguePlan(DialogueAct.ESCALATE, 1.0, "compound Mary-activity question requires full reasoning", local=False)
            return DialoguePlan(DialogueAct.STATUS, 0.96, "represented Mary activity question", local=True, slots={"status_kind": "activity"})

        fact = _CREATOR_FACT_RE.search(value)
        if fact:
            field = _normalize_field(fact.group("field"))
            hit = _creator_fact_hit(reservoir, field)
            if hit is not None and hit.confidence >= 0.85:
                return DialoguePlan(
                    DialogueAct.KNOWN_FACT,
                    0.96,
                    "high-confidence creator fact exists locally",
                    local=True,
                    slots={"hit": hit.to_dict(), "field": field},
                    target_length="brief",
                )

        preference = _MARY_PREFERENCE_RE.search(value)
        if preference:
            topic = " ".join(preference.group("topic").split()).strip()
            hits = reservoir.search(topic, limit=8, minimum_confidence=0.7)
            for hit in hits:
                if hit.subject == "mary" and hit.kind == "mary_preference":
                    return DialoguePlan(
                        DialogueAct.KNOWN_PREFERENCE,
                        min(.96, .72 + hit.confidence * .24),
                        "represented Mary preference exists locally",
                        local=True,
                        slots={"hit": hit.to_dict(), "topic": topic},
                        target_length="brief",
                    )
            # The reservoir is a rebuildable selector, not the authority.  A
            # direct preference question can still be attempted locally when
            # the selector is cold/empty: owner confirmation below will require
            # an exact live match in Mary's canonical Preferences object before
            # any response is allowed. Unknown topics therefore fail closed to
            # normal cognition instead of being invented.
            return DialoguePlan(
                DialogueAct.KNOWN_PREFERENCE,
                .90,
                "direct Mary preference question; confirm against canonical owner",
                local=True,
                slots={"topic": topic},
                target_length="brief",
            )

        knowledge = _LOCAL_KNOWLEDGE_RE.search(value)
        if knowledge:
            topic = " ".join(knowledge.group("topic").split()).strip()
            hits = [
                hit.to_dict() for hit in reservoir.search(topic, limit=5, minimum_confidence=.78)
                if hit.authority in {
                    "creator_explicit", "mary_canonical", "mary_developed",
                    "semantic_memory", "knowledge_verified", "episodic_history",
                }
            ][:3]
            if hits:
                return DialoguePlan(
                    DialogueAct.ANSWER,
                    .88,
                    "bounded high-confidence local reservoir evidence exists",
                    local=True,
                    slots={"hits": hits, "topic": topic},
                    target_length="brief",
                )

        return DialoguePlan(DialogueAct.ESCALATE, 0.9, "novel/open-ended language is better handled by a language cortex", local=False)


def _normalize_field(value: str) -> str:
    text = " ".join(str(value).strip().lower().split())
    aliases = {
        "favorite colour": "favorite_color",
        "favorite color": "favorite_color",
        "favourite color": "favorite_color",
        "favourite colour": "favorite_color",
        "name": "name",
    }
    return aliases.get(text, text.replace(" ", "_"))


def _creator_fact_hit(reservoir: CognitiveReservoir, field: str) -> ReservoirHit | None:
    exact = reservoir.exact(subject="creator", predicate=field)
    if exact is not None:
        return exact
    # Preference records often carry natural keys such as favorite_color.
    results = reservoir.search(field.replace("_", " "), limit=6, minimum_confidence=0.8)
    for hit in results:
        if hit.subject == "creator" and hit.predicate == field:
            return hit
    return None
