"""Prompt-only selection for ephemeral orchestration evidence.

TaskWorkspace remains the audit owner. This module only decides which evidence
is worth serializing into a specialist model prompt. Durable/creator-backed
sources do not expire merely because they are old; rebuildable tool/web/model
outputs can age out or be compressed under prompt pressure.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from mary.orchestration.models import ProvenanceSource, TaskEvidence

VERSION = "13.46"

_PROTECTED = {
    ProvenanceSource.CREATOR.value,
    ProvenanceSource.PERSISTENT_MEMORY.value,
    ProvenanceSource.RELATIONSHIP_MODEL.value,
    ProvenanceSource.MARY_RUNTIME.value,
}
_REBUILDABLE = {
    ProvenanceSource.LOCAL_TOOL.value,
    ProvenanceSource.TEST_RESULT.value,
    ProvenanceSource.WEB.value,
    ProvenanceSource.GROQ.value,
    ProvenanceSource.GEMINI.value,
    ProvenanceSource.OPENROUTER.value,
    ProvenanceSource.OLLAMA.value,
    ProvenanceSource.OPENAI.value,
    ProvenanceSource.INFERENCE.value,
}


@dataclass(frozen=True)
class PromptEvidenceSelection:
    selected: tuple[TaskEvidence, ...]
    omitted_ids: tuple[str, ...]
    stale_ids: tuple[str, ...]
    protected_ids: tuple[str, ...]
    total_candidates: int
    policy_version: str = VERSION

    def telemetry(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "total_candidates": self.total_candidates,
            "selected_count": len(self.selected),
            "omitted_count": len(self.omitted_ids),
            "stale_count": len(self.stale_ids),
            "protected_count": len(self.protected_ids),
            # IDs are task-local opaque identifiers; no evidence prose is kept.
            "omitted_ids": list(self.omitted_ids),
            "stale_ids": list(self.stale_ids),
        }


def _age_seconds(created_at: str, *, now: datetime) -> float | None:
    try:
        parsed = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (now - parsed.astimezone(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


def _importance(item: TaskEvidence) -> float:
    metadata = dict(item.metadata or {})
    try:
        explicit = float(metadata.get("prompt_importance", 0.0) or 0.0)
    except (TypeError, ValueError):
        explicit = 0.0
    confidence = max(0.0, min(1.0, float(item.confidence or 0.0)))
    return max(explicit, confidence)


def select_prompt_evidence(
    evidence: Iterable[TaskEvidence],
    *,
    max_items: int = 8,
    rebuildable_ttl_seconds: float = 1800.0,
    now: datetime | None = None,
) -> PromptEvidenceSelection:
    """Select prompt evidence without deleting anything from TaskWorkspace.

    Protected provenance is retained preferentially regardless of age. Old
    rebuildable evidence is omitted unless explicitly marked high-importance.
    Remaining slots favor newer/high-confidence evidence while preserving final
    chronological order for model readability.
    """
    rows = list(evidence or ())
    limit = max(1, min(32, int(max_items)))
    ttl = max(30.0, min(86_400.0, float(rebuildable_ttl_seconds)))
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    else:
        instant = instant.astimezone(timezone.utc)

    protected: list[tuple[int, TaskEvidence]] = []
    candidates: list[tuple[int, TaskEvidence, float | None, float]] = []
    stale_ids: list[str] = []

    for index, item in enumerate(rows):
        provenance = str(item.provenance or "").strip().lower()
        if provenance in _PROTECTED:
            protected.append((index, item))
            continue
        age = _age_seconds(item.created_at, now=instant)
        importance = _importance(item)
        stale = bool(
            provenance in _REBUILDABLE
            and age is not None
            and age > ttl
            and importance < 0.95
        )
        if stale:
            stale_ids.append(item.evidence_id)
            continue
        candidates.append((index, item, age, importance))

    # Protected facts win scarce prompt slots, but if there are more protected
    # records than the bound, keep the newest ones rather than exceeding budget.
    protected = protected[-limit:]
    remaining = max(0, limit - len(protected))

    ranked = sorted(
        candidates,
        key=lambda row: (
            row[3],                         # confidence/explicit importance
            -(row[2] if row[2] is not None else 0.0),  # prefer newer
            row[0],
        ),
        reverse=True,
    )[:remaining]

    selected_pairs = protected + [(index, item) for index, item, _age, _imp in ranked]
    selected_pairs.sort(key=lambda row: row[0])
    selected = tuple(item for _index, item in selected_pairs)
    selected_ids = {item.evidence_id for item in selected}
    omitted = tuple(item.evidence_id for item in rows if item.evidence_id not in selected_ids)

    return PromptEvidenceSelection(
        selected=selected,
        omitted_ids=omitted,
        stale_ids=tuple(stale_ids),
        protected_ids=tuple(item.evidence_id for _index, item in protected),
        total_candidates=len(rows),
    )
