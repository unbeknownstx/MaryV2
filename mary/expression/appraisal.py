"""Conversation emotion appraisal for MaryV2.

This module turns one completed conversation turn into a conservative
expressive signal for Mary's existing :class:`EmotionManager`.

It does not call an LLM, browse, write memory, or infer hidden facts about
Unbe.  It only uses the current user message, Mary's already-produced reply,
and the already-detected intent.  Mary's perceived creator emotion is kept
separate from Mary's own expressive response emotion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from time import time
from typing import Any

from mary.cognition.intent import Intent, IntentType
from mary.expression.emotion import Emotion, EmotionManager, EmotionalState


@dataclass(frozen=True)
class ConversationEmotionAppraisal:
    """A bounded interpretation of one conversation turn."""

    emotion: Emotion = Emotion.NEUTRAL
    intensity: float = 0.0
    confidence: float = 0.0
    reason: str = "no meaningful emotional signal"
    creator_emotion: str | None = None
    creator_valence: float = 0.0
    relationship_relevance: float = 0.0
    source: str = "conversation_appraisal"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_meaningful(self) -> bool:
        return self.emotion != Emotion.NEUTRAL and self.intensity >= 0.25

    def to_dict(self) -> dict[str, Any]:
        return {
            "emotion": self.emotion.value,
            "intensity": self.intensity,
            "confidence": self.confidence,
            "reason": self.reason,
            "creator_emotion": self.creator_emotion,
            "creator_valence": self.creator_valence,
            "relationship_relevance": self.relationship_relevance,
            "source": self.source,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class _Candidate:
    emotion: Emotion
    intensity: float
    confidence: float
    reason: str
    creator_emotion: str | None = None
    creator_valence: float = 0.0
    relationship_relevance: float = 1.0
    source: str = "conversation_appraisal"

    @property
    def score(self) -> float:
        return self.intensity * self.confidence


class ConversationEmotionAppraiser:
    """Derive Mary's expressive reaction from one already-completed turn.

    The classifier is intentionally conservative.  It prefers explicit
    self-reports and multi-word conversational events over isolated keywords.
    Mary's own first-person emotional wording in the completed reply may be
    used as supporting evidence because the normal reasoning pass has already
    interpreted the conversation.
    """

    _MARY_SELF_EXPRESSIONS: tuple[tuple[re.Pattern[str], Emotion, float], ...] = (
        (re.compile(r"\b(?:i(?:'m| am)|that makes me)\s+(?:really\s+)?curious\b", re.I), Emotion.CURIOSITY, 0.58),
        (re.compile(r"\b(?:i(?:'m| am)|that makes me)\s+(?:really\s+)?excited\b", re.I), Emotion.EXCITEMENT, 0.70),
        (re.compile(r"\b(?:i(?:'m| am)\s+)?(?:really\s+)?glad\b", re.I), Emotion.JOY, 0.58),
        (re.compile(r"\b(?:i(?:'m| am)|that makes me)\s+(?:really\s+)?happy\b", re.I), Emotion.JOY, 0.62),
        (re.compile(r"\b(?:i(?:'m| am)|that makes me)\s+(?:really\s+)?proud\b", re.I), Emotion.PRIDE, 0.68),
        (re.compile(r"\b(?:i(?:'m| am)|that makes me)\s+(?:really\s+)?concerned\b", re.I), Emotion.CONCERN, 0.62),
        (re.compile(r"\b(?:i(?:'m| am)|that makes me)\s+(?:really\s+)?worried\b", re.I), Emotion.CONCERN, 0.65),
        (re.compile(r"\b(?:i(?:'m| am)|that makes me)\s+(?:really\s+)?grateful\b", re.I), Emotion.GRATITUDE, 0.64),
        (re.compile(r"\bi\s+(?:really\s+)?appreciate\b", re.I), Emotion.GRATITUDE, 0.58),
        (re.compile(r"\b(?:i(?:'m| am)|that makes me)\s+(?:really\s+)?surprised\b", re.I), Emotion.SURPRISE, 0.58),
        (re.compile(r"\b(?:i(?:'m| am)|that makes me)\s+(?:really\s+)?confused\b", re.I), Emotion.CONFUSION, 0.52),
        (re.compile(r"\b(?:i(?:'m| am)|that makes me)\s+(?:really\s+)?hopeful\b", re.I), Emotion.HOPE, 0.58),
    )

    _CREATOR_FRUSTRATION = re.compile(
        r"\b(?:i(?:'m| am)\s+(?:really\s+)?(?:frustrated|annoyed|fed up|stuck)|"
        r"this\s+(?:still\s+)?(?:keeps\s+)?(?:breaking|failing)|"
        r"it\s+(?:still\s+)?(?:keeps\s+)?(?:breaking|failing|not working)|"
        r"nothing\s+(?:is\s+)?working)\b",
        re.I,
    )
    _CREATOR_SADNESS = re.compile(
        r"\b(?:i(?:'m| am)\s+(?:really\s+)?(?:sad|hurt|heartbroken|lonely)|"
        r"i\s+(?:really\s+)?miss\s+|"
        r"(?:my|a|the)\s+\w+\s+(?:died|passed away))",
        re.I,
    )
    _ACHIEVEMENT = re.compile(
        r"\b(?:i\s+finally\s+(?:finished|completed|got|made|fixed|solved)|"
        r"i\s+(?:did it|passed|finished|completed|fixed it|got it working)|"
        r"it\s+(?:finally\s+)?works|"
        r"we\s+(?:did it|got it working|finished it)|"
        r"(?:all|the)\s+tests?\s+passed)\b",
        re.I,
    )
    _NEGATED_ACHIEVEMENT = re.compile(
        r"\b(?:didn['’]?t|did not|haven['’]?t|have not|can['’]?t|cannot|not)\b.{0,24}\b(?:finish|finished|complete|completed|pass|passed|work|works|fixed)\b",
        re.I,
    )
    _GRATITUDE = re.compile(
        r"\b(?:thank you|thanks mary|thanks,? mary|i appreciate you|i appreciate that|appreciate you)\b",
        re.I,
    )
    _AFFECTION = re.compile(
        r"\b(?:i love you,? mary|love you,? mary|i care about you,? mary)\b",
        re.I,
    )
    _POSITIVE_EXCITEMENT = re.compile(
        r"\b(?:that(?:'s| is)\s+(?:awesome|amazing|perfect)|this is awesome|let['’]?s go|hell yeah|yes!+)\b",
        re.I,
    )
    _NEGATIVE_FEEDBACK = re.compile(
        r"\b(?:that(?:'s| is)\s+(?:wrong|not right)|you got that wrong|that didn['’]?t work|no,? that['’]?s not)\b",
        re.I,
    )

    def __init__(self, *, creator_name: str = "Unbe") -> None:
        self.creator_name = str(creator_name or "Unbe").strip() or "Unbe"

    def appraise(
        self,
        *,
        input_text: str,
        response_text: str = "",
        intent: Intent | None = None,
    ) -> ConversationEmotionAppraisal:
        user_text = str(input_text or "").strip()
        reply = str(response_text or "").strip()
        candidates: list[_Candidate] = []

        # Mary's own already-generated first-person emotional language is
        # useful semantic evidence without requiring another model call.
        for pattern, emotion, intensity in self._MARY_SELF_EXPRESSIONS:
            if pattern.search(reply):
                candidates.append(
                    _Candidate(
                        emotion=emotion,
                        intensity=intensity,
                        confidence=0.86,
                        reason=f"Mary's completed reply explicitly expresses {emotion.value}",
                        source="mary_response_expression",
                    )
                )

        # Explicit creator emotional self-report maps to Mary's *response*
        # emotion, not a copied creator emotion.
        if self._CREATOR_FRUSTRATION.search(user_text):
            candidates.append(
                _Candidate(
                    emotion=Emotion.CONCERN,
                    intensity=0.64,
                    confidence=0.94,
                    reason="Unbe explicitly expressed frustration or being stuck",
                    creator_emotion="frustration",
                    creator_valence=-0.65,
                    source="creator_explicit_emotion",
                )
            )

        if self._CREATOR_SADNESS.search(user_text):
            candidates.append(
                _Candidate(
                    emotion=Emotion.CONCERN,
                    intensity=0.70,
                    confidence=0.94,
                    reason="Unbe explicitly expressed sadness, hurt, loneliness, or loss",
                    creator_emotion="sadness",
                    creator_valence=-0.80,
                    source="creator_explicit_emotion",
                )
            )

        if self._ACHIEVEMENT.search(user_text) and not self._NEGATED_ACHIEVEMENT.search(user_text):
            candidates.append(
                _Candidate(
                    emotion=Emotion.PRIDE,
                    intensity=0.70,
                    confidence=0.90,
                    reason="Unbe described a completed achievement or successful breakthrough",
                    creator_emotion="positive_achievement",
                    creator_valence=0.85,
                    source="creator_achievement",
                )
            )

        if self._GRATITUDE.search(user_text):
            candidates.append(
                _Candidate(
                    emotion=Emotion.GRATITUDE,
                    intensity=0.60,
                    confidence=0.95,
                    reason="Unbe directly expressed thanks or appreciation to Mary",
                    creator_emotion="gratitude",
                    creator_valence=0.80,
                    source="creator_direct_expression",
                )
            )

        if self._AFFECTION.search(user_text):
            candidates.append(
                _Candidate(
                    emotion=Emotion.AFFECTION,
                    intensity=0.68,
                    confidence=0.94,
                    reason="Unbe directly expressed affection toward Mary",
                    creator_emotion="affection",
                    creator_valence=0.90,
                    source="creator_direct_expression",
                )
            )

        if self._POSITIVE_EXCITEMENT.search(user_text):
            candidates.append(
                _Candidate(
                    emotion=Emotion.EXCITEMENT,
                    intensity=0.62,
                    confidence=0.82,
                    reason="The current exchange contains an explicit positive breakthrough reaction",
                    creator_emotion="excitement",
                    creator_valence=0.78,
                    source="conversation_event",
                )
            )

        if self._NEGATIVE_FEEDBACK.search(user_text):
            candidates.append(
                _Candidate(
                    emotion=Emotion.CONCERN,
                    intensity=0.46,
                    confidence=0.84,
                    reason="Unbe gave direct negative feedback about Mary's current response or result",
                    creator_emotion="dissatisfaction",
                    creator_valence=-0.45,
                    source="creator_feedback",
                )
            )

        if intent is not None:
            if intent.intent_type == IntentType.RELATIONSHIP_SHARE:
                candidates.append(
                    _Candidate(
                        emotion=Emotion.CURIOSITY,
                        intensity=0.43,
                        confidence=0.82,
                        reason="Unbe explicitly shared new relationship information with Mary",
                        relationship_relevance=1.0,
                        source="relationship_share",
                    )
                )
            elif intent.intent_type == IntentType.EMOTIONAL_SUPPORT:
                candidates.append(
                    _Candidate(
                        emotion=Emotion.CONCERN,
                        intensity=0.58,
                        confidence=0.78,
                        reason="The detected conversational intent calls for emotional support",
                        relationship_relevance=1.0,
                        source="intent",
                    )
                )
            elif intent.intent_type in {IntentType.QUESTION, IntentType.SELF_QUERY} and "?" in user_text:
                candidates.append(
                    _Candidate(
                        emotion=Emotion.CURIOSITY,
                        intensity=0.30,
                        confidence=0.60,
                        reason="The conversation invites a low-intensity curious response",
                        relationship_relevance=0.65,
                        source="intent",
                    )
                )

        if not candidates:
            return ConversationEmotionAppraisal(
                metadata={
                    "candidate_count": 0,
                    "creator_name": self.creator_name,
                }
            )

        best = max(candidates, key=lambda item: item.score)
        return ConversationEmotionAppraisal(
            emotion=best.emotion,
            intensity=_clamp(best.intensity),
            confidence=_clamp(best.confidence),
            reason=best.reason,
            creator_emotion=best.creator_emotion,
            creator_valence=max(-1.0, min(1.0, best.creator_valence)),
            relationship_relevance=_clamp(best.relationship_relevance),
            source=best.source,
            metadata={
                "candidate_count": len(candidates),
                "creator_name": self.creator_name,
            },
        )

    def apply(
        self,
        manager: EmotionManager,
        appraisal: ConversationEmotionAppraisal,
        *,
        now: float | None = None,
    ) -> EmotionalState:
        """Decay the prior state, then apply one bounded appraisal signal."""

        if not isinstance(manager, EmotionManager):
            raise TypeError("manager must be an EmotionManager instance")

        current_time = float(time() if now is None else now)
        elapsed = max(0.0, current_time - float(manager.state.updated_at))

        # Every completed turn relaxes the previous state slightly. Longer
        # pauses add additional decay, capped so one appraisal never produces
        # an abrupt emotional reset.
        decay_amount = 0.07 + min(0.18, (elapsed / 300.0) * 0.18)
        manager.decay(decay_amount)

        if appraisal.is_meaningful:
            manager.signal(
                appraisal.emotion,
                appraisal.intensity,
                source=appraisal.source,
                reason=appraisal.reason,
                metadata={
                    "appraisal_confidence": appraisal.confidence,
                    "creator_emotion": appraisal.creator_emotion,
                    "creator_valence": appraisal.creator_valence,
                    "relationship_relevance": appraisal.relationship_relevance,
                },
            )
            manager.state.confidence = appraisal.confidence

        manager.state.metadata["last_conversation_appraisal"] = appraisal.to_dict()
        manager.state.metadata["perceived_creator_emotion"] = appraisal.creator_emotion
        manager.state.metadata["appraisal_updated_at"] = current_time
        return manager.state


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
