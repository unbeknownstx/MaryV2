"""
MaryV2 - Preference Promotion System

Tracks tentative evidence that Mary may be developing a preference without
immediately rewriting her durable self-state.

Boundary:
    observation/evidence -> candidate -> eligible -> explicit promotion

Eligibility is deterministic and never auto-applies a durable preference.
Model dialogue, situational imagination, and other model-authored output are
not accepted as evidence sources.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid


class PreferencePromotionSystem:
    """Accumulate and evaluate evidence before durable preference promotion."""

    SCHEMA_VERSION = 1

    BLOCKED_SOURCES = {
        "model",
        "model_dialogue",
        "llm",
        "llm_output",
        "situational",
        "imagination",
    }

    def __init__(
        self,
        *,
        min_observations: int = 3,
        min_mean_confidence: float = 0.70,
        min_consistency: float = 0.75,
        min_mean_magnitude: float = 0.50,
    ) -> None:
        self.min_observations = max(2, int(min_observations))
        self.min_mean_confidence = self._clamp(min_mean_confidence)
        self.min_consistency = self._clamp(min_consistency)
        self.min_mean_magnitude = self._clamp(min_mean_magnitude)

        self.candidates: Dict[str, Dict[str, Any]] = {}
        self.history: List[Dict[str, Any]] = []

        self.path: Path | None = None
        self.auto_save = False
        self.loaded = False

    # ============================================================
    # CONFIGURATION / PERSISTENCE
    # ============================================================

    def configure(
        self,
        path: str | Path,
        *,
        auto_save: bool = True,
        load: bool = True,
    ) -> bool:
        """Enable persistence for the tentative evidence ledger."""

        self.path = Path(path)
        self.auto_save = bool(auto_save)

        if load:
            return self.load()

        return True

    @property
    def configured(self) -> bool:
        return self.path is not None

    def save_if_configured(self) -> bool:
        if not self.configured or not self.auto_save:
            return True
        return self.save()

    def save(self) -> bool:
        if self.path is None:
            return True

        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")

        try:
            temporary.write_text(
                json.dumps(
                    self.to_dict(),
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass

        return True

    def load(self) -> bool:
        if self.path is None:
            return True

        if not self.path.exists():
            self.loaded = True
            return True

        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return False

        self.load_dict(payload)
        self.loaded = True
        return True

    # ============================================================
    # OBSERVATION
    # ============================================================

    def observe(
        self,
        name: str,
        *,
        category: str = "general",
        strength: float = 0.5,
        polarity: float = 1.0,
        confidence: float = 0.5,
        source: str = "experience",
        reason: str = "",
        evidence_id: str | None = None,
    ) -> Dict[str, Any]:
        """Record one non-model piece of preference evidence.

        This does not mutate Mary's Preferences object and cannot promote a
        candidate by itself.
        """

        normalized_name = self._normalize_name(name)
        if not normalized_name:
            raise ValueError("Preference candidate name cannot be empty.")

        normalized_source = self._normalize_source(source)
        if normalized_source in self.BLOCKED_SOURCES:
            raise ValueError(
                "Model/situational output cannot be preference-promotion evidence."
            )

        normalized_evidence_id = str(
            evidence_id or f"evidence_{uuid.uuid4().hex}"
        ).strip()

        candidate = self.candidates.get(normalized_name)
        if candidate is None:
            now = datetime.now().isoformat()
            candidate = {
                "name": normalized_name,
                "category": str(category).strip().lower() or "general",
                "status": "candidate",
                "observations": [],
                "created_at": now,
                "updated_at": now,
            }
            self.candidates[normalized_name] = candidate

        # Idempotency: the same external experience/event cannot be counted
        # repeatedly merely because a caller retries the operation.
        for observation in candidate.get("observations", []):
            if str(observation.get("evidence_id", "")) == normalized_evidence_id:
                return self.evaluate(normalized_name)

        signed_score = self._signed_score(
            strength=strength,
            polarity=polarity,
        )

        observation = {
            "evidence_id": normalized_evidence_id,
            "signed_score": signed_score,
            "strength": abs(signed_score),
            "polarity": 1.0 if signed_score >= 0.0 else -1.0,
            "confidence": self._clamp(confidence),
            "source": normalized_source,
            "reason": str(reason).strip(),
            "timestamp": datetime.now().isoformat(),
        }

        candidate["category"] = str(category).strip().lower() or candidate.get(
            "category", "general"
        )
        candidate.setdefault("observations", []).append(observation)
        candidate["updated_at"] = observation["timestamp"]

        evaluation = self.evaluate(normalized_name)
        candidate["status"] = "eligible" if evaluation["eligible"] else "candidate"

        self.save_if_configured()
        return evaluation

    # ============================================================
    # EVALUATION
    # ============================================================

    def evaluate(self, name: str) -> Dict[str, Any]:
        """Deterministically evaluate one tentative preference candidate."""

        normalized_name = self._normalize_name(name)
        candidate = self.candidates.get(normalized_name)

        if candidate is None:
            return {
                "name": normalized_name,
                "eligible": False,
                "reason": "No preference candidate exists.",
                "observation_count": 0,
                "mean_confidence": 0.0,
                "consistency": 0.0,
                "mean_magnitude": 0.0,
                "direction": 0,
                "signed_mean": 0.0,
            }

        observations = [
            item
            for item in candidate.get("observations", [])
            if isinstance(item, dict)
        ]
        count = len(observations)

        if count == 0:
            return self._evaluation(
                normalized_name,
                eligible=False,
                reason="Candidate has no observations.",
            )

        scores = [float(item.get("signed_score", 0.0)) for item in observations]
        confidences = [
            self._clamp(item.get("confidence", 0.0))
            for item in observations
        ]

        positive = sum(1 for score in scores if score > 0.0)
        negative = sum(1 for score in scores if score < 0.0)
        directional = positive + negative

        direction = 1 if positive >= negative else -1
        consistency = (
            max(positive, negative) / directional
            if directional
            else 0.0
        )
        mean_confidence = sum(confidences) / count
        mean_magnitude = sum(abs(score) for score in scores) / count
        signed_mean = sum(scores) / count

        failures: list[str] = []
        if count < self.min_observations:
            failures.append(
                f"needs at least {self.min_observations} observations"
            )
        if mean_confidence < self.min_mean_confidence:
            failures.append(
                f"mean confidence is below {self.min_mean_confidence:.2f}"
            )
        if consistency < self.min_consistency:
            failures.append(
                f"directional consistency is below {self.min_consistency:.2f}"
            )
        if mean_magnitude < self.min_mean_magnitude:
            failures.append(
                f"mean preference strength is below {self.min_mean_magnitude:.2f}"
            )

        eligible = not failures
        reason = (
            "Candidate satisfies deterministic promotion thresholds."
            if eligible
            else "Candidate is not yet eligible: " + "; ".join(failures) + "."
        )

        return self._evaluation(
            normalized_name,
            eligible=eligible,
            reason=reason,
            observation_count=count,
            mean_confidence=mean_confidence,
            consistency=consistency,
            mean_magnitude=mean_magnitude,
            direction=direction,
            signed_mean=signed_mean,
            category=str(candidate.get("category", "general")),
        )

    def promotion_spec(self, name: str) -> Optional[Dict[str, Any]]:
        """Return the durable preference payload only when eligibility passes."""

        evaluation = self.evaluate(name)
        if not evaluation["eligible"]:
            return None

        signed_mean = float(evaluation["signed_mean"])
        return {
            "name": evaluation["name"],
            "category": evaluation.get("category", "general"),
            "strength": self._clamp(abs(signed_mean)),
            "polarity": 1.0 if signed_mean >= 0.0 else -1.0,
            "confidence": self._clamp(evaluation["mean_confidence"]),
            "source": "experience_promotion",
        }

    # ============================================================
    # EXPLICIT DECISIONS
    # ============================================================

    def mark_promoted(
        self,
        name: str,
        *,
        preference: Dict[str, Any],
    ) -> bool:
        """Move a promoted candidate into decision history."""

        normalized_name = self._normalize_name(name)
        candidate = self.candidates.pop(normalized_name, None)
        if candidate is None:
            return False

        self.history.append(
            {
                "name": normalized_name,
                "status": "promoted",
                "candidate": deepcopy(candidate),
                "preference": deepcopy(preference),
                "timestamp": datetime.now().isoformat(),
            }
        )
        self.save_if_configured()
        return True

    def reject(self, name: str, *, reason: str = "") -> bool:
        """Explicitly reject a candidate without mutating Mary's Preferences."""

        normalized_name = self._normalize_name(name)
        candidate = self.candidates.pop(normalized_name, None)
        if candidate is None:
            return False

        self.history.append(
            {
                "name": normalized_name,
                "status": "rejected",
                "candidate": deepcopy(candidate),
                "reason": str(reason).strip() or "Preference candidate rejected.",
                "timestamp": datetime.now().isoformat(),
            }
        )
        self.save_if_configured()
        return True

    # ============================================================
    # READ API
    # ============================================================

    def get_candidate(self, name: str) -> Optional[Dict[str, Any]]:
        candidate = self.candidates.get(self._normalize_name(name))
        return deepcopy(candidate) if candidate is not None else None

    def get_candidates(self) -> List[Dict[str, Any]]:
        return [deepcopy(item) for item in self.candidates.values()]

    def get_history(self, limit: int | None = None) -> List[Dict[str, Any]]:
        result = deepcopy(self.history)
        if limit is not None:
            result = result[-max(0, int(limit)):]
        return result

    def summary(self) -> Dict[str, Any]:
        eligible = sum(
            1
            for name in self.candidates
            if self.evaluate(name)["eligible"]
        )
        return {
            "candidates": len(self.candidates),
            "eligible": eligible,
            "history": len(self.history),
            "min_observations": self.min_observations,
            "min_mean_confidence": self.min_mean_confidence,
            "min_consistency": self.min_consistency,
            "min_mean_magnitude": self.min_mean_magnitude,
            "configured": self.configured,
        }

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "policy": {
                "auto_promote": False,
                "model_output_counts_as_evidence": False,
                "explicit_promotion_required": True,
            },
            "thresholds": {
                "min_observations": self.min_observations,
                "min_mean_confidence": self.min_mean_confidence,
                "min_consistency": self.min_consistency,
                "min_mean_magnitude": self.min_mean_magnitude,
            },
            "candidates": deepcopy(self.candidates),
            "history": deepcopy(self.history),
        }

    def load_dict(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            return

        thresholds = data.get("thresholds", {})
        if isinstance(thresholds, dict):
            self.min_observations = max(
                2,
                int(thresholds.get("min_observations", self.min_observations)),
            )
            self.min_mean_confidence = self._clamp(
                thresholds.get("min_mean_confidence", self.min_mean_confidence)
            )
            self.min_consistency = self._clamp(
                thresholds.get("min_consistency", self.min_consistency)
            )
            self.min_mean_magnitude = self._clamp(
                thresholds.get("min_mean_magnitude", self.min_mean_magnitude)
            )

        candidates = data.get("candidates", {})
        history = data.get("history", [])

        self.candidates = (
            deepcopy(candidates)
            if isinstance(candidates, dict)
            else {}
        )
        self.history = (
            deepcopy(history)
            if isinstance(history, list)
            else []
        )

    # ============================================================
    # HELPERS
    # ============================================================

    def _evaluation(
        self,
        name: str,
        *,
        eligible: bool,
        reason: str,
        observation_count: int = 0,
        mean_confidence: float = 0.0,
        consistency: float = 0.0,
        mean_magnitude: float = 0.0,
        direction: int = 0,
        signed_mean: float = 0.0,
        category: str = "general",
    ) -> Dict[str, Any]:
        return {
            "name": name,
            "category": category,
            "eligible": bool(eligible),
            "reason": reason,
            "observation_count": int(observation_count),
            "mean_confidence": float(mean_confidence),
            "consistency": float(consistency),
            "mean_magnitude": float(mean_magnitude),
            "direction": int(direction),
            "signed_mean": float(signed_mean),
        }

    @staticmethod
    def _normalize_name(value: Any) -> str:
        return str(value).strip().lower()

    @staticmethod
    def _normalize_source(value: Any) -> str:
        return str(value).strip().lower() or "experience"

    @classmethod
    def _signed_score(cls, *, strength: Any, polarity: Any) -> float:
        magnitude = cls._clamp(strength)
        try:
            polarity_value = float(polarity)
        except (TypeError, ValueError):
            polarity_value = 0.0

        if polarity_value > 0.0:
            return magnitude
        if polarity_value < 0.0:
            return -magnitude
        return 0.0

    @staticmethod
    def _clamp(value: Any) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 0.0
        return max(0.0, min(1.0, numeric))
