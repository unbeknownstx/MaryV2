"""Per-turn confirmation against Mary's canonical state owners.

The cognitive reservoir is only a rebuildable selector/index.  Before a local
response may use an authority-bearing hit, this module confirms that the exact
derived record still corresponds to the current canonical owner and returns a
small immutable scalar projection.  It stores nothing and calls no model.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import math
from numbers import Real
from typing import Any

from .dialogue_acts import DialogueAct, DialoguePlan
from .verbalization_plan import bounded_response_scalar


@dataclass(frozen=True, slots=True)
class ConfirmedAuthorityScalar:
    """One exact, bounded value copied from a canonical owner for this turn."""

    selector_id: str
    owner: str
    subject: str
    predicate: str
    value: str
    kind: str
    source: str
    authority: str
    confidence: float
    polarity: float | None = None

    def __post_init__(self) -> None:
        for field_name, limit in (
            ("selector_id", 160),
            ("owner", 64),
            ("subject", 120),
            ("predicate", 120),
            ("value", 180),
            ("kind", 80),
            ("source", 120),
            ("authority", 96),
        ):
            object.__setattr__(
                self,
                field_name,
                bounded_response_scalar(
                    f"confirmed {field_name}",
                    getattr(self, field_name),
                    limit=limit,
                ),
            )
        confidence = _unit_float(self.confidence)
        object.__setattr__(self, "confidence", confidence)
        if self.polarity is not None:
            polarity = _finite_real(self.polarity)
            if not -1.0 <= polarity <= 1.0:
                raise ValueError("confirmed polarity must be between -1 and 1")
            object.__setattr__(self, "polarity", polarity)


@dataclass(frozen=True, slots=True)
class AuthorityConfirmationBundle:
    """Bounded nonpersistent confirmations for selected reservoir records."""

    items: tuple[ConfirmedAuthorityScalar, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.items, Mapping) or isinstance(
            self.items,
            (str, bytes, bytearray),
        ) or not isinstance(self.items, Sequence):
            raise TypeError("confirmation items must be a sequence")
        items = tuple(self.items)
        if len(items) > 3:
            raise ValueError("at most three authority confirmations are allowed")
        if any(not isinstance(item, ConfirmedAuthorityScalar) for item in items):
            raise TypeError("confirmation items must be ConfirmedAuthorityScalar values")
        if len({item.selector_id for item in items}) != len(items):
            raise ValueError("confirmation selector IDs must be unique")
        object.__setattr__(self, "items", items)

    def for_selector(self, selector_id: Any) -> ConfirmedAuthorityScalar | None:
        if not isinstance(selector_id, str):
            return None
        return next(
            (item for item in self.items if item.selector_id == selector_id),
            None,
        )


def confirm_dialogue_plan_authority(
    mary: Any,
    dialogue_plan: DialoguePlan,
) -> AuthorityConfirmationBundle:
    """Confirm selected hits against current owners, failing closed to empty."""

    if not isinstance(dialogue_plan, DialoguePlan):
        raise TypeError("dialogue_plan must be a DialoguePlan")
    try:
        if dialogue_plan.act == DialogueAct.KNOWN_FACT:
            hit = _mapping(dialogue_plan.slots.get("hit"))
            item = _confirm_creator_fact(mary, hit)
            return AuthorityConfirmationBundle((item,) if item else ())
        if dialogue_plan.act == DialogueAct.KNOWN_PREFERENCE:
            hit = _mapping(dialogue_plan.slots.get("hit"))
            item = _confirm_mary_preference(mary, hit)
            return AuthorityConfirmationBundle((item,) if item else ())
        if dialogue_plan.act == DialogueAct.ANSWER:
            raw_hits = dialogue_plan.slots.get("hits")
            if isinstance(raw_hits, Mapping) or isinstance(
                raw_hits,
                (str, bytes, bytearray),
            ) or not isinstance(raw_hits, Sequence):
                return AuthorityConfirmationBundle()
            confirmed: list[ConfirmedAuthorityScalar] = []
            for raw_hit in tuple(raw_hits):
                item = _confirm_semantic_memory(mary, _mapping(raw_hit))
                if item is None:
                    return AuthorityConfirmationBundle()
                confirmed.append(item)
            return AuthorityConfirmationBundle(tuple(confirmed))
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return AuthorityConfirmationBundle()
    return AuthorityConfirmationBundle()


def _confirm_creator_fact(
    mary: Any,
    hit: Mapping[str, Any],
) -> ConfirmedAuthorityScalar | None:
    metadata = _mapping(hit.get("metadata"))
    key = metadata.get("key")
    if not isinstance(key, str):
        return None
    records = mary.user_model.get_profile_records(current_only=True)
    for record in records:
        if not isinstance(record, Mapping) or _key(record.get("key")) != _key(key):
            continue
        category = _plain(record.get("category") or "general", limit=40)
        canonical_key = _key(key).replace(" ", "_")
        value = _owner_scalar(record.get("value"), limit=180)
        source = _plain(record.get("source") or "relationship", limit=120)
        confidence = _unit_float(record.get("confidence", 1.0))
        explicitly_shared = bool(record.get("explicitly_shared"))
        authority = "creator_explicit" if explicitly_shared else "creator_structured"
        record_id = f"creator:{record.get('id') or _rid(category, key, value)}"
        expected = {
            "record_id": record_id,
            "kind": f"creator_{category}",
            "subject": "creator",
            "predicate": canonical_key,
            "content": _creator_content(category, canonical_key, value),
            "source": source,
            "authority": authority,
            "confidence": round(confidence, 3),
            "metadata": {
                "category": category,
                "key": canonical_key,
                "value": record.get("value"),
                "explicitly_shared": explicitly_shared,
            },
        }
        if _exact_hit(hit, expected):
            return ConfirmedAuthorityScalar(
                selector_id=record_id,
                owner="creator_user_model",
                subject="creator",
                predicate=canonical_key,
                value=value,
                kind=f"creator_{category}",
                source=source,
                authority=authority,
                confidence=confidence,
            )
    return None


def _confirm_mary_preference(
    mary: Any,
    hit: Mapping[str, Any],
) -> ConfirmedAuthorityScalar | None:
    metadata = _mapping(hit.get("metadata"))
    name = metadata.get("name")
    if not isinstance(name, str):
        return None
    preference = mary.preferences.get_preference(name)
    if not isinstance(preference, Mapping):
        return None
    canonical_name = _plain(preference.get("name") or name, limit=140)
    polarity = _signed_unit_float(preference.get("polarity", 0.0))
    confidence = _unit_float(preference.get("confidence", 0.8))
    source = _plain(preference.get("source") or "preferences", limit=120)
    record_id = f"mary-preference:{_rid(canonical_name)}"
    stance = (
        "likes"
        if polarity > 0.05
        else "dislikes"
        if polarity < -0.05
        else "is undecided about"
    )
    expected = {
        "record_id": record_id,
        "kind": "mary_preference",
        "subject": "mary",
        "predicate": _key(canonical_name).replace(" ", "_"),
        "content": f"Mary {stance} {canonical_name.replace('_', ' ')}.",
        "source": source,
        "authority": "mary_developed",
        "confidence": round(confidence, 3),
        "metadata": {
            "name": canonical_name,
            "polarity": polarity,
            "value": preference.get("value", preference.get("strength", preference.get("score"))),
        },
    }
    if not _exact_hit(hit, expected):
        return None
    return ConfirmedAuthorityScalar(
        selector_id=record_id,
        owner="mary_preferences",
        subject="mary",
        predicate=_key(canonical_name).replace(" ", "_"),
        value=canonical_name.replace("_", " "),
        kind="mary_preference",
        source=source,
        authority="mary_developed",
        confidence=confidence,
        polarity=polarity,
    )


def _confirm_semantic_memory(
    mary: Any,
    hit: Mapping[str, Any],
) -> ConfirmedAuthorityScalar | None:
    memories = mary.memory.semantic.all()
    for memory in memories:
        if not isinstance(memory, Mapping):
            continue
        subject = _plain(memory.get("subject"), limit=100)
        predicate = _plain(memory.get("predicate"), limit=100)
        value = _owner_scalar(memory.get("value"), limit=180)
        source = _plain(memory.get("source") or "semantic_memory", limit=120)
        confidence = _unit_float(memory.get("confidence", 1.0))
        record_id = f"semantic:{memory.get('id') or _rid(subject, predicate, value)}"
        expected = {
            "record_id": record_id,
            "kind": "semantic_memory",
            "subject": subject.lower(),
            "predicate": predicate.lower().replace(" ", "_"),
            "content": f"{subject} {predicate.replace('_', ' ')} {value}.",
            "source": source,
            "authority": "semantic_memory",
            "confidence": round(confidence, 3),
            "metadata": {
                "subject": subject,
                "predicate": predicate,
                "value": memory.get("value"),
            },
        }
        if not _exact_hit(hit, expected):
            continue
        return ConfirmedAuthorityScalar(
            selector_id=record_id,
            owner="semantic_memory",
            subject=subject,
            predicate=predicate,
            value=value,
            kind="semantic_memory",
            source=source,
            authority="semantic_memory",
            confidence=confidence,
        )
    return None


def _exact_hit(hit: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    for key in (
        "record_id",
        "kind",
        "subject",
        "predicate",
        "content",
        "source",
        "authority",
    ):
        if hit.get(key) != expected.get(key):
            return False
    try:
        if round(_finite_real(hit.get("confidence")), 3) != expected.get("confidence"):
            return False
    except (TypeError, ValueError):
        return False
    metadata = hit.get("metadata")
    expected_metadata = expected.get("metadata")
    return (
        isinstance(metadata, Mapping)
        and isinstance(expected_metadata, Mapping)
        and dict(metadata) == dict(expected_metadata)
    )


def _creator_content(category: str, key: str, value: str) -> str:
    label = key.replace("_", " ")
    if category == "preference":
        return f"The creator's {label} preference is {value}."
    if category == "goal":
        return f"The creator has a represented goal: {value}."
    if category == "interest":
        return f"The creator is interested in {value}."
    if category == "value":
        return f"The creator values {value}."
    if category == "communication":
        return f"The creator's communication preference {label} is {value}."
    return f"The creator's {label} is {value}."


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _plain(value: Any, *, limit: int) -> str:
    return bounded_response_scalar("canonical owner scalar", value, limit=limit)


def _owner_scalar(value: Any, *, limit: int) -> str:
    if isinstance(value, bool):
        # Match the rebuildable reservoir's canonical ``str(value)`` surface.
        return _plain(str(value), limit=limit)
    if isinstance(value, Real):
        _finite_real(value)
        return _plain(str(value), limit=limit)
    if not isinstance(value, str):
        raise TypeError("canonical owner values must be bounded scalars")
    return _plain(value, limit=limit)


def _key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.casefold().replace("_", " ").split()).strip()


def _rid(*parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha1(
        raw.encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()


def _finite_real(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError("canonical numeric scalar must be real")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("canonical numeric scalar must be finite")
    return number


def _unit_float(value: Any) -> float:
    number = _finite_real(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError("canonical confidence must be between 0 and 1")
    return number


def _signed_unit_float(value: Any) -> float:
    number = _finite_real(value)
    if not -1.0 <= number <= 1.0:
        raise ValueError("canonical polarity must be between -1 and 1")
    return number
