"""Deterministic turn-end policy for realtime Mary conversation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TurnEndEvidence:
    transcript: str = ""
    speech_active: bool = False
    silence_ms: float = 0.0
    stt_final: bool = False
    semantic_end_probability: float | None = None


@dataclass(frozen=True)
class TurnEndDecision:
    complete: bool
    confidence: float
    wait_ms: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TurnEndPolicy:
    """Fuse VAD/STT timing with an optional local semantic end score."""

    VERSION = "13.18"

    def __init__(self, *, settle_ms: int = 360, hard_ms: int = 1100) -> None:
        self.settle_ms = max(120, min(1500, int(settle_ms)))
        self.hard_ms = max(self.settle_ms + 100, min(4000, int(hard_ms)))

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def decide(self, evidence: TurnEndEvidence) -> TurnEndDecision:
        text = " ".join(str(evidence.transcript or "").split())
        silence = max(0.0, float(evidence.silence_ms or 0.0))
        if evidence.speech_active or not text:
            return TurnEndDecision(False, 0.0, self.settle_ms, "speech_active_or_empty")

        score = 0.0
        reasons: list[str] = []
        if evidence.stt_final:
            score += 0.30
            reasons.append("stt_final")
        if text.endswith((".", "?", "!", "…")):
            score += 0.20
            reasons.append("terminal_punctuation")
        semantic = evidence.semantic_end_probability
        if semantic is not None:
            semantic = self._clamp(semantic)
            score += 0.40 * semantic
            reasons.append(f"semantic={semantic:.2f}")
        if silence >= self.settle_ms:
            score += min(0.30, 0.12 + (0.18 * min(1.0, silence / self.hard_ms)))
            reasons.append(f"silence={int(silence)}ms")

        score = self._clamp(score)
        complete = bool(
            (semantic is not None and semantic >= 0.72 and silence >= self.settle_ms)
            or (silence >= self.hard_ms and evidence.stt_final)
            or (score >= 0.72 and silence >= self.settle_ms)
        )
        wait_ms = 0 if complete else max(80, int(self.settle_ms - min(silence, self.settle_ms)))
        if complete:
            reasons.append("complete")
        return TurnEndDecision(complete, round(score, 3), wait_ms, ",".join(reasons))

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "settle_ms": self.settle_ms,
            "hard_ms": self.hard_ms,
            "semantic_signal": "optional",
            "audio_capture": "external",
        }
