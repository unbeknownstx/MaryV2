"""MaryV2 turn-routing policy.

This module is the single policy boundary that decides which kind of language
engine should get first chance on a model-backed turn.  It does **not** own
identity, memory, relationship state, tools, or provider implementations.

V2 policy:
- personal/relational/character conversation -> local-first conversation route
- factual/technical/task work -> normal free-first task/general route
- grounded tool/research synthesis -> the existing tool/research paths
- explicit session overrides remain authoritative in :mod:`mary.llm.router`
- paid OpenAI remains an explicit one-task expert route and is never selected
  here automatically

The policy intentionally looks at Mary's conservatively normalized chat text in
addition to the coarse IntentType.  The current intent detector is broad by
design, so phrases such as "write me a python function" may still arrive as
CONVERSATION while "what do u think im trying to say" may arrive as QUESTION.
This layer keeps provider purpose aligned with the *actual* turn.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from mary.cognition.intent import Intent, IntentType
from mary.cognition.natural_input import normalize_for_matching


@dataclass(frozen=True)
class TurnPolicyDecision:
    """Display-safe routing decision for one model-backed turn."""

    category: str
    generation_purpose: str | None
    local_first: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "generation_purpose": self.generation_purpose,
            "local_first": self.local_first,
            "rationale": self.rationale,
        }


class TurnPolicyEngine:
    """Classify a Mary turn as local conversation or task/general work."""

    VERSION = "v2-breakthrough-10"

    # Phrases where the creator is talking *with Mary* rather than asking for a
    # detached factual/task answer. Keep these narrow and human-readable.
    _RELATIONAL_PATTERNS: tuple[str, ...] = (
        r"\b(?:just )?(?:wanna|want to) talk(?: to you| with you)?\b",
        r"\b(?:talk|chat) (?:with|to) (?:u|you)\b",
        r"\bwhat do (?:u|you) think\b",
        r"\bwhy do (?:u|you) think\b",
        r"\bwhat do (?:u|you) feel\b",
        r"\bhow do (?:u|you) feel\b",
        r"\bdo (?:u|you) think (?:i|im|i'm|we)\b",
        r"\bwhat should i\b",
        r"\bhelp me think\b",
        r"\bbounce ideas\b",
        r"\bthats not (?:really )?what i meant\b",
        r"\bi (?:dont|don't) agree\b",
        r"\b(?:our|my) relationship\b",
        r"\babout (?:me|us)\b",
        r"\bbuilding (?:u|you)\b",
        r"\bhow (?:u|you)(?:ve|'ve| have) changed\b",
        r"\bwhat (?:u|you)(?:ve|'ve| have) learned about me\b",
        r"\bwhat would (?:u|you) (?:ask|want to know)\b",
        r"\bi feel\b",
        r"\bim feeling\b",
        r"\bi'm feeling\b",
    )

    # Strong indicators that the user is delegating a detached task or asking
    # for factual/technical information. These override a coarse CONVERSATION
    # label unless a relational pattern above clearly applies.
    _TASK_PATTERNS: tuple[str, ...] = (
        r"^\s*what is\b",
        r"^\s*who is\b",
        r"^\s*when (?:is|did|was|were|does)\b",
        r"^\s*where (?:is|are|did|was|were)\b",
        r"^\s*how many\b",
        r"^\s*how much\b",
        r"^\s*define\b",
        r"^\s*explain\b",
        r"^\s*calculate\b",
        r"^\s*solve\b",
        r"\b(?:write|make|create|generate) (?:me )?(?:a )?(?:python|javascript|code|script|function|regex)\b",
        r"\bdebug (?:this|my|the) (?:code|script|program)\b",
        r"\b(?:summarize|analyse|analyze|extract|compare) (?:this|these|the|two|my)\b",
        r"\b(?:research|look up|search for|find)\b",
        r"\b(?:latest|current|today|right now)\b.*\b(?:news|price|weather|score|law|version|release)\b",
        r"\b(?:convert|conversion)\b",
        r"\bcapital of\b",
        r"\bwhat does .+ mean\b",
        r"\bhow does .+ work\b",
        r"\bhow do i (?:install|configure|fix|build|run|code|debug)\b",
    )

    _LOCAL_INTENTS = {
        IntentType.CONVERSATION,
        IntentType.EMOTIONAL_SUPPORT,
        IntentType.FEEDBACK,
        IntentType.SELF_QUERY,
        IntentType.GOAL,
        IntentType.CREATIVE,
        IntentType.UNKNOWN,
    }

    _TASK_INTENTS = {
        IntentType.REQUEST,
        IntentType.COMMAND,
        IntentType.INFORMATION,
        IntentType.WEB_SEARCH,
        IntentType.TOOL_USE,
    }

    def decide(
        self,
        *,
        input_text: str,
        intent: Intent | None,
        local_tool_grounded: bool = False,
        self_grounded: bool = False,
    ) -> TurnPolicyDecision:
        """Return the bounded provider-purpose decision for this turn."""

        if local_tool_grounded:
            return TurnPolicyDecision(
                category="grounded_tool_task",
                generation_purpose=None,
                local_first=False,
                rationale="tool evidence uses the normal task/general synthesis route",
            )

        if self_grounded:
            return TurnPolicyDecision(
                category="grounded_self_conversation",
                generation_purpose="conversation",
                local_first=True,
                rationale="Mary self/relationship expression is grounded locally and uses her conversation voice",
            )

        normalized = normalize_for_matching(str(input_text or ""))
        lowered = normalized.lower().strip()

        relational = self._matches_any(lowered, self._RELATIONAL_PATTERNS)
        task_like = self._matches_any(lowered, self._TASK_PATTERNS)

        # Direct relationship cues win over generic task-looking syntax. Example:
        # "what do you think is wrong with how im building you" is still a Mary
        # conversation, not a detached fact lookup.
        if relational:
            return TurnPolicyDecision(
                category="personal_conversation",
                generation_purpose="conversation",
                local_first=True,
                rationale="the creator is talking with Mary or asking for Mary's perspective",
            )

        if task_like:
            return TurnPolicyDecision(
                category="task_general",
                generation_purpose=None,
                local_first=False,
                rationale="the turn is factual/technical/delegated work rather than personal conversation",
            )

        intent_type = intent.intent_type if intent is not None else None

        if intent_type in self._TASK_INTENTS:
            return TurnPolicyDecision(
                category="task_general",
                generation_purpose=None,
                local_first=False,
                rationale=f"{intent_type.value} defaults to the normal task/general provider route",
            )

        if intent_type in self._LOCAL_INTENTS or intent_type is None:
            return TurnPolicyDecision(
                category="character_conversation",
                generation_purpose="conversation",
                local_first=True,
                rationale="ordinary character conversation stays local-first",
            )

        # QUESTION is intentionally resolved last. A bare question without a
        # task signature is more likely to be conversational than operational.
        if intent_type == IntentType.QUESTION:
            return TurnPolicyDecision(
                category="character_conversation",
                generation_purpose="conversation",
                local_first=True,
                rationale="question has no factual/task signature, so preserve Mary's conversational route",
            )

        return TurnPolicyDecision(
            category="task_general",
            generation_purpose=None,
            local_first=False,
            rationale="unclassified operational turn uses the normal task/general route",
        )

    def status(self) -> dict[str, Any]:
        return {
            "connected": True,
            "version": self.VERSION,
            "conversation_policy": "local_first",
            "task_policy": "free_first",
            "paid_expert_policy": "explicit_per_task_only",
        }

    @staticmethod
    def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
