"""Safe, explicit continuity reconciliation for an older creator-owned Mary root.

This module never discovers files and never performs network I/O. It accepts a
bounded payload containing only MemoryManager and RelationshipManager durable
state, computes a content-free merge plan, and can merge it into the live
canonical Mary while preserving current-Core values on conflicts.

Recovery policy:
- current canonical Core wins scalar creator-profile conflicts;
- exact/semantic duplicates are skipped;
- older conflicting scalar profile values may be retained as historical
  evidence, never promoted over a newer current Core value;
- rebuildable indexes, working memory, provider/runtime state, node leases,
  credentials and traces are never imported;
- record IDs are preserved when unique and deterministically renamed when an
  ID collision refers to different content.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from mary.memory.episodic import EpisodicMemory
from mary.relationship.history import RelationshipHistory
from mary.relationship.milestones import MilestoneManager
from mary.relationship.understanding import RelationshipUnderstanding
from mary.relationship.user import UserModel


RECOVERY_FORMAT = "maryv2-continuity-recovery-v1"
SCALAR_PROFILE_CATEGORIES = {"fact", "preference", "communication", "general"}
SET_PROFILE_CATEGORIES = {"interest", "value", "goal"}
UNDERSTANDING_COLLECTIONS = ("observations", "inferences", "patterns")


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any, *, prefix: str) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()[:16]}"


def _clean_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [deepcopy(item) for item in value if isinstance(item, dict)]


def normalize_recovery_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Return a bounded structural recovery payload without interpreting prose."""

    raw = dict(payload or {})
    memory = raw.get("memory")
    relationship = raw.get("relationship")
    if memory is not None and not isinstance(memory, dict):
        raise ValueError("recovery memory must be a JSON object")
    if relationship is not None and not isinstance(relationship, dict):
        raise ValueError("recovery relationship must be a JSON object")

    memory = dict(memory or {})
    relationship = dict(relationship or {})

    user_model = relationship.get("user_model")
    if not isinstance(user_model, dict):
        user_model = {}
    history = relationship.get("history")
    if not isinstance(history, dict):
        history = {}
    understanding = relationship.get("understanding")
    if not isinstance(understanding, dict):
        understanding = {}

    normalized = {
        "format": RECOVERY_FORMAT,
        "memory": {
            "episodic": _clean_list(memory.get("episodic")),
            "semantic": _clean_list(memory.get("semantic")),
        },
        "relationship": {
            "user_model": {
                "creator_id": str(user_model.get("creator_id") or "creator")[:160],
                "name": str(user_model.get("name") or "unbe")[:160],
                "facts": dict(user_model.get("facts") or {}) if isinstance(user_model.get("facts"), dict) else {},
                "preferences": dict(user_model.get("preferences") or {}) if isinstance(user_model.get("preferences"), dict) else {},
                "interests": list(user_model.get("interests") or []) if isinstance(user_model.get("interests"), list) else [],
                "values": list(user_model.get("values") or []) if isinstance(user_model.get("values"), list) else [],
                "goals": list(user_model.get("goals") or []) if isinstance(user_model.get("goals"), list) else [],
                "communication_style": dict(user_model.get("communication_style") or {}) if isinstance(user_model.get("communication_style"), dict) else {},
                "profile_records": _clean_list(user_model.get("profile_records")),
            },
            "history": {
                "creator_id": str(history.get("creator_id") or "creator")[:160],
                "events": _clean_list(history.get("events")),
            },
            "understanding": {
                name: _clean_list(understanding.get(name))
                for name in UNDERSTANDING_COLLECTIONS
            },
            "milestones": _clean_list(relationship.get("milestones")),
        },
    }
    return normalized


def source_counts(payload: dict[str, Any]) -> dict[str, int]:
    data = normalize_recovery_payload(payload)
    relationship = data["relationship"]
    understanding = relationship["understanding"]
    profile = relationship["user_model"]
    return {
        "episodic": len(data["memory"]["episodic"]),
        "semantic": len(data["memory"]["semantic"]),
        "relationship_history": len(relationship["history"]["events"]),
        "creator_profile_records": len(profile["profile_records"]),
        "relationship_milestones": len(relationship["milestones"]),
        "relationship_observations": len(understanding["observations"]),
        "relationship_inferences": len(understanding["inferences"]),
        "relationship_patterns": len(understanding["patterns"]),
    }


def current_counts(mary: Any) -> dict[str, int]:
    relationship = mary.relationship
    return {
        "episodic": int(mary.memory.episodic.count()),
        "semantic": int(mary.memory.semantic.count()),
        "relationship_history": int(relationship.history.count()),
        "creator_profile_records": len(relationship.user_model.profile_records),
        "relationship_milestones": int(relationship.milestones.count()),
        "relationship_observations": len(relationship.understanding.observations),
        "relationship_inferences": len(relationship.understanding.inferences),
        "relationship_patterns": len(relationship.understanding.patterns),
    }


def _episode_signature(item: dict[str, Any]) -> str:
    return _canonical({
        "content": str(item.get("content") or "").strip(),
        "timestamp": str(item.get("timestamp") or ""),
        "source": str(item.get("source") or ""),
        "event_type": str(item.get("event_type") or ""),
        "participants": list(item.get("participants") or []),
    })


def _semantic_signature(item: dict[str, Any]) -> str:
    return _canonical({
        "subject": str(item.get("subject") or "").strip().lower(),
        "predicate": str(item.get("predicate") or "").strip().lower(),
        "value": item.get("value"),
    })


def _history_signature(item: dict[str, Any]) -> str:
    return _canonical({
        "type": str(item.get("type") or "").strip().lower(),
        "description": str(item.get("description") or "").strip(),
        "source": str(item.get("source") or "").strip().lower(),
        "created_at": str(item.get("created_at") or ""),
    })


def _profile_signature(item: dict[str, Any]) -> str:
    return _canonical({
        "category": str(item.get("category") or "").strip().lower(),
        "key": str(item.get("key") or "").strip().lower(),
        "value": item.get("value"),
        "status": str(item.get("status") or "current").strip().lower(),
    })


def _milestone_signature(item: dict[str, Any]) -> str:
    return _canonical({
        "title": str(item.get("title") or "").strip(),
        "description": str(item.get("description") or "").strip(),
        "category": str(item.get("category") or "").strip().lower(),
        "created_at": str(item.get("created_at") or ""),
    })


def _generic_signature(item: dict[str, Any]) -> str:
    clean = {
        key: value
        for key, value in item.items()
        if key not in {"id", "updated_at"}
    }
    return _canonical(clean)


def _collection_diff(
    source: list[dict[str, Any]],
    current: list[dict[str, Any]],
    *,
    signature,
) -> tuple[int, int, int]:
    """Return additions, duplicates and ID collisions."""

    current_ids = {
        str(item.get("id"))
        for item in current
        if str(item.get("id") or "").strip()
    }
    current_signatures = {signature(item) for item in current}
    additions = duplicates = collisions = 0
    for item in source:
        sig = signature(item)
        item_id = str(item.get("id") or "").strip()
        if sig in current_signatures:
            duplicates += 1
            continue
        if item_id and item_id in current_ids:
            collisions += 1
        additions += 1
    return additions, duplicates, collisions


