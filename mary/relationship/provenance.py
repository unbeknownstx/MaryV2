"""Creator-profile provenance helpers used by conversational surfaces.

Persistent state can legitimately contain old development probes.  Those records
remain auditable and recoverable, but they should not quietly become part of
Mary's natural description of her creator.  This module provides a conservative,
read-only view that excludes obvious test/probe-shaped records from ordinary
conversation while leaving the underlying durable state untouched.
"""

from __future__ import annotations

from typing import Any, Mapping


TEST_MARKERS = (
    "test animal",
    "test_animal",
    "probe phrase",
    "persistence probe",
    "restart probe",
    "cobalt lantern",
    "benchmark",
    "pytest",
)



def text_has_test_probe_marker(text: str) -> bool:
    """Return whether plain text is obviously development/test probe material."""

    lowered = str(text or "").casefold()
    return any(marker in lowered for marker in TEST_MARKERS)

def creator_record_test_flags(
    record: Mapping[str, Any],
    *,
    evidence_text: str = "",
) -> list[str]:
    """Return conservative test/probe flags for one creator-profile record."""

    key = str(record.get("key", "") or "")
    value = str(record.get("value", "") or "")
    source = str(record.get("source", "") or "")
    haystack = " ".join((key, value, source, str(evidence_text or ""))).casefold()

    reasons: list[str] = []
    if text_has_test_probe_marker(haystack):
        reasons.append("contains test/probe marker")
    if key.casefold().startswith(("test_", "probe_")):
        reasons.append("test/probe-shaped key")
    if source.casefold().startswith(("test", "pytest", "verify")):
        reasons.append("test/verification source")
    return reasons


def is_creator_record_conversation_safe(
    record: Mapping[str, Any],
    *,
    evidence_text: str = "",
) -> bool:
    """Return whether a durable creator record belongs in normal conversation."""

    return not creator_record_test_flags(record, evidence_text=evidence_text)


def conversation_profile(
    user_model: Any,
    *,
    evidence_by_id: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a current creator-profile view with obvious probes excluded.

    This never mutates ``user_model``.  Debug/audit surfaces can still show all
    records, including excluded ones.
    """

    evidence_by_id = evidence_by_id or {}
    result: dict[str, Any] = {
        "identity": user_model.get_identity(),
        "facts": {},
        "preferences": {},
        "interests": [],
        "values": [],
        "goals": [],
        "communication_style": {},
        "general": [],
        "excluded_probe_records": 0,
    }

    try:
        records = list(user_model.get_profile_records(current_only=True))
    except Exception:
        records = []

    for record in records:
        if not isinstance(record, dict):
            continue
        evidence_id = str(record.get("evidence_id", "") or "")
        evidence_text = str(evidence_by_id.get(evidence_id, "") or "")
        if not is_creator_record_conversation_safe(record, evidence_text=evidence_text):
            result["excluded_probe_records"] += 1
            continue

        category = str(record.get("category", "") or "").casefold()
        key = str(record.get("key", "") or "")
        value = record.get("value")
        if category == "fact":
            result["facts"][key] = value
        elif category == "preference":
            result["preferences"][key] = value
        elif category == "communication":
            result["communication_style"][key] = value
        elif category in {"interest", "value", "goal"}:
            target = result[category + "s"]
            normalized = str(value).strip().casefold()
            if normalized and all(str(item).strip().casefold() != normalized for item in target):
                target.append(value)
        elif category == "general":
            result["general"].append(value)

    return result
