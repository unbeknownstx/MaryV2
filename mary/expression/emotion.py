"""
MaryV2 - Emotional Expression System

Defines Mary's internal expressive/emotional state.

This module does NOT attempt to model human consciousness.

Instead, it provides a structured state representation that other
MaryV2 systems can use when deciding how Mary should respond.

Potential influences include:

    - perception
    - cognition
    - memory
    - personality
    - relationship state
    - goals
    - events
    - conversation context

The emotional state should influence expression, not override
reasoning or safety controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any


# ================================================================
# EMOTIONS
# ================================================================


class Emotion(str, Enum):
    """
    High-level emotional states available to Mary.

    These are expressive states rather than claims about biological
    human emotion.
    """

    NEUTRAL = "neutral"

    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"

    LOVE = "love"
    AFFECTION = "affection"
    WARMTH = "warmth"
    APPRECIATION = "appreciation"
    GRATITUDE = "gratitude"

    CURIOSITY = "curiosity"
    EXCITEMENT = "excitement"
    SURPRISE = "surprise"

    CONFUSION = "confusion"
    FRUSTRATION = "frustration"

    CALM = "calm"
    CONCERN = "concern"

    PRIDE = "pride"
    DISAPPOINTMENT = "disappointment"

    HOPE = "hope"
    LONELINESS = "loneliness"


# ================================================================
# INTENSITY
# ================================================================


class EmotionIntensity(str, Enum):
    """
    Human-readable intensity categories.

    Numeric intensity is still stored separately so systems can
    perform calculations.
    """

    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


# ================================================================
# EMOTIONAL SIGNAL
# ================================================================


@dataclass(frozen=True)
class EmotionalSignal:
    """
    A temporary influence on Mary's emotional state.

    Example:

        emotion = JOY
        intensity = 0.7
        source = "positive_conversation"

    A signal is evidence for a state transition, not the state
    itself.
    """

    emotion: Emotion

    intensity: float

    source: str

    reason: str = ""

    timestamp: float = field(
        default_factory=time
    )

    duration: float | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError(
                "Emotion intensity must "
                "be between 0.0 and 1.0."
            )

        if not self.source.strip():
            raise ValueError(
                "Emotion signal source "
                "cannot be empty."
            )

        if (
            self.duration is not None
            and self.duration < 0
        ):
            raise ValueError(
                "Emotion signal duration "
                "cannot be negative."
            )


# ================================================================
# EMOTIONAL STATE
# ================================================================


@dataclass
class EmotionalState:
    """
    Mary's current expressive emotional state.

    The state contains:

        primary emotion
        intensity
        secondary emotions
        valence
        arousal
        confidence
        current signals
        metadata

    Valence:
        -1.0 = strongly negative
         0.0 = neutral
        +1.0 = strongly positive

    Arousal:
         0.0 = very calm
         1.0 = highly activated

    Confidence:
         0.0 = uncertain state
         1.0 = highly confident state
    """

    primary: Emotion = Emotion.NEUTRAL

    intensity: float = 0.0

    valence: float = 0.0

    arousal: float = 0.0

    confidence: float = 1.0

    # Emotional momentum is short-lived expressive continuity, not personality.
    # Strong/repeated events give a state inertia so Mary does not snap back to
    # neutral on the next mundane turn.
    momentum: float = 0.0

    resting: Emotion = Emotion.NEUTRAL

    secondary: dict[
        Emotion,
        float,
    ] = field(
        default_factory=dict
    )

    signals: list[
        EmotionalSignal
    ] = field(
        default_factory=list
    )

    updated_at: float = field(
        default_factory=time
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        self.intensity = _clamp(
            self.intensity
        )

        self.valence = _clamp(
            self.valence,
            minimum=-1.0,
            maximum=1.0,
        )

        self.arousal = _clamp(
            self.arousal
        )

        self.confidence = _clamp(
            self.confidence
        )

        self.momentum = _clamp(self.momentum)
        if not isinstance(self.resting, Emotion):
            try:
                self.resting = Emotion(str(self.resting))
            except ValueError:
                self.resting = Emotion.NEUTRAL

        self.secondary = {
            emotion: _clamp(
                intensity
            )
            for emotion, intensity
            in self.secondary.items()
        }

    # ============================================================
    # SIGNALS
    # ============================================================

    def apply_signal(
        self,
        signal: EmotionalSignal,
    ) -> None:
        """
        Apply an emotional signal to the state.

        The signal is blended into the existing state rather than
        instantly replacing it.
        """

        self.signals.append(
            signal
        )

        # Keep a bounded signal history.
        if len(
            self.signals
        ) > 50:
            self.signals = self.signals[
                -50:
            ]

        if (
            signal.emotion
            == self.primary
        ):
            self.intensity = _blend(
                self.intensity,
                signal.intensity,
                weight=0.65,
            )
            self.momentum = max(
                self.momentum,
                _blend(self.momentum, signal.intensity, weight=0.55),
            )

        else:
            self.secondary[
                signal.emotion
            ] = _blend(
                self.secondary.get(
                    signal.emotion,
                    0.0,
                ),
                signal.intensity,
                weight=0.65,
            )

            # A meaningful signal should be able to move Mary out of a
            # neutral rest state without requiring high intensity. Existing
            # non-neutral states remain resistant to weak competing signals.
            promote_from_neutral = (
                self.primary == Emotion.NEUTRAL
                and signal.intensity >= 0.25
            )

            replace_existing = (
                signal.intensity
                > self.intensity
                and signal.intensity
                >= 0.6
            )

            if promote_from_neutral or replace_existing:
                previous = (
                    self.primary
                )

                previous_intensity = (
                    self.intensity
                )

                self.primary = (
                    signal.emotion
                )

                self.intensity = (
                    signal.intensity
                )
                self.momentum = max(self.momentum * 0.5, signal.intensity)

                self.secondary.pop(
                    signal.emotion,
                    None,
                )

                if previous != Emotion.NEUTRAL:
                    self.secondary[
                        previous
                    ] = previous_intensity

        self.updated_at = time()

    # ============================================================
    # DECAY
    # ============================================================

    def decay(
        self,
        amount: float = 0.05,
    ) -> None:
        """Gradually relax expression while preserving short-lived momentum.

        ``momentum`` is deliberately ephemeral.  It makes a strong state decay
        more naturally across ordinary turns, but it always decays and never
        writes personality/developed-self state.
        """

        amount = _clamp(amount)
        previous_momentum = self.momentum
        self.momentum = max(0.0, self.momentum - (amount * 0.45))

        # High momentum resists an immediate reset, while a state with no
        # momentum preserves the legacy decay rate exactly.
        resistance = 1.0 - (0.65 * previous_momentum)
        effective_amount = amount * max(0.25, resistance)
        self.intensity = max(0.0, self.intensity - effective_amount)

        # A fading but still meaningful emotional residue remains expressible
        # until momentum itself has relaxed. This avoids primary=neutral after
        # one or two mundane turns following a strong event.
        if self.primary != self.resting and self.momentum > 0.03:
            residue_floor = min(0.16, self.momentum * 0.16)
            self.intensity = max(self.intensity, residue_floor)

        updated_secondary: dict[Emotion, float] = {}
        for emotion, intensity in self.secondary.items():
            remaining = max(0.0, intensity - amount)
            if remaining > 0.01:
                updated_secondary[emotion] = remaining
        self.secondary = updated_secondary

        if self.intensity <= 0.01 and self.momentum <= 0.02:
            self.intensity = 0.0
            if self.primary != self.resting:
                self.primary = self.resting

        self.updated_at = time()

    # ============================================================
    # QUERIES
    # ============================================================

    def get_intensity(
        self,
        emotion: Emotion,
    ) -> float:
        """
        Get current intensity for an emotion.
        """

        if emotion == self.primary:
            return self.intensity

        return self.secondary.get(
            emotion,
            0.0,
        )

    def is_active(
        self,
        emotion: Emotion,
        threshold: float = 0.25,
    ) -> bool:
        """
        Determine whether an emotion is meaningfully active.
        """

        return (
            self.get_intensity(
                emotion
            )
            >= threshold
        )

    def intensity_level(
        self,
    ) -> EmotionIntensity:
        """
        Convert numeric intensity into a category.
        """

        if self.intensity < 0.2:
            return EmotionIntensity.VERY_LOW

        if self.intensity < 0.4:
            return EmotionIntensity.LOW

        if self.intensity < 0.6:
            return EmotionIntensity.MODERATE

        if self.intensity < 0.8:
            return EmotionIntensity.HIGH

        return EmotionIntensity.VERY_HIGH

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize emotional state.
        """

        return {
            "primary": self.primary.value,
            "intensity": self.intensity,
            "intensity_level": (
                self.intensity_level().value
            ),
            "valence": self.valence,
            "arousal": self.arousal,
            "confidence": self.confidence,
            "momentum": self.momentum,
            "resting": self.resting.value,
            "secondary": {
                emotion.value: intensity
                for emotion, intensity
                in self.secondary.items()
                if intensity > 0.0
            },
            "updated_at": self.updated_at,
            "metadata": dict(
                self.metadata
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "EmotionalState":
        """
        Restore an emotional state from serialized data.
        """

        primary = Emotion(
            data.get(
                "primary",
                Emotion.NEUTRAL.value,
            )
        )

        secondary: dict[
            Emotion,
            float,
        ] = {}

        for name, intensity in (
            data.get(
                "secondary",
                {},
            ).items()
        ):
            try:
                emotion = Emotion(
                    name
                )
            except ValueError:
                continue

            secondary[
                emotion
            ] = float(
                intensity
            )

        return cls(
            primary=primary,
            intensity=float(
                data.get(
                    "intensity",
                    0.0,
                )
            ),
            valence=float(
                data.get(
                    "valence",
                    0.0,
                )
            ),
            arousal=float(
                data.get(
                    "arousal",
                    0.0,
                )
            ),
            confidence=float(
                data.get(
                    "confidence",
                    1.0,
                )
            ),
            momentum=float(data.get("momentum", 0.0) or 0.0),
            resting=Emotion(str(data.get("resting", Emotion.NEUTRAL.value))),
            secondary=secondary,
            updated_at=float(
                data.get(
                    "updated_at",
                    time(),
                )
            ),
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )


# ================================================================
# EMOTION MANAGER
# ================================================================


class EmotionManager:
    """
    Manages Mary's current emotional state.

    This provides a controlled interface for other subsystems.

    It does not decide why Mary should feel something.

    Cognition, memory, personality, relationship, and perception
    can provide signals; the manager maintains the resulting state.
    """

    def __init__(
        self,
        initial_state: EmotionalState | None = None,
    ) -> None:

        self.state = (
            initial_state
            if initial_state is not None
            else EmotionalState(
                primary=Emotion.NEUTRAL,
                intensity=0.0,
                valence=0.0,
                arousal=0.0,
                confidence=1.0,
            )
        )

    # ============================================================
    # SIGNALS
    # ============================================================

    def signal(
        self,
        emotion: Emotion,
        intensity: float,
        *,
        source: str,
        reason: str = "",
        duration: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EmotionalState:
        """
        Apply a new emotional signal.
        """

        emotional_signal = (
            EmotionalSignal(
                emotion=emotion,
                intensity=intensity,
                source=source,
                reason=reason,
                duration=duration,
                metadata=(
                    metadata
                    if metadata is not None
                    else {}
                ),
            )
        )

        self.state.apply_signal(
            emotional_signal
        )

        self._update_dimensions(
            emotion,
            intensity,
        )

        return self.state

    # ============================================================
    # DIMENSIONS
    # ============================================================

    def _update_dimensions(
        self,
        emotion: Emotion,
        intensity: float,
    ) -> None:
        """
        Update valence and arousal based on the current emotional
        signal.

        These mappings are intentionally approximate.

        They are not intended to be scientific claims about human
        emotional psychology.
        """

        valence_map = {
            Emotion.JOY: 0.8,
            Emotion.SADNESS: -0.7,
            Emotion.ANGER: -0.6,
            Emotion.FEAR: -0.7,
            Emotion.LOVE: 0.9,
            Emotion.AFFECTION: 0.8,
            Emotion.WARMTH: 0.75,
            Emotion.APPRECIATION: 0.78,
            Emotion.GRATITUDE: 0.8,
            Emotion.CURIOSITY: 0.3,
            Emotion.EXCITEMENT: 0.8,
            Emotion.SURPRISE: 0.1,
            Emotion.CONFUSION: -0.1,
            Emotion.FRUSTRATION: -0.5,
            Emotion.CALM: 0.5,
            Emotion.CONCERN: -0.3,
            Emotion.PRIDE: 0.7,
            Emotion.DISAPPOINTMENT: -0.6,
            Emotion.HOPE: 0.6,
            Emotion.LONELINESS: -0.7,
            Emotion.NEUTRAL: 0.0,
        }

        arousal_map = {
            Emotion.JOY: 0.7,
            Emotion.SADNESS: 0.3,
            Emotion.ANGER: 0.9,
            Emotion.FEAR: 0.9,
            Emotion.LOVE: 0.6,
            Emotion.AFFECTION: 0.4,
            Emotion.WARMTH: 0.28,
            Emotion.APPRECIATION: 0.34,
            Emotion.GRATITUDE: 0.4,
            Emotion.CURIOSITY: 0.6,
            Emotion.EXCITEMENT: 0.9,
            Emotion.SURPRISE: 0.9,
            Emotion.CONFUSION: 0.6,
            Emotion.FRUSTRATION: 0.8,
            Emotion.CALM: 0.1,
            Emotion.CONCERN: 0.6,
            Emotion.PRIDE: 0.6,
            Emotion.DISAPPOINTMENT: 0.4,
            Emotion.HOPE: 0.5,
            Emotion.LONELINESS: 0.4,
            Emotion.NEUTRAL: 0.0,
        }

        target_valence = (
            valence_map.get(
                emotion,
                0.0,
            )
        )

        target_arousal = (
            arousal_map.get(
                emotion,
                0.0,
            )
        )

        self.state.valence = _blend(
            self.state.valence,
            target_valence,
            weight=intensity,
        )

        self.state.arousal = _blend(
            self.state.arousal,
            target_arousal,
            weight=intensity,
        )

    # ============================================================
    # DECAY
    # ============================================================

    def decay(
        self,
        amount: float = 0.05,
    ) -> EmotionalState:
        """Decay expressive intensity and relax dimensions toward neutral."""

        amount = _clamp(
            amount
        )

        self.state.decay(
            amount
        )

        dimension_weight = min(
            1.0,
            amount * 1.5 * (1.0 - 0.55 * self.state.momentum),
        )

        self.state.valence = _blend(
            self.state.valence,
            0.0,
            weight=dimension_weight,
        )

        self.state.arousal = _blend(
            self.state.arousal,
            0.0,
            weight=dimension_weight,
        )

        return self.state

    # ============================================================
    # RESET
    # ============================================================

    def reset(
        self,
    ) -> EmotionalState:
        """
        Return Mary to a neutral expressive state.
        """

        self.state = EmotionalState()

        return self.state

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def snapshot(
        self,
    ) -> dict[str, Any]:
        """
        Return a serializable emotional snapshot.
        """

        return self.state.to_dict()


# ================================================================
# HELPERS
# ================================================================


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    """
    Clamp a numeric value to a range.
    """

    return max(
        minimum,
        min(
            maximum,
            float(value),
        ),
    )


def _blend(
    current: float,
    target: float,
    *,
    weight: float,
) -> float:
    """
    Blend current and target values.
    """

    weight = _clamp(
        weight
    )

    return (
        current
        + (
            target
            - current
        )
        * weight
    )


# ================================================================
# DEFAULT STATE
# ================================================================


def create_emotion_manager(
    initial_state: EmotionalState | None = None,
) -> EmotionManager:
    """
    Create Mary's emotion manager.
    """

    return EmotionManager(
        initial_state=initial_state
    )