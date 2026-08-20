"""MaryV2 conversational continuity and drive selection.

This module is deliberately local/deterministic.  It does not create another
memory store or call an LLM.  It interprets the recent DialogueManager history
so Mary's existing character systems can choose a conversational *move* and
avoid repeating the same move, question, opening, or wording turn after turn.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any

from mary.cognition.intent import IntentType


_WORD_RE = re.compile(r"[a-z0-9']+")
_QUESTION_STARTS = (
    "what ", "why ", "how ", "when ", "where ", "who ", "which ",
    "do ", "did ", "does ", "are ", "is ", "can ", "could ", "would ",
)
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for",
    "with", "that", "this", "it", "i", "im", "i'm", "you", "your", "we",
    "our", "me", "my", "is", "are", "was", "were", "be", "been", "being",
    "do", "did", "does", "have", "has", "had", "so", "just", "like", "kind",
    "really", "actually", "maybe", "think", "thing", "things", "sounds",
}


class ConversationalDrive(str, Enum):
    REACT = "react"
    ANSWER = "answer"
    OPINE = "opine"
    TEASE = "tease"
    REFLECT = "reflect"
    DISAGREE = "disagree"
    ASK = "ask"
    RECALL = "recall"
    CONTINUE = "continue"
    ACKNOWLEDGE = "acknowledge"
    THINK_ALOUD = "think_aloud"


@dataclass(frozen=True)
class ContinuitySnapshot:
    drive: ConversationalDrive
    recent_drives: tuple[str, ...]
    recent_mary_responses: tuple[str, ...]
    recent_openings: tuple[str, ...]
    recent_distinctive_terms: tuple[str, ...]
    recent_question_count: int
    consecutive_question_turns: int
    allow_follow_up_question: bool
    max_follow_up_questions: int
    instructions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "drive": self.drive.value,
            "recent_drives": list(self.recent_drives),
            "recent_mary_responses": list(self.recent_mary_responses),
            "recent_openings": list(self.recent_openings),
            "recent_distinctive_terms": list(self.recent_distinctive_terms),
            "recent_question_count": self.recent_question_count,
            "consecutive_question_turns": self.consecutive_question_turns,
            "allow_follow_up_question": self.allow_follow_up_question,
            "max_follow_up_questions": self.max_follow_up_questions,
            "instructions": list(self.instructions),
        }


class ConversationContinuity:
    """Derive conversational behavior from recent dialogue without an LLM."""

    def build(
        self,
        *,
        input_text: str,
        intent_type: IntentType,
        recent_conversation: list[dict[str, str]],
        active_curiosity: bool = False,
    ) -> ContinuitySnapshot:
        mary_responses = [
            str(item.get("content", "")).strip()
            for item in recent_conversation
            if isinstance(item, dict)
            and item.get("role") == "assistant"
            and str(item.get("content", "")).strip()
        ][-4:]

        recent_drives = tuple(self._infer_drive(text).value for text in mary_responses[-3:])
        openings = tuple(self._opening(text) for text in mary_responses[-3:] if self._opening(text))
        distinctive = self._distinctive_terms(mary_responses[-3:])

        last_three = mary_responses[-3:]
        question_count = sum(1 for text in last_three if "?" in text)
        consecutive_questions = 0
        for text in reversed(last_three):
            if "?" not in text:
                break
            consecutive_questions += 1

        # A follow-up is intentionally scarce.  Curiosity raises the *interest*
        # in a topic, not a requirement to interrogate Unbe every turn.
        allow_question = consecutive_questions == 0 and question_count < 2
        max_questions = 1 if allow_question else 0

        drive = self._select_drive(
            input_text=input_text,
            intent_type=intent_type,
            recent_drives=recent_drives,
            active_curiosity=active_curiosity,
            allow_question=allow_question,
        )

        instructions = (
            f"Primary conversational move for this turn: {drive.value}. Do that move before considering any secondary move.",
            "Do not repeat Mary's recent opening, metaphor, punchline, question structure, or conversational move when a different natural move works.",
            (
                "A follow-up question is allowed, but optional; ask at most one only if it genuinely improves this turn."
                if allow_question
                else "Do not end this turn with a follow-up question; Mary has asked enough questions recently. Make a statement, reaction, opinion, recollection, or reflection and stop naturally."
            ),
            "Curiosity can appear as noticing, wondering, hypothesizing, remembering, or forming an opinion; it does not require Mary to ask Unbe a question.",
            "When Mary has an opinion, let her state it instead of reflexively bouncing the decision back to Unbe.",
        )

        return ContinuitySnapshot(
            drive=drive,
            recent_drives=recent_drives,
            recent_mary_responses=tuple(mary_responses[-3:]),
            recent_openings=openings,
            recent_distinctive_terms=distinctive,
            recent_question_count=question_count,
            consecutive_question_turns=consecutive_questions,
            allow_follow_up_question=allow_question,
            max_follow_up_questions=max_questions,
            instructions=instructions,
        )

    def _select_drive(
        self,
        *,
        input_text: str,
        intent_type: IntentType,
        recent_drives: tuple[str, ...],
        active_curiosity: bool,
        allow_question: bool,
    ) -> ConversationalDrive:
        lowered = input_text.lower().strip()

        if intent_type == IntentType.CONVERSATION_RECALL:
            return ConversationalDrive.RECALL
        if any(phrase in lowered for phrase in ("you can disagree", "disagree with me", "don't agree with me", "dont agree with me")):
            return ConversationalDrive.DISAGREE
        if any(word in lowered for word in ("finally", "passed", "finished", "worked", "working", "milestone", "got it")):
            return ConversationalDrive.REACT
        if any(phrase in lowered for phrase in (
            "i think", "i feel like", "maybe we", "seems like", "overengineer", "over-engineer",
            "do you think i make any mistakes", "do you think i'm making any mistakes",
            "do you think i am making any mistakes", "what am i doing wrong",
            "what do you think i'm doing wrong", "what do you think i am doing wrong",
            "critique my", "give me your critique", "be critical of",
        )):
            return ConversationalDrive.OPINE
        if intent_type == IntentType.FEEDBACK:
            return ConversationalDrive.REFLECT
        if intent_type in {IntentType.QUESTION, IntentType.INFORMATION}:
            return ConversationalDrive.ANSWER
        if intent_type in {IntentType.REQUEST, IntentType.COMMAND, IntentType.TOOL_USE, IntentType.WEB_SEARCH}:
            return ConversationalDrive.ANSWER
        if lowered.startswith(("honestly", "be honest", "admit it")):
            return ConversationalDrive.REACT

        # Don't make ASK the default merely because curiosity is active.  It is
        # only selected when the input explicitly invites a question-like move.
        if active_curiosity and allow_question and any(
            phrase in lowered for phrase in ("ask me", "anything you want to know", "what are you curious")
        ):
            return ConversationalDrive.ASK

        if recent_drives and recent_drives[-1] == ConversationalDrive.REACT.value:
            return ConversationalDrive.OPINE
        return ConversationalDrive.REACT

    def _infer_drive(self, text: str) -> ConversationalDrive:
        lowered = text.lower().strip()
        if "?" in text:
            return ConversationalDrive.ASK
        if lowered.startswith(("i think", "honestly", "to me", "my take", "maybe")):
            return ConversationalDrive.OPINE
        if any(token in lowered for token in ("i disagree", "don't think", "dont think", "not sure i agree")):
            return ConversationalDrive.DISAGREE
        if any(token in lowered for token in ("i remember", "we were talking", "you said", "i said")):
            return ConversationalDrive.RECALL
        if lowered.startswith(("hmm", "wait", "oh", "yeah", "ha", "finally", "nice")):
            return ConversationalDrive.REACT
        return ConversationalDrive.CONTINUE

    def _opening(self, text: str) -> str:
        words = _WORD_RE.findall(text.lower())
        return " ".join(words[:4])

    def _distinctive_terms(self, responses: list[str]) -> tuple[str, ...]:
        terms: list[str] = []
        for text in responses:
            for word in _WORD_RE.findall(text.lower()):
                if len(word) < 5 or word in _STOPWORDS:
                    continue
                if word not in terms:
                    terms.append(word)
        return tuple(terms[-18:])


CONVERSATION_RECALL_PATTERNS = (
    "what were we just talking about",
    "what were we talking about",
    "what did we just talk about",
    "what have we been talking about",
    "what did i just say",
    "what did you just say",
    "what were you just saying",
    "what do you remember from what we were just talking about",
    "remember what we were just talking about",
    "remind me what we were talking about",
    "what was our last conversation about",
    "what have we been working on together",
    "what have we been working on",
    "what have we worked on together",
    "what are we working on together",
)


def is_conversation_recall_query(text: str) -> bool:
    lowered = " ".join(str(text).lower().split())
    if any(pattern in lowered for pattern in CONVERSATION_RECALL_PATTERNS):
        return True
    return bool(
        re.search(r"\b(what|remind me).{0,30}\b(just|recent|last).{0,25}\b(talk|say|said|discuss)", lowered)
    )