def _legacy_profile_candidates(user_model: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for category, field in (
        ("fact", "facts"),
        ("preference", "preferences"),
        ("communication", "communication_style"),
    ):
        values = user_model.get(field)
        if isinstance(values, dict):
            for key, value in values.items():
                candidates.append({
                    "category": category,
                    "key": str(key),
                    "value": value,
                    "status": "current",
                    "source": "continuity_recovery_legacy",
                    "confidence": 1.0,
                    "explicitly_shared": False,
                })
    for category, field in (
        ("interest", "interests"),
        ("value", "values"),
        ("goal", "goals"),
    ):
        values = user_model.get(field)
        if isinstance(values, list):
            for value in values:
                rendered = str(value).strip()
                if rendered:
                    candidates.append({
                        "category": category,
                        "key": category,
                        "value": value,
                        "status": "current",
                        "source": "continuity_recovery_legacy",
                        "confidence": 1.0,
                        "explicitly_shared": False,
                    })
    return candidates


def _effective_source_profiles(user_model: dict[str, Any]) -> list[dict[str, Any]]:
    records = _clean_list(user_model.get("profile_records"))
    signatures = {_profile_signature(item) for item in records}
    for legacy in _legacy_profile_candidates(user_model):
        if _profile_signature(legacy) not in signatures:
            records.append(legacy)
            signatures.add(_profile_signature(legacy))
    return records


def _profile_conflicts(
    source: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> int:
    active: dict[tuple[str, str], Any] = {}
    for item in current:
        if str(item.get("status") or "current").lower() != "current":
            continue
        category = str(item.get("category") or "").lower()
        if category not in SCALAR_PROFILE_CATEGORIES:
            continue
        key = str(item.get("key") or "").lower()
        active[(category, key)] = item.get("value")

    conflicts = 0
    for item in source:
        if str(item.get("status") or "current").lower() != "current":
            continue
        category = str(item.get("category") or "").lower()
        if category not in SCALAR_PROFILE_CATEGORIES:
            continue
        key = str(item.get("key") or "").lower()
        slot = (category, key)
        if slot in active and active[slot] != item.get("value"):
            conflicts += 1
    return conflicts


def build_recovery_plan(mary: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Compute a content-free deterministic merge plan."""

    data = normalize_recovery_payload(payload)
    relationship = data["relationship"]
    source_profile = _effective_source_profiles(relationship["user_model"])

    current_episodes = mary.memory.episodic.export()
    current_semantic = [dict(item) for item in mary.memory.semantic.all()]
    current_history = list(mary.relationship.history.events)
    current_profile = list(mary.relationship.user_model.profile_records)
    current_milestones = mary.relationship.milestones.export()
    current_understanding = mary.relationship.understanding

    collections = {
        "episodic": (
            data["memory"]["episodic"],
            current_episodes,
            _episode_signature,
        ),
        "semantic": (
            data["memory"]["semantic"],
            current_semantic,
            _semantic_signature,
        ),
        "relationship_history": (
            relationship["history"]["events"],
            current_history,
            _history_signature,
        ),
        "relationship_milestones": (
            relationship["milestones"],
            current_milestones,
            _milestone_signature,
        ),
        "relationship_observations": (
            relationship["understanding"]["observations"],
            list(current_understanding.observations),
            _generic_signature,
        ),
        "relationship_inferences": (
            relationship["understanding"]["inferences"],
            list(current_understanding.inferences),
            _generic_signature,
        ),
        "relationship_patterns": (
            relationship["understanding"]["patterns"],
            list(current_understanding.patterns),
            _generic_signature,
        ),
    }

    additions: dict[str, int] = {}
    duplicates: dict[str, int] = {}
    id_collisions: dict[str, int] = {}
    for name, (source, current, signature) in collections.items():
        add, dup, collision = _collection_diff(
            source,
            current,
            signature=signature,
        )
        additions[name] = add
        duplicates[name] = dup
        id_collisions[name] = collision

    # Profile reconciliation has stronger semantics than a generic list diff:
    # current Core wins scalar conflicts and legacy facade values may duplicate
    # source-aware profile records. Simulate the actual merge against a cloned
    # UserModel so preview counts exactly match apply behavior.
    profile_clone = UserModel.from_dict(
        mary.relationship.user_model.to_dict()
    )
    profile_added, profile_conflicts = _merge_profiles(
        relationship["user_model"],
        profile_clone,
    )
    raw_profile_add, raw_profile_dup, raw_profile_collision = _collection_diff(
        source_profile,
        current_profile,
        signature=_profile_signature,
    )
    additions["creator_profile_records"] = profile_added
    duplicates["creator_profile_records"] = max(
        raw_profile_dup,
        max(0, len(source_profile) - profile_added - raw_profile_collision),
    )
    id_collisions["creator_profile_records"] = raw_profile_collision

    conflicts = {
        "creator_profile_scalar_conflicts": profile_conflicts,
    }
    return {
        "format": RECOVERY_FORMAT,
        "source": source_counts(data),
        "current": current_counts(mary),
        "additions": additions,
        "duplicates": duplicates,
        "id_collisions": id_collisions,
        "conflicts": conflicts,
        "total_additions": sum(additions.values()),
        "total_duplicates": sum(duplicates.values()),
        "total_id_collisions": sum(id_collisions.values()),
        "policy": {
            "current_core_wins_profile_conflicts": True,
            "conflicting_old_profile_values_become_historical": True,
            "working_memory_imported": False,
            "derived_indexes_imported": False,
            "provider_runtime_state_imported": False,
            "credentials_imported": False,
        },
    }


def _unique_id(
    item: dict[str, Any],
    used: set[str],
    *,
    prefix: str,
    signature,
) -> str:
    existing = str(item.get("id") or "").strip()
    if existing and existing not in used:
        used.add(existing)
        return existing
    generated = _digest(signature(item), prefix=prefix)
    candidate = generated
    suffix = 2
    while candidate in used:
        candidate = f"{generated}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _merge_simple_collection(
    source: list[dict[str, Any]],
    target: list[dict[str, Any]],
    *,
    signature,
    id_prefix: str,
) -> int:
    signatures = {signature(item) for item in target}
    used_ids = {
        str(item.get("id"))
        for item in target
        if str(item.get("id") or "").strip()
    }
    added = 0
    for raw in source:
        sig = signature(raw)
        if sig in signatures:
            continue
        item = deepcopy(raw)
        item["id"] = _unique_id(
            item,
            used_ids,
            prefix=id_prefix,
            signature=signature,
        )
        target.append(item)
        signatures.add(sig)
        added += 1
    return added


def _append_historical_profile(
    model: UserModel,
    raw: dict[str, Any],
    used_ids: set[str],
) -> bool:
    existing_signatures = {
        _profile_signature(item)
        for item in model.profile_records
    }
    item = deepcopy(raw)
    item["status"] = "historical"
    if _profile_signature(item) in existing_signatures:
        return False
    item["id"] = _unique_id(
        item,
        used_ids,
        prefix="profile_recovered",
        signature=_profile_signature,
    )
    now = datetime.now(timezone.utc).isoformat()
    item.setdefault("created_at", now)
    item["updated_at"] = now
    model.profile_records.append(item)
    return True


def _merge_profiles(
    source_user_model: dict[str, Any],
    model: UserModel,
) -> tuple[int, int]:
    source = _effective_source_profiles(source_user_model)
    existing_signatures = {
        _profile_signature(item)
        for item in model.profile_records
    }
    used_ids = {
        str(item.get("id"))
        for item in model.profile_records
        if str(item.get("id") or "").strip()
    }
    added = conflicts = 0

    for raw in source:
        sig = _profile_signature(raw)
        if sig in existing_signatures:
            continue

        category = str(raw.get("category") or "general").strip().lower()
        if category not in UserModel.VALID_PROFILE_CATEGORIES:
            continue
        key = str(raw.get("key") or category).strip().lower()
        if not key:
            continue
        value = raw.get("value")
        status = str(raw.get("status") or "current").strip().lower()

        if status != "current":
            if _append_historical_profile(model, raw, used_ids):
                added += 1
                existing_signatures.add(_profile_signature({
                    **raw,
                    "status": "historical",
                }))
            continue

        if category in SCALAR_PROFILE_CATEGORIES:
            current_same_slot = [
                item
                for item in model.profile_records
                if str(item.get("status") or "current").lower() == "current"
                and str(item.get("category") or "").lower() == category
                and str(item.get("key") or "").lower() == key
            ]
            if current_same_slot:
                if any(item.get("value") == value for item in current_same_slot):
                    continue
                conflicts += 1
                if _append_historical_profile(model, raw, used_ids):
                    added += 1
                continue

        if category in SET_PROFILE_CATEGORIES:
            normalized_value = str(value).strip().lower()
            duplicate = any(
                str(item.get("status") or "current").lower() == "current"
                and str(item.get("category") or "").lower() == category
                and str(item.get("value") or "").strip().lower() == normalized_value
                for item in model.profile_records
            )
            if duplicate:
                continue

        record = model.record_profile(
            category=category,
            key=key,
            value=value,
            source=str(raw.get("source") or "continuity_recovery"),
            confidence=raw.get("confidence", 1.0),
            explicitly_shared=bool(raw.get("explicitly_shared", False)),
            evidence_id=raw.get("evidence_id"),
            observation_id=raw.get("observation_id"),
        )
        desired_id = str(raw.get("id") or "").strip()
        if desired_id and desired_id not in used_ids:
            record["id"] = desired_id
            used_ids.add(desired_id)
        else:
            used_ids.add(str(record.get("id") or ""))
        if raw.get("created_at"):
            record["created_at"] = raw["created_at"]
        existing_signatures.add(_profile_signature(record))
        added += 1

    return added, conflicts


def capture_continuity_state(mary: Any) -> dict[str, Any]:
    return {
        "memory": {
            "episodic": mary.memory.episodic.export(),
            "semantic": [dict(item) for item in mary.memory.semantic.all()],
        },
        "relationship": {
            "user_model": mary.relationship.user_model.to_dict(),
            "history": mary.relationship.history.to_dict(),
            "understanding": mary.relationship.understanding.to_dict(),
            "milestones": mary.relationship.milestones.export(),
        },
    }


def restore_continuity_state(mary: Any, snapshot: dict[str, Any]) -> None:
    """Restore an in-memory snapshot after a failed persistence attempt."""

    memory = dict(snapshot.get("memory") or {})
    mary.memory.episodic.import_data(_clean_list(memory.get("episodic")))
    mary.memory.semantic.clear()
    for item in _clean_list(memory.get("semantic")):
        subject = item.get("subject")
        predicate = item.get("predicate")
        if subject is None or predicate is None:
            continue
        restored = mary.memory.semantic.add(
            subject=str(subject),
            predicate=str(predicate),
            value=item.get("value"),
            confidence=item.get("confidence", 1.0),
            source=item.get("source"),
        )
        for field in ("id", "created_at", "updated_at"):
            if item.get(field) is not None:
                restored[field] = item[field]

    relationship_payload = dict(snapshot.get("relationship") or {})
    relationship = mary.relationship
    relationship.user_model = UserModel.from_dict(
        relationship_payload.get("user_model")
    )
    relationship.history = RelationshipHistory.from_dict(
        relationship_payload.get("history")
    )
    relationship.understanding = RelationshipUnderstanding.from_dict(
        relationship_payload.get("understanding"),
        user_model=relationship.user_model,
        history=relationship.history,
    )
    milestones = relationship_payload.get("milestones")
    relationship.milestones = MilestoneManager(
        milestones if isinstance(milestones, list) else []
    )

    # Mary exposes compatibility aliases to these one authoritative objects.
    mary.user_model = relationship.user_model
    mary.relationship_history = relationship.history
    mary.relationship_understanding = relationship.understanding
    mary.relationship_milestones = relationship.milestones


def apply_recovery_payload(mary: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Merge normalized recovery state into the live canonical Mary in memory.

    The caller owns locking, backup creation and persistence/rollback.
    """

    data = normalize_recovery_payload(payload)
    before = current_counts(mary)
    relationship_source = data["relationship"]

    current_episode_signatures = {
        _episode_signature(item) for item in mary.memory.episodic.export()
    }
    used_episode_ids = {
        str(item.get("id"))
        for item in mary.memory.episodic.export()
        if str(item.get("id") or "").strip()
    }
    episode_added = 0
    for raw in data["memory"]["episodic"]:
        sig = _episode_signature(raw)
        if sig in current_episode_signatures:
            continue
        item = deepcopy(raw)
        item["id"] = _unique_id(
            item,
            used_episode_ids,
            prefix="episode_recovered",
            signature=_episode_signature,
        )
        mary.memory.episodic.add(EpisodicMemory.from_dict(item))
        current_episode_signatures.add(sig)
        episode_added += 1

    semantic_added = 0
    existing_semantic = {
        _semantic_signature(dict(item))
        for item in mary.memory.semantic.all()
    }
    for raw in data["memory"]["semantic"]:
        sig = _semantic_signature(raw)
        if sig in existing_semantic:
            continue
        subject = raw.get("subject")
        predicate = raw.get("predicate")
        if subject is None or predicate is None:
            continue
        restored = mary.memory.semantic.add(
            subject=str(subject),
            predicate=str(predicate),
            value=raw.get("value"),
            confidence=raw.get("confidence", 1.0),
            source=raw.get("source") or "continuity_recovery",
        )
        for field in ("id", "created_at", "updated_at"):
            if raw.get(field) is not None:
                restored[field] = raw[field]
        existing_semantic.add(sig)
        semantic_added += 1

    history_added = _merge_simple_collection(
        relationship_source["history"]["events"],
        mary.relationship.history.events,
        signature=_history_signature,
        id_prefix="relationship_recovered",
    )

    profile_added, profile_conflicts = _merge_profiles(
        relationship_source["user_model"],
        mary.relationship.user_model,
    )

    milestone_added = _merge_simple_collection(
        relationship_source["milestones"],
        mary.relationship.milestones.milestones,
        signature=_milestone_signature,
        id_prefix="milestone_recovered",
    )

    understanding_added: dict[str, int] = {}
    for name in UNDERSTANDING_COLLECTIONS:
        target = getattr(mary.relationship.understanding, name)
        understanding_added[name] = _merge_simple_collection(
            relationship_source["understanding"][name],
            target,
            signature=_generic_signature,
            id_prefix=f"{name[:-1]}_recovered",
        )

    mary.relationship._compact_state()
    after = current_counts(mary)
    return {
        "format": RECOVERY_FORMAT,
        "before": before,
        "after": after,
        "added": {
            "episodic": episode_added,
            "semantic": semantic_added,
            "relationship_history": history_added,
            "creator_profile_records": profile_added,
            "relationship_milestones": milestone_added,
            "relationship_observations": understanding_added["observations"],
            "relationship_inferences": understanding_added["inferences"],
            "relationship_patterns": understanding_added["patterns"],
        },
        "profile_conflicts_preserved_as_history": profile_conflicts,
    }
