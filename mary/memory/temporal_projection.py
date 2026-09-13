"""Derived temporal projection over Mary's canonical memory/relationship facts.

This module never becomes a truth owner. It provides Graphiti-inspired validity,
supersession, contradiction and provenance semantics over records supplied by
Mary's existing authorities. The projection is rebuildable and disposable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


@dataclass
class TemporalFact:
    fact_id: str
    subject: str
    predicate: str
    value: Any
    source: str
    confidence: float = 1.0
    valid_from: str = field(default_factory=_now)
    valid_until: str | None = None
    observed_at: str = field(default_factory=_now)
    evidence_id: str | None = None
    supersedes: str | None = None
    contradicted_by: list[str] = field(default_factory=list)
    status: str = "current"

    def key(self) -> tuple[str, str]:
        return (_norm(self.subject), _norm(self.predicate))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TemporalKnowledgeProjection:
    """Small rebuildable temporal index for canonical facts."""

    VERSION = "13.19"

    def __init__(self) -> None:
        self._facts: list[TemporalFact] = []

    @staticmethod
    def _clamp(value: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.5
        return max(0.0, min(1.0, number))

    def add(
        self,
        *,
        subject: str,
        predicate: str,
        value: Any,
        source: str,
        confidence: float = 1.0,
        valid_from: str | None = None,
        evidence_id: str | None = None,
    ) -> TemporalFact:
        subject = str(subject).strip()
        predicate = str(predicate).strip()
        source = str(source).strip()
        if not subject or not predicate or not source:
            raise ValueError("subject, predicate, and source are required")

        key = (_norm(subject), _norm(predicate))
        same_key = [fact for fact in self._facts if fact.key() == key and fact.status == "current"]
        normalized_value = _norm(value)
        for fact in same_key:
            if _norm(fact.value) == normalized_value:
                fact.confidence = max(fact.confidence, self._clamp(confidence))
                if evidence_id:
                    fact.evidence_id = str(evidence_id)
                return fact

        now = str(valid_from or _now())
        supersedes: str | None = None
        for fact in same_key:
            fact.status = "historical"
            fact.valid_until = now
            supersedes = fact.fact_id

        created = TemporalFact(
            fact_id=f"temporal_{len(self._facts) + 1}",
            subject=subject,
            predicate=predicate,
            value=value,
            source=source,
            confidence=self._clamp(confidence),
            valid_from=now,
            evidence_id=(None if evidence_id is None else str(evidence_id)),
            supersedes=supersedes,
        )
        if same_key:
            for previous in same_key:
                previous.contradicted_by.append(created.fact_id)
        self._facts.append(created)
        return created

    @staticmethod
    def _canonical_shape(record: dict[str, Any]) -> dict[str, Any]:
        """Normalize semantic-memory or Relationship UserModel record shapes."""
        subject = str(record.get("subject") or "").strip()
        predicate = str(record.get("predicate") or "").strip()

        # Relationship UserModel profile records use category/key/value rather
        # than subject/predicate/value. Preserve that namespace so preference,
        # communication and fact keys cannot collide with each other.
        if not subject and record.get("category") is not None:
            subject = "creator"
        if not predicate and record.get("key") is not None:
            category = str(record.get("category") or "general").strip().lower() or "general"
            key = str(record.get("key") or "").strip().lower()
            predicate = f"{category}.{key}" if key else category

        valid_from = record.get("valid_from") or record.get("created_at") or record.get("updated_at")
        evidence_id = record.get("evidence_id") or record.get("observation_id") or record.get("id")
        return {
            "subject": subject,
            "predicate": predicate or str(record.get("key") or ""),
            "value": record.get("value"),
            "source": str(record.get("source") or "canonical"),
            "confidence": record.get("confidence", 1.0),
            "valid_from": (str(valid_from) if valid_from else None),
            "evidence_id": (str(evidence_id) if evidence_id else None),
        }

    def rebuild(self, records: Iterable[dict[str, Any]]) -> None:
        self._facts.clear()
        for record in records:
            if not isinstance(record, dict):
                continue
            normalized = self._canonical_shape(record)
            try:
                self.add(
                    subject=normalized["subject"],
                    predicate=normalized["predicate"],
                    value=normalized["value"],
                    source=normalized["source"],
                    confidence=float(normalized["confidence"]),
                    valid_from=normalized["valid_from"],
                    evidence_id=normalized["evidence_id"],
                )
            except (TypeError, ValueError):
                continue

    def rebuild_user_model(self, user_model: Any) -> None:
        """Rebuild directly from Mary's source-aware canonical creator profile."""
        self.rebuild(list(getattr(user_model, "profile_records", []) or []))

    def current(self, *, subject: str | None = None, predicate: str | None = None) -> list[dict[str, Any]]:
        items = [fact for fact in self._facts if fact.status == "current"]
        if subject is not None:
            items = [fact for fact in items if _norm(fact.subject) == _norm(subject)]
        if predicate is not None:
            items = [fact for fact in items if _norm(fact.predicate) == _norm(predicate)]
        return [fact.to_dict() for fact in items]

    def history(self, *, subject: str, predicate: str) -> list[dict[str, Any]]:
        key = (_norm(subject), _norm(predicate))
        return [fact.to_dict() for fact in self._facts if fact.key() == key]

    def snapshot(self) -> dict[str, Any]:
        current = sum(1 for fact in self._facts if fact.status == "current")
        return {
            "version": self.VERSION,
            "authority": "derived_rebuildable_projection",
            "fact_count": len(self._facts),
            "current_count": current,
            "historical_count": len(self._facts) - current,
            "facts": [fact.to_dict() for fact in self._facts],
        }
