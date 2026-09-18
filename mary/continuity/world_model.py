"""Persistent evidence-aware world/belief model for MaryV2.

This module is deliberately *not* canonical MemoryManager, identity, relationship
or internet truth.  It is Mary's structured map of entities and propositions:
what she has observed, what she currently believes, what is only a hypothesis,
where the evidence came from, when it was valid, and whether newer evidence
contradicts or supersedes it.

Canonical owners remain authoritative.  The world model is an inspectable
coordination/evidence layer above raw retrieval and below Mary Core decisions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Iterable
from uuid import uuid4

from .storage import AtomicJsonStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _tuple(values: Iterable[str], *, limit: int = 20, item_limit: int = 160) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            _bounded(value, item_limit)
            for value in list(values)[:limit]
            if _bounded(value, item_limit)
        )
    )


@dataclass(frozen=True)
class WorldEntity:
    id: str
    entity_type: str
    label: str
    aliases: tuple[str, ...]
    source: str
    authority: str
    confidence: float
    created_at: str
    updated_at: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["aliases"] = list(self.aliases)
        payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True)
class BeliefClaim:
    id: str
    subject: str
    predicate: str
    value: Any
    belief_type: str
    status: str
    confidence: float
    source: str
    authority: str
    evidence_ids: tuple[str, ...]
    observed_at: str
    valid_from: str
    valid_to: str | None
    verification: str
    supersedes: str | None = None
    contradiction_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] | None = None

    @property
    def current(self) -> bool:
        return self.valid_to is None and self.status in {"current", "contested"}

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_ids"] = list(self.evidence_ids)
        payload["contradiction_ids"] = list(self.contradiction_ids)
        payload["metadata"] = dict(self.metadata or {})
        payload["current"] = self.current
        return payload


class WorldModel:
    """Small durable entity/belief graph with explicit epistemic boundaries."""

    VERSION = 1
    BELIEF_TYPES = {"fact", "observation", "inference", "hypothesis", "unknown"}
    STATUSES = {"current", "contested", "retired"}
    VERIFICATIONS = {"verified", "unverified", "contradicted", "uncertain"}
    AUTHORITIES = {
        "canonical",
        "creator",
        "verified_external",
        "external",
        "runtime",
        "inference",
        "candidate",
    }

    def __init__(self, path: Path, *, entity_capacity: int = 2000, belief_capacity: int = 8000) -> None:
        self.entity_capacity = max(64, int(entity_capacity))
        self.belief_capacity = max(128, int(belief_capacity))
        self._store = AtomicJsonStore(
            path,
            default={
                "version": self.VERSION,
                "entities": [],
                "beliefs": [],
            },
        )

    def upsert_entity(
        self,
        *,
        label: str,
        entity_type: str,
        source: str,
        authority: str = "candidate",
        confidence: float = 0.7,
        aliases: Iterable[str] = (),
        metadata: dict[str, Any] | None = None,
    ) -> WorldEntity:
        clean_label = _bounded(label, 240)
        clean_type = _bounded(entity_type, 80).casefold() or "entity"
        clean_source = _bounded(source, 240) or "unknown"
        clean_authority = _bounded(authority, 80).casefold() or "candidate"
        if not clean_label:
            raise ValueError("world entity label is required")
        if clean_authority not in self.AUTHORITIES:
            clean_authority = "candidate"
        now = _now()
        aliases_tuple = _tuple(aliases)
        safe_metadata = self._safe_metadata(metadata)
        entity_id = ""

        def mutate(data: dict[str, Any]) -> None:
            nonlocal entity_id
            rows = list(data.get("entities") or [])
            match = next(
                (
                    row for row in rows
                    if str(row.get("label") or "").casefold() == clean_label.casefold()
                    and str(row.get("entity_type") or "").casefold() == clean_type
                ),
                None,
            )
            if match is None:
                entity_id = f"entity_{uuid4().hex}"
                rows.append({
                    "id": entity_id,
                    "entity_type": clean_type,
                    "label": clean_label,
                    "aliases": list(aliases_tuple),
                    "source": clean_source,
                    "authority": clean_authority,
                    "confidence": max(0.0, min(1.0, float(confidence))),
                    "created_at": now,
                    "updated_at": now,
                    "metadata": safe_metadata,
                })
            else:
                entity_id = str(match.get("id") or "")
                merged_aliases = _tuple([*(match.get("aliases") or []), *aliases_tuple])
                match.update({
                    "aliases": list(merged_aliases),
                    "source": clean_source,
                    "authority": clean_authority,
                    "confidence": max(
                        float(match.get("confidence", 0.0) or 0.0),
                        max(0.0, min(1.0, float(confidence))),
                    ),
                    "updated_at": now,
                    "metadata": {**dict(match.get("metadata") or {}), **safe_metadata},
                })
            data["entities"] = rows[-self.entity_capacity :]
            data["version"] = self.VERSION

        self._store.mutate(mutate)
        return self.get_entity(entity_id)

    def observe(
        self,
        *,
        subject: str,
        predicate: str,
        value: Any,
        source: str,
        belief_type: str = "observation",
        confidence: float = 0.7,
        authority: str = "candidate",
        evidence_ids: Iterable[str] = (),
        verification: str = "unverified",
        observed_at: str | None = None,
        valid_from: str | None = None,
        supersede_current: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> BeliefClaim:
        subject = self.canonical_label(subject)
        predicate = _bounded(predicate, 160).casefold()
        source = _bounded(source, 240) or "unknown"
        belief_type = _bounded(belief_type, 40).casefold()
        authority = _bounded(authority, 80).casefold()
        verification = _bounded(verification, 40).casefold()
        if not subject or not predicate:
            raise ValueError("world belief subject and predicate are required")
        if belief_type not in self.BELIEF_TYPES:
            raise ValueError(f"belief_type must be one of {sorted(self.BELIEF_TYPES)}")
        if authority not in self.AUTHORITIES:
            authority = "candidate"
        if verification not in self.VERIFICATIONS:
            verification = "unverified"
        when = observed_at or _now()
        started = valid_from or when
        belief_id = f"belief_{uuid4().hex}"
        evidence = _tuple(evidence_ids, limit=32, item_limit=180)
        safe_metadata = self._safe_metadata(metadata)
        superseded: str | None = None
        contradiction_ids: list[str] = []

        def mutate(data: dict[str, Any]) -> None:
            nonlocal superseded
            rows = list(data.get("beliefs") or [])
            for row in rows:
                if (
                    str(row.get("subject") or "").casefold() != subject.casefold()
                    or str(row.get("predicate") or "").casefold() != predicate
                    or row.get("valid_to") is not None
                    or str(row.get("status") or "") == "retired"
                ):
                    continue
                same_value = self._value_key(row.get("value")) == self._value_key(value)
                if supersede_current:
                    row["valid_to"] = started
                    row["status"] = "retired"
                    superseded = str(row.get("id") or "") or superseded
                    continue
                if same_value:
                    continue
                contradiction_ids.append(str(row.get("id") or ""))
                row["status"] = "contested"
                row["verification"] = (
                    "contradicted"
                    if str(row.get("verification") or "") != "verified"
                    else "uncertain"
                )
                existing = list(row.get("contradiction_ids") or [])
                if belief_id not in existing:
                    existing.append(belief_id)
                row["contradiction_ids"] = existing[-16:]

            rows.append({
                "id": belief_id,
                "subject": subject,
                "predicate": predicate,
                "value": value,
                "belief_type": belief_type,
                "status": "contested" if contradiction_ids and not supersede_current else "current",
                "confidence": max(0.0, min(1.0, float(confidence))),
                "source": source,
                "authority": authority,
                "evidence_ids": list(evidence),
                "observed_at": when,
                "valid_from": started,
                "valid_to": None,
                "verification": verification,
                "supersedes": superseded,
                "contradiction_ids": [item for item in contradiction_ids if item][-16:],
                "metadata": safe_metadata,
            })
            data["beliefs"] = rows[-self.belief_capacity :]
            data["version"] = self.VERSION

        self._store.mutate(mutate)
        return self.get_belief(belief_id)

    def verify(
        self,
        belief_id: str,
        *,
        evidence_ids: Iterable[str] = (),
        confidence: float | None = None,
        source: str | None = None,
    ) -> BeliefClaim:
        found = False
        evidence = _tuple(evidence_ids, limit=32, item_limit=180)

        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            for row in list(data.get("beliefs") or []):
                if row.get("id") != belief_id:
                    continue
                row["verification"] = "verified"
                row["status"] = "current"
                row["evidence_ids"] = list(
                    _tuple([*(row.get("evidence_ids") or []), *evidence], limit=32, item_limit=180)
                )
                if confidence is not None:
                    row["confidence"] = max(0.0, min(1.0, float(confidence)))
                if source is not None:
                    row["source"] = _bounded(source, 240) or str(row.get("source") or "unknown")
                found = True
                break

        self._store.mutate(mutate)
        if not found:
            raise KeyError(belief_id)
        return self.get_belief(belief_id)

    def retire(self, belief_id: str, *, valid_to: str | None = None) -> BeliefClaim:
        found = False

        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            for row in list(data.get("beliefs") or []):
                if row.get("id") == belief_id:
                    row["valid_to"] = valid_to or _now()
                    row["status"] = "retired"
                    found = True
                    break

        self._store.mutate(mutate)
        if not found:
            raise KeyError(belief_id)
        return self.get_belief(belief_id)

    def reconcile(
        self,
        belief_id: str,
        *,
        resolved_by: str = "creator",
        source: str | None = None,
    ) -> BeliefClaim:
        """Explicitly select one current belief while preserving competing history.

        Reconciliation is a creator/governed operation. Competing current
        beliefs with the same subject/predicate are retired, never deleted.
        """

        winner = self.get_belief(belief_id)
        when = _now()
        resolver = _bounded(resolved_by, 160) or "creator"
        source_override = _bounded(source, 240) if source is not None else ""
        found = False

        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            rows = list(data.get("beliefs") or [])
            target = next((row for row in rows if row.get("id") == belief_id), None)
            if target is None:
                return
            subject = str(target.get("subject") or "").casefold()
            predicate = str(target.get("predicate") or "").casefold()
            retired_ids: list[str] = []
            for row in rows:
                if row is target:
                    continue
                if (
                    str(row.get("subject") or "").casefold() != subject
                    or str(row.get("predicate") or "").casefold() != predicate
                    or row.get("valid_to") is not None
                    or str(row.get("status") or "") == "retired"
                ):
                    continue
                row["valid_to"] = when
                row["status"] = "retired"
                row["verification"] = "contradicted"
                ids = list(row.get("contradiction_ids") or [])
                if belief_id not in ids:
                    ids.append(belief_id)
                row["contradiction_ids"] = ids[-16:]
                retired_ids.append(str(row.get("id") or ""))
            target["status"] = "current"
            target["verification"] = "verified"
            if source_override:
                target["source"] = source_override
            metadata = dict(target.get("metadata") or {})
            metadata.update({
                "reconciled_at": when,
                "reconciled_by": resolver,
                "retired_competitors": len(retired_ids),
            })
            target["metadata"] = self._safe_metadata(metadata)
            target["contradiction_ids"] = list(_tuple(
                [*(target.get("contradiction_ids") or []), *retired_ids],
                limit=16,
                item_limit=180,
            ))
            found = True

        self._store.mutate(mutate)
        if not found:
            raise KeyError(belief_id)
        return self.get_belief(belief_id)

    def resolve_entity(self, label_or_alias: str) -> WorldEntity | None:
        """Resolve an exact label/alias without fuzzy identity invention."""

        key = _bounded(label_or_alias, 240).casefold()
        if not key:
            return None
        candidates: list[WorldEntity] = []
        for row in list(self._store.snapshot().get("entities") or []):
            entity = self._decode_entity(row)
            names = {entity.label.casefold()}
            names.update(alias.casefold() for alias in entity.aliases)
            if key in names:
                candidates.append(entity)
        if not candidates:
            return None
        candidates.sort(
            key=lambda item: (item.confidence, item.updated_at),
            reverse=True,
        )
        best = candidates[0]
        if len(candidates) > 1:
            second = candidates[1]
            if (
                second.confidence == best.confidence
                and second.updated_at == best.updated_at
                and second.id != best.id
            ):
                return None
        return best

    def canonical_label(self, label_or_alias: str) -> str:
        entity = self.resolve_entity(label_or_alias)
        return entity.label if entity is not None else _bounded(label_or_alias, 240)

    def get_entity(self, entity_id: str) -> WorldEntity:
        for row in list(self._store.snapshot().get("entities") or []):
            if row.get("id") == entity_id:
                return self._decode_entity(row)
        raise KeyError(entity_id)

    def get_belief(self, belief_id: str) -> BeliefClaim:
        for row in list(self._store.snapshot().get("beliefs") or []):
            if row.get("id") == belief_id:
                return self._decode_belief(row)
        raise KeyError(belief_id)

    def current_beliefs(
        self,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        verified_only: bool = False,
    ) -> list[BeliefClaim]:
        if subject is not None:
            subject = self.canonical_label(subject).casefold()
        if predicate is not None:
            predicate = _bounded(predicate, 160).casefold()
        output: list[BeliefClaim] = []
        for row in list(self._store.snapshot().get("beliefs") or []):
            if row.get("valid_to") is not None or row.get("status") == "retired":
                continue
            if subject is not None and str(row.get("subject") or "").casefold() != subject:
                continue
            if predicate is not None and str(row.get("predicate") or "").casefold() != predicate:
                continue
            if verified_only and str(row.get("verification") or "") != "verified":
                continue
            output.append(self._decode_belief(row))
        return output

    def relevant(self, query: str, *, limit: int = 12) -> list[BeliefClaim]:
        terms = {
            token.casefold()
            for token in re.findall(r"[\w'-]{3,}", str(query or ""))
        }
        if not terms:
            return []
        scored: list[tuple[float, str, BeliefClaim]] = []
        for belief in self.current_beliefs():
            haystack = (
                f"{belief.subject} {belief.predicate} {belief.value} "
                f"{belief.belief_type} {belief.source}"
            ).casefold()
            lexical = sum(1.0 for term in terms if term in haystack)
            if lexical <= 0:
                continue
            verified_bonus = 0.35 if belief.verification == "verified" else 0.0
            authority_bonus = 0.25 if belief.authority in {"canonical", "creator"} else 0.0
            contested_penalty = 0.35 if belief.status == "contested" else 0.0
            score = lexical + belief.confidence * 0.3 + verified_bonus + authority_bonus - contested_penalty
            scored.append((score, belief.observed_at, belief))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored[: max(1, min(50, int(limit)))]]

    def neighborhood(self, entity: str, *, limit: int = 30) -> list[BeliefClaim]:
        clean = self.canonical_label(entity).casefold()
        matches = [
            belief
            for belief in self.current_beliefs()
            if belief.subject.casefold() == clean
            or str(belief.value).strip().casefold() == clean
        ]
        matches.sort(
            key=lambda item: (
                item.verification == "verified",
                item.confidence,
                item.observed_at,
            ),
            reverse=True,
        )
        return matches[: max(1, min(100, int(limit)))]

    def contradictions(self, *, limit: int = 100) -> list[BeliefClaim]:
        rows = [
            belief
            for belief in self.current_beliefs()
            if belief.status == "contested" or belief.contradiction_ids
        ]
        rows.sort(key=lambda item: item.observed_at, reverse=True)
        return rows[: max(1, min(500, int(limit)))]

    def epistemic_summary(self) -> dict[str, int]:
        beliefs = self.current_beliefs()
        return {
            "known_verified": sum(1 for item in beliefs if item.verification == "verified"),
            "observed_unverified": sum(
                1 for item in beliefs
                if item.belief_type == "observation" and item.verification != "verified"
            ),
            "inferred": sum(1 for item in beliefs if item.belief_type == "inference"),
            "hypotheses": sum(1 for item in beliefs if item.belief_type == "hypothesis"),
            "unknowns": sum(1 for item in beliefs if item.belief_type == "unknown"),
            "contested": sum(1 for item in beliefs if item.status == "contested"),
        }

    def status(self) -> dict[str, Any]:
        data = self._store.snapshot()
        entities = list(data.get("entities") or [])
        beliefs = list(data.get("beliefs") or [])
        return {
            "version": self.VERSION,
            "entities": len(entities),
            "beliefs": len(beliefs),
            "current_beliefs": sum(
                1 for row in beliefs
                if row.get("valid_to") is None and row.get("status") != "retired"
            ),
            "epistemic": self.epistemic_summary(),
            "authority": "evidence/belief coordination only; canonical owners remain authoritative",
            "policy": (
                "observations and inferences may be stored with provenance; "
                "contradictions remain visible instead of silently overwriting truth"
            ),
        }

    @staticmethod
    def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
        denied = {"token", "authorization", "api_key", "secret", "password", "cookie"}
        output: dict[str, Any] = {}
        for key, value in list(dict(metadata or {}).items())[:24]:
            name = _bounded(key, 80)
            if not name or name.casefold() in denied:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                output[name] = value if not isinstance(value, str) else _bounded(value, 500)
            else:
                output[name] = _bounded(value, 500)
        return output

    @staticmethod
    def _value_key(value: Any) -> str:
        if isinstance(value, str):
            return " ".join(value.split()).casefold()
        return repr(value)

    @staticmethod
    def _decode_entity(row: dict[str, Any]) -> WorldEntity:
        values = dict(row)
        values["aliases"] = tuple(values.get("aliases") or [])
        values["metadata"] = dict(values.get("metadata") or {})
        return WorldEntity(**values)

    @staticmethod
    def _decode_belief(row: dict[str, Any]) -> BeliefClaim:
        values = dict(row)
        values["evidence_ids"] = tuple(values.get("evidence_ids") or [])
        values["contradiction_ids"] = tuple(values.get("contradiction_ids") or [])
        values["metadata"] = dict(values.get("metadata") or {})
        return BeliefClaim(**values)
