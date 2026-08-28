"""MaryV2 conversational continuity and local repair state.

This module is deliberately deterministic. It reads the recent DialogueManager
history and derives conversational moves, question budget, style repetition, and
recently rejected interpretations. It does not create durable memory or call an
LLM.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
import re
from typing import Any

from mary.cognition.intent import IntentType
from mary.cognition.natural_input import normalize_for_matching


_WORD_RE = re.compile(r"[a-z0-9']+")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for",
    "with", "that", "this", "it", "i", "im", "i'm", "you", "your", "we",
    "our", "me", "my", "is", "are", "was", "were", "be", "been", "being",
    "do", "did", "does", "have", "has", "had", "so", "just", "like", "kind",
    "really", "actually", "maybe", "think", "thing", "things", "sounds",
    "there", "what", "when", "where", "which", "would", "could", "should",
    "about", "because", "from", "into", "still", "even", "only", "know",
}
_REPAIR_MARKERS = (
    "that's not really what i meant", "that's not what i meant", "not what i meant",
    "you misunderstood", "that's not it", "no that's not it", "not what i'm saying",
)
_DISAGREEMENT_MARKERS = (
    "i don't agree", "i don't know if i agree", "not sure i agree", "i disagree",
    "nah i don't totally agree", "no i don't agree",
)
_STYLE_MOTIFS = {
    "quiet", "spark", "sparks", "magic", "soft", "glow", "buzz", "chest",
    "together", "presence", "vibe", "moment", "moments", "rainy", "silence",
    "doodling", "little", "wild", "chaos",
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
    recent_overused_terms: tuple[str, ...]
    rejected_hypothesis_terms: tuple[str, ...]
    recent_question_count: int
    consecutive_question_turns: int
    allow_follow_up_question: bool
    max_follow_up_questions: int
    interaction_momentum: float
    cadence_mode: str
    instructions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "drive": self.drive.value,
            "recent_drives": list(self.recent_drives),
            "recent_mary_responses": list(self.recent_mary_responses),
            "recent_openings": list(self.recent_openings),
            "recent_distinctive_terms": list(self.recent_distinctive_terms),
            "recent_overused_terms": list(self.recent_overused_terms),
            "rejected_hypothesis_terms": list(self.rejected_hypothesis_terms),
            "recent_question_count": self.recent_question_count,
            "consecutive_question_turns": self.consecutive_question_turns,
            "allow_follow_up_question": self.allow_follow_up_question,
            "max_follow_up_questions": self.max_follow_up_questions,
            "interaction_momentum": round(float(self.interaction_momentum), 3),
            "cadence_mode": self.cadence_mode,
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
        ][-5:]

        recent_drives = tuple(self._infer_drive(text).value for text in mary_responses[-3:])
        openings = tuple(self._opening(text) for text in mary_responses[-3:] if self._opening(text))
        distinctive = self._distinctive_terms(mary_responses[-3:])
        overused = self._overused_terms(mary_responses[-4:], input_text=input_text)
        rejected = self._rejected_hypothesis_terms(recent_conversation)

        last_three = mary_responses[-3:]
        question_count = sum(1 for text in last_three if "?" in text)
        consecutive_questions = 0
        for text in reversed(last_three):
            if "?" not in text:
                break
            consecutive_questions += 1

        allow_question = consecutive_questions == 0 and question_count < 2
        max_questions = 1 if allow_question else 0

        drive = self._select_drive(
            input_text=input_text,
            intent_type=intent_type,
            recent_drives=recent_drives,
            active_curiosity=active_curiosity,
            allow_question=allow_question,
        )

        normalized_input = normalize_for_matching(input_text)
        question_invited = any(
            phrase in normalized_input
            for phrase in (
                "ask me",
                "you can ask",
                "u can ask",
                "anything you want to know",
                "anything u want to know",
                "what do you want to know",
                "what do u want to know",
                "got any questions",
            )
        )

        milestone_update = (
            drive == ConversationalDrive.REACT
            and any(
                marker in normalized_input
                for marker in (
                    "finally", "passed", "finished", "milestone", "got it",
                    "fixed", "solved", "got everything working", "got it working",
                )
            )
        )

        # Opinion/repair/disagreement turns should land on Mary's own thought
        # instead of reflexively handing the conversation back to Unbe. Explicit
        # invitations to ask still win. This makes independence visible in the
        # dialogue rather than merely represented in character data.
        if (
            (
                drive in {
                    ConversationalDrive.OPINE,
                    ConversationalDrive.DISAGREE,
                    ConversationalDrive.REFLECT,
                }
                or milestone_update
            )
            and not question_invited
        ):
            allow_question = False
            max_questions = 0

        interaction_momentum = self._interaction_momentum(
            input_text=input_text,
            recent_conversation=recent_conversation,
        )
        cadence_mode = (
            "lively" if interaction_momentum >= 0.68
            else "engaged" if interaction_momentum >= 0.42
            else "quiet"
        )

        instruction_items = [
            f"Primary conversational move for this turn: {drive.value}. Do that move before considering any secondary move.",
            "Do not repeat Mary's recent opening, metaphor, punchline, question structure, or conversational move when a different natural move works.",
            (
                "A follow-up question is allowed, but optional; ask at most one only if it genuinely improves this turn."
                if allow_question
                else "Do not end this turn with a follow-up question; Mary has asked enough questions recently. Make a statement, reaction, opinion, recollection, or reflection and stop naturally."
            ),
            "Curiosity can appear as noticing, wondering, hypothesizing, remembering, or forming an opinion; it does not require Mary to ask Unbe a question.",
            "When Mary has an opinion, let her state it instead of reflexively bouncing the decision back to Unbe.",
            "Color, slang, emoji, and metaphor are optional texture. Do not make every casual reply poetic or decorate every turn.",
            (
                f"Ephemeral interaction cadence is {cadence_mode} ({interaction_momentum:.2f}). "
                "This reflects only observable conversational rhythm, not Unbe's hidden emotion or a durable trait. "
                "Let lively rhythm modestly increase immediacy/animation when the subject is light; serious emotion or moral stakes always override it."
            ),
        ]

        if overused:
            instruction_items.append(
                "Mary has recently overused these model-generated style motifs: "
                + ", ".join(overused[:8])
                + ". Avoid recycling them this turn unless Unbe himself reintroduced one. Use fresher plain language."
            )
        if rejected:
            instruction_items.append(
                "A recent interpretation was corrected/rejected. Do not quietly regenerate the same hypothesis. "
                "Treat these terms as temporarily suppressed unless Unbe supplies new evidence: "
                + ", ".join(rejected[:10])
                + "."
            )

        if any(marker in normalized_input for marker in _REPAIR_MARKERS):
            instruction_items.append(
                "Unbe is correcting Mary's interpretation. Drop the prior hypothesis instead of defending it, "
                "acknowledge the correction, and re-anchor only on what he actually said. Do not invent a hidden motive."
            )
        if intent_type == IntentType.FEEDBACK:
            instruction_items.append(
                "Unbe is reacting to Mary herself. Receive the relational/character feedback first; do not pivot into a canned capability or speech-style explanation unless he actually asked for one."
            )
        if drive == ConversationalDrive.DISAGREE and any(
            phrase in normalized_input
            for phrase in _DISAGREEMENT_MARKERS + ("why do you think that", "why do you say that")
        ):
            instruction_items.append(
                "Unbe is challenging Mary's position. Explain the reasoning, revise it if warranted, or hold the disagreement honestly; do not erase the disagreement by claiming you already agree."
            )

        return ContinuitySnapshot(
            drive=drive,
            recent_drives=recent_drives,
            recent_mary_responses=tuple(mary_responses[-3:]),
            recent_openings=openings,
            recent_distinctive_terms=distinctive,
            recent_overused_terms=overused,
            rejected_hypothesis_terms=rejected,
            recent_question_count=question_count,
            consecutive_question_turns=consecutive_questions,
            allow_follow_up_question=allow_question,
            max_follow_up_questions=max_questions,
            interaction_momentum=interaction_momentum,
            cadence_mode=cadence_mode,
            instructions=tuple(instruction_items),
        )

    @staticmethod
    def _interaction_momentum(
        *,
        input_text: str,
        recent_conversation: list[dict[str, str]],
    ) -> float:
        """Estimate observable turn rhythm without inferring private emotion.

        This value is intentionally ephemeral and recomputed from the immediate
        transcript.  It is a pacing signal only: it is never memory, relationship
        evidence, or a claim that the creator *feels* excited/happy/etc.
        """

        items = [
            item for item in recent_conversation[-8:]
            if isinstance(item, dict) and str(item.get("content", "")).strip()
        ]
        density = min(1.0, len(items) / 8.0)

        alternating = 0
        previous_role = ""
        for item in items:
            role = str(item.get("role", ""))
            if previous_role and role and role != previous_role:
                alternating += 1
            previous_role = role
        alternation = min(1.0, alternating / 5.0)

        text = str(input_text or "").strip()
        normalized = normalize_for_matching(text)
        words = _WORD_RE.findall(text.lower())
        brevity = 1.0 if 0 < len(words) <= 12 else 0.55 if len(words) <= 28 else 0.2
        punctuation = min(1.0, (text.count("!") * 0.28) + (text.count("?") * 0.08))
        lively_markers = (
            "lol", "lmao", "haha", "hell yeah", "hell yea", "lets go", "let's go",
            "no way", "bro", "dude", "wild", "awesome", "nice", "yooo", "yo ",
        )
        marker_signal = 1.0 if any(marker in normalized for marker in lively_markers) else 0.0

        # All-caps is only a surface cue and is bounded so one acronym does not
        # make a turn hyperactive.
        alpha = [c for c in text if c.isalpha()]
        uppercase_ratio = (
            sum(1 for c in alpha if c.isupper()) / len(alpha)
            if len(alpha) >= 6 else 0.0
        )
        caps_signal = min(1.0, max(0.0, (uppercase_ratio - 0.35) * 1.8))

        score = (
            0.08
            + density * 0.22
            + alternation * 0.24
            + brevity * 0.16
            + punctuation * 0.12
            + marker_signal * 0.14
            + caps_signal * 0.04
        )
        return max(0.0, min(1.0, score))

    def _select_drive(
        self,
        *,
        input_text: str,
        intent_type: IntentType,
        recent_drives: tuple[str, ...],
        active_curiosity: bool,
        allow_question: bool,
    ) -> ConversationalDrive:
        lowered = normalize_for_matching(input_text)

        if intent_type == IntentType.CONVERSATION_RECALL:
            return ConversationalDrive.RECALL
        if any(phrase in lowered for phrase in _REPAIR_MARKERS):
            return ConversationalDrive.REFLECT
        if any(phrase in lowered for phrase in _DISAGREEMENT_MARKERS + (
            "you can disagree", "disagree with me", "don't agree with me",
            "why do you think that", "why do you say that", "defend that", "convince me",
            "what do you disagree with", "what do u disagree with", "where do you disagree",
            "what would you push back on", "what would u push back on", "push back on me",
            "challenge me",
        )):
            return ConversationalDrive.DISAGREE
        if any(phrase in lowered for phrase in (
            "roast me", "make fun of me", "bet you can't", "bet u cant",
            "fight me", "come at me", "youre weird", "you're weird",
        )):
            return ConversationalDrive.TEASE
        if lowered.startswith(("hmm", "hm ", "idk", "i wonder", "what if", "maybe ")):
            return ConversationalDrive.THINK_ALOUD
        if lowered in {"hey", "hey mary", "hi", "hi mary", "yo", "yo mary", "sup", "what up"}:
            return ConversationalDrive.ACKNOWLEDGE
        if any(word in lowered for word in ("finally", "passed", "finished", "worked", "working", "milestone", "got it", "fixed", "solved")):
            return ConversationalDrive.REACT
        if any(phrase in lowered for phrase in (
            "i think", "i feel like", "maybe we", "seems like", "overengineer", "over-engineer",
            "do you think i make any mistakes", "do you think i'm making any mistakes",
            "do you think i am making any mistakes", "what am i doing wrong",
            "what do you think i'm doing wrong", "what do you think i am doing wrong",
            "critique my", "give me your critique", "be critical of",
            "what do you really think", "what do you actually think",
            "what's your take", "whats your take", "give me your opinion",
            "your honest opinion", "be honest with me about",
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

    def _overused_terms(self, responses: list[str], *, input_text: str) -> tuple[str, ...]:
        """Find Mary-only motifs repeated across multiple immediately recent replies."""

        if len(responses) < 2:
            return ()
        user_terms = set(_WORD_RE.findall(normalize_for_matching(input_text)))
        counts: Counter[str] = Counter()
        last_position: dict[str, int] = {}
        for index, text in enumerate(responses):
            seen = {
                word
                for word in _WORD_RE.findall(text.lower())
                if len(word) >= 4 and word not in _STOPWORDS
            }
            for word in seen:
                counts[word] += 1
                last_position[word] = index
        candidates = [
            word for word, count in counts.items()
            if count >= 2 and word not in user_terms and (word in _STYLE_MOTIFS or count >= 3)
        ]
        candidates.sort(key=lambda word: (-counts[word], -last_position[word], word))
        return tuple(candidates[:12])

    def _rejected_hypothesis_terms(self, conversation: list[dict[str, str]]) -> tuple[str, ...]:
        """Derive the last interpretation Unbe explicitly rejected/corrected.

        This is session continuity, not durable memory. We look backward for the
        most recent creator repair/disagreement turn, then extract distinctive
        terms from Mary's immediately preceding response.
        """

        items = [item for item in conversation[-10:] if isinstance(item, dict)]
        for index in range(len(items) - 1, -1, -1):
            item = items[index]
            if str(item.get("role", "")) != "user":
                continue
            normalized = normalize_for_matching(str(item.get("content", "")))
            if not any(marker in normalized for marker in _REPAIR_MARKERS + _DISAGREEMENT_MARKERS):
                continue
            for prior in range(index - 1, -1, -1):
                previous = items[prior]
                if str(previous.get("role", "")) != "assistant":
                    continue
                terms = [
                    word
                    for word in _WORD_RE.findall(str(previous.get("content", "")).lower())
                    if len(word) >= 5 and word not in _STOPWORDS
                ]
                unique: list[str] = []
                for word in terms:
                    if word not in unique:
                        unique.append(word)
                return tuple(unique[:12])
        return ()


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
