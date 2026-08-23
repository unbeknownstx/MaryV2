"""Build reservoir records from Mary's existing authoritative systems."""
from __future__ import annotations

import hashlib
from typing import Any, Iterable

from .reservoir import ReservoirRecord
from mary.relationship.provenance import text_has_test_probe_marker


def _rid(*parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8"), usedforsecurity=False).hexdigest()


def authoritative_records(mary: Any) -> list[ReservoirRecord]:
    records: list[ReservoirRecord] = []
    records.extend(_creator_records(mary))
    records.extend(_mary_preference_records(mary))
    records.extend(_semantic_memory_records(mary))
    records.extend(_episodic_memory_records(mary))
    records.extend(_knowledge_records(mary))
    return records


def _creator_records(mary: Any) -> Iterable[ReservoirRecord]:
    try:
        profile = list(mary.user_model.get_profile_records(current_only=True))
    except Exception:
        return []
    output: list[ReservoirRecord] = []
    for item in profile:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "general").strip().lower()
        key = str(item.get("key") or category).strip().lower().replace(" ", "_")
        value = item.get("value")
        if value is None or not str(value).strip():
            continue
        if text_has_test_probe_marker(str(value)):
            continue
        explicit = bool(item.get("explicitly_shared"))
        confidence = float(item.get("confidence", 1.0) or 1.0)
        source = str(item.get("source") or "relationship")
        if category == "preference":
            content = f"The creator's {key.replace('_', ' ')} preference is {value}."
        elif category == "goal":
            content = f"The creator has a represented goal: {value}."
        elif category == "interest":
            content = f"The creator is interested in {value}."
        elif category == "value":
            content = f"The creator values {value}."
        elif category == "communication":
            content = f"The creator's communication preference {key.replace('_', ' ')} is {value}."
        else:
            content = f"The creator's {key.replace('_', ' ')} is {value}."
        output.append(
            ReservoirRecord(
                record_id=f"creator:{item.get('id') or _rid(category,key,value)}",
                kind=f"creator_{category}",
                subject="creator",
                predicate=key,
                content=content,
                source=source,
                authority="creator_explicit" if explicit else "creator_structured",
                confidence=max(0.0, min(1.0, confidence)),
                tags=("creator", category, key),
                metadata={
                    "category": category,
                    "key": key,
                    "value": value,
                    "explicitly_shared": explicit,
                },
            )
        )
    return output


def _mary_preference_records(mary: Any) -> Iterable[ReservoirRecord]:
    try:
        preferences = dict(mary.preferences.to_dict())
    except Exception:
        return []
    output: list[ReservoirRecord] = []
    for name, item in preferences.items():
        if not isinstance(item, dict):
            continue
        value = item.get("value", item.get("strength", item.get("score")))
        polarity = item.get("polarity")
        if polarity is None:
            try:
                polarity = float(value)
            except (TypeError, ValueError):
                polarity = 0.0
        try:
            polarity_value = float(polarity)
        except (TypeError, ValueError):
            polarity_value = 0.0
        stance = "likes" if polarity_value > 0.05 else "dislikes" if polarity_value < -0.05 else "is undecided about"
        confidence = float(item.get("confidence", 0.8) or 0.8)
        output.append(
            ReservoirRecord(
                record_id=f"mary-preference:{_rid(name)}",
                kind="mary_preference",
                subject="mary",
                predicate=str(name).strip().lower().replace(" ", "_"),
                content=f"Mary {stance} {str(name).replace('_', ' ')}.",
                source=str(item.get("source") or "preferences"),
                authority="mary_developed",
                confidence=max(0.0, min(1.0, confidence)),
                tags=("mary", "preference", str(name)),
                metadata={"name": name, "polarity": polarity_value, "value": value},
            )
        )
    return output



