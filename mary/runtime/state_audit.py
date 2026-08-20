"""Read-only persistent-state audit helpers for MaryV2.

The audit is intentionally non-destructive.  It helps identify benchmark/probe
residue in Mary's real creator model without silently deleting user data.
"""

from __future__ import annotations

from typing import Any

from mary.relationship.provenance import creator_record_test_flags


def _memory_index(mary: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        memories = mary.memory.episodic.all()
    except Exception:
        memories = []
    for memory in memories:
        memory_id = str(getattr(memory, "id", "") or "")
        content = str(getattr(memory, "content", "") or "")
        if memory_id:
            result[memory_id] = content
    return result


def audit_creator_state(mary: Any) -> dict[str, Any]:
    """Return current creator records with provenance and conservative flags."""

    model = getattr(mary, "user_model", None)
    if model is None:
        return {"records": [], "flagged": [], "count": 0, "flagged_count": 0}

    memory_by_id = _memory_index(mary)
    try:
        records = list(model.get_profile_records(current_only=False))
    except Exception:
        records = []

    rendered: list[dict[str, Any]] = []
    flagged: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        evidence_id = str(record.get("evidence_id", "") or "")
        evidence_text = memory_by_id.get(evidence_id, "")
        key = str(record.get("key", "") or "")
        value = str(record.get("value", "") or "")
        source = str(record.get("source", "") or "")
        reasons = creator_record_test_flags(
            record,
            evidence_text=evidence_text,
        )

        item = {
            "id": record.get("id"),
            "category": record.get("category"),
            "key": key,
            "value": value,
            "status": record.get("status"),
            "source": source,
            "confidence": record.get("confidence"),
            "explicitly_shared": bool(record.get("explicitly_shared")),
            "evidence_id": evidence_id or None,
            "evidence_preview": evidence_text[:180] if evidence_text else None,
            "flags": reasons,
        }
        rendered.append(item)
        if reasons:
            flagged.append(item)

    return {
        "policy": "read_only_no_automatic_deletion",
        "count": len(rendered),
        "flagged_count": len(flagged),
        "records": rendered,
        "flagged": flagged,
    }


def format_creator_state_audit(mary: Any, *, show_all: bool = False) -> str:
    audit = audit_creator_state(mary)
    records = audit["records"] if show_all else audit["flagged"]
    lines = [
        "MARYV2 CREATOR-STATE AUDIT",
        "────────────────────────────────",
        f"Profile records: {audit['count']}",
        f"Flagged test/probe-like records: {audit['flagged_count']}",
        "Policy: read-only; nothing is deleted automatically.",
    ]
    if not records:
        lines.append("No records matched the conservative test/probe markers.")
        if not show_all:
            lines.append("Use `python -m scripts.audit_creator_state --all` to inspect every record/provenance entry.")
        return "\n".join(lines)

    lines.append("")
    for item in records:
        lines.append(
            f"- {item.get('id')}: {item.get('category')}/{item.get('key')} = {item.get('value')}"
        )
        lines.append(
            f"  source={item.get('source')} status={item.get('status')} confidence={item.get('confidence')}"
        )
        if item.get("evidence_preview"):
            lines.append(f"  evidence={item.get('evidence_preview')}")
        if item.get("flags"):
            lines.append("  flags=" + "; ".join(item["flags"]))
    return "\n".join(lines)