def _semantic_memory_records(mary: Any) -> Iterable[ReservoirRecord]:
    """Project durable semantic memory into the rebuildable reservoir."""
    try:
        memories = list(mary.memory.semantic.all())
    except Exception:
        return []
    output: list[ReservoirRecord] = []
    for item in memories[:20_000]:
        if not isinstance(item, dict):
            continue
        subject = str(item.get("subject") or "").strip()
        predicate = str(item.get("predicate") or "").strip()
        value = item.get("value")
        if not subject or not predicate or value is None or not str(value).strip():
            continue
        rendered = str(value).strip()
        if text_has_test_probe_marker(rendered):
            continue
        confidence = float(item.get("confidence", 1.0) or 1.0)
        output.append(
            ReservoirRecord(
                record_id=f"semantic:{item.get('id') or _rid(subject,predicate,rendered)}",
                kind="semantic_memory",
                subject=subject.lower(),
                predicate=predicate.lower().replace(" ", "_"),
                content=f"{subject} {predicate.replace('_', ' ')} {rendered}.",
                source=str(item.get("source") or "semantic_memory"),
                authority="semantic_memory",
                confidence=max(0.0, min(1.0, confidence)),
                tags=("semantic", subject, predicate),
                metadata={"subject": subject, "predicate": predicate, "value": value},
            )
        )
    return output


def _episodic_memory_records(mary: Any) -> Iterable[ReservoirRecord]:
    """Index meaningful episodic history without promoting it to semantic truth."""
    try:
        memories = list(mary.memory.episodic.all())
    except Exception:
        return []
    output: list[ReservoirRecord] = []
    # Episodic history can grow. Only the bounded, more important tail belongs
    # in the hot searchable reservoir; the authoritative episodic store remains
    # intact and can still be queried by the normal memory subsystem.
    selected = sorted(
        memories,
        key=lambda item: (float(getattr(item, "importance", 0.0) or 0.0), getattr(item, "timestamp", "")),
        reverse=True,
    )[:5_000]
    for memory in selected:
        content = " ".join(str(getattr(memory, "content", "") or "").split()).strip()
        if not content or text_has_test_probe_marker(content):
            continue
        importance = float(getattr(memory, "importance", 0.5) or 0.5)
        if importance < 0.45:
            continue
        event_type = str(getattr(memory, "event_type", "general") or "general")
        source = str(getattr(memory, "source", "episodic_memory") or "episodic_memory")
        output.append(
            ReservoirRecord(
                record_id=f"episode:{getattr(memory, 'id', None) or _rid(content)}",
                kind="episodic_memory",
                subject="shared_history",
                predicate=event_type.lower().replace(" ", "_"),
                content=content,
                source=source,
                authority="episodic_history",
                confidence=max(0.45, min(0.95, 0.55 + importance * 0.4)),
                tags=("episode", "shared_history", event_type),
                metadata={
                    "importance": importance,
                    "event_type": event_type,
                    "timestamp": str(getattr(memory, "timestamp", "")),
                },
            )
        )
    return output

def _knowledge_records(mary: Any) -> Iterable[ReservoirRecord]:
    try:
        concepts = list(mary.knowledge.get_all_concepts())
    except Exception:
        return []
    output: list[ReservoirRecord] = []
    for concept in concepts[:20_000]:
        data = concept.to_dict() if hasattr(concept, "to_dict") else dict(concept)
        status = str(data.get("status") or "candidate").lower()
        if status not in {"verified", "established", "accepted"}:
            continue
        name = str(data.get("name") or data.get("concept") or data.get("id") or "").strip()
        definition = str(data.get("definition") or data.get("description") or data.get("content") or "").strip()
        if not name or not definition:
            continue
        confidence = float(data.get("confidence", 0.8) or 0.8)
        output.append(
            ReservoirRecord(
                record_id=f"knowledge:{data.get('id') or _rid(name)}",
                kind="knowledge_concept",
                subject="world",
                predicate=name.lower().replace(" ", "_"),
                content=f"{name}: {definition}",
                source=str(data.get("source") or "knowledge_manager"),
                authority="knowledge_verified",
                confidence=max(0.0, min(1.0, confidence)),
                tags=("knowledge", name),
                metadata={"name": name, "status": status},
            )
        )
    return output
