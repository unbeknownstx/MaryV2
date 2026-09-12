"""Structured, read-only character intelligence over Mary's authored sourcebook.

This module borrows the useful ideas behind temporal/graph memory systems without
creating another character authority. It projects already-selected creator evidence
into typed claims and provenance edges for one turn. The underlying sourcebook
remains the authored source of truth; memory/relationship state keep their current
owners.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import re
from typing import Any

from .sourcebook import CharacterSourceSelection, CharacterSourcebook as BaseCharacterSourcebook

_TOKEN_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)


@dataclass(frozen=True)
class CharacterClaim:
    claim_id: str
    record_id: str
    claim_type: str
    authority_tier: str
    boundary: str
    heading: str
    source: str
    labels: tuple[str, ...]
    text: str
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CharacterEvidenceEdge:
    subject: str
    predicate: str
    object_id: str
    provenance: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class IntelligentCharacterSelection:
    """Compatibility wrapper around the canonical sourcebook selection."""

    selection: CharacterSourceSelection

    @property
    def records(self):
        return self.selection.records

    @property
    def query(self) -> str:
        return self.selection.query

    @property
    def total_records(self) -> int:
        return self.selection.total_records

    @property
    def sourcebook_hash(self) -> str:
        return self.selection.sourcebook_hash

    def prompt_view(self) -> dict[str, Any]:
        return enrich_prompt_view(self.selection.prompt_view())


def _authority_tier(labels: tuple[str, ...], boundary: str) -> str:
    values = {str(item).upper() for item in labels}
    if boundary == "negative_example_not_character_instruction" or "NEG" in values:
        return "negative_example"
    if "AI" in values:
        return "ai_mary_authored"
    if "DNA" in values:
        return "shared_character_dna"
    if "PUB" in values:
        return "public_performer"
    if "FC" in values or boundary == "fictional_reference_not_ai_memory":
        return "fictional_reference"
    if "ALT" in values:
        return "alternate_reference"
    return "creator_authored"


def _claim_type(kind: str, heading: str) -> str:
    joined = f"{kind} {heading}".casefold()
    for marker, value in (
        ("voice", "voice"),
        ("speech", "voice"),
        ("romance", "relationship_behavior"),
        ("relationship", "relationship_behavior"),
        ("value", "value"),
        ("boundary", "boundary"),
        ("negative", "anti_pattern"),
        ("anti-", "anti_pattern"),
        ("behavior", "behavior"),
        ("reaction", "reaction"),
        ("perform", "performance"),
        ("canon", "canon_reference"),
    ):
        if marker in joined:
            return value
    return "character_evidence"


def _heading_key(value: str) -> str:
    tokens = [token.casefold() for token in _TOKEN_RE.findall(value or "") if len(token) > 2]
    return " ".join(tokens[:12])


def _conflicts(claims: list[CharacterClaim]) -> list[dict[str, Any]]:
    groups: dict[str, list[CharacterClaim]] = {}
    for claim in claims:
        key = _heading_key(claim.heading)
        if key:
            groups.setdefault(key, []).append(claim)
    output: list[dict[str, Any]] = []
    for key, items in groups.items():
        negative = [item for item in items if item.authority_tier == "negative_example"]
        positive = [item for item in items if item.authority_tier != "negative_example"]
        if negative and positive:
            output.append({
                "kind": "positive_negative_evidence_collision",
                "heading_key": key,
                "positive_claims": [item.claim_id for item in positive[:4]],
                "negative_claims": [item.claim_id for item in negative[:4]],
                "resolution": "treat negative records as anti-pattern evidence, never as desired behavior",
            })
    return output[:8]


def enrich_prompt_view(view: dict[str, Any] | None) -> dict[str, Any]:
    """Add bounded typed provenance to the existing sourcebook prompt view."""
    result = dict(view or {})
    records = list(result.get("records") or [])[:12]
    claims: list[CharacterClaim] = []
    edges: list[CharacterEvidenceEdge] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        record_id = str(item.get("id") or "")[:96]
        text = " ".join(str(item.get("text") or "").split())[:1800]
        if not record_id or not text:
            continue
        labels = tuple(str(label).upper()[:16] for label in list(item.get("labels") or [])[:8])
        boundary = str(item.get("boundary") or "authored_character_evidence")[:80]
        heading = " ".join(str(item.get("heading") or "").split())[:240]
        source = str(item.get("source") or "")[:160]
        kind = str(item.get("kind") or "character_source")[:80]
        content_hash = sha256(text.encode("utf-8")).hexdigest()[:20]
        claim_id = sha256(f"{record_id}:{content_hash}".encode("utf-8")).hexdigest()[:18]
        claim = CharacterClaim(
            claim_id=claim_id,
            record_id=record_id,
            claim_type=_claim_type(kind, heading),
            authority_tier=_authority_tier(labels, boundary),
            boundary=boundary,
            heading=heading,
            source=source,
            labels=labels,
            text=text,
            content_hash=content_hash,
        )
        claims.append(claim)
        edges.append(CharacterEvidenceEdge("Mary", "supported_by", claim_id, source or "creator_authored"))
        if heading:
            edges.append(CharacterEvidenceEdge(claim_id, "under_heading", _heading_key(heading)[:120], source or "creator_authored"))

    result["structured_evidence"] = {
        "semantics": {
            "projection_only": True,
            "character_authority_owner": "CharacterSourcebook",
            "memory_owner": False,
            "relationship_owner": False,
            "model_mutable": False,
        },
        "claims": [claim.to_dict() for claim in claims],
        "edges": [edge.to_dict() for edge in edges[:24]],
        "conflicts": _conflicts(claims),
    }
    return result


def compile_character_context(
    sourcebook: Any,
    query: str,
    *,
    limit: int = 6,
    max_characters: int = 4200,
) -> dict[str, Any]:
    select = getattr(sourcebook, "select", None)
    if not callable(select):
        return {}
    selection = select(str(query or ""), limit=limit, max_characters=max_characters)
    prompt_view = getattr(selection, "prompt_view", None)
    return enrich_prompt_view(dict(prompt_view() or {}) if callable(prompt_view) else {})


class IntelligentCharacterSourcebook(BaseCharacterSourcebook):
    """Drop-in sourcebook that enriches selections without changing authority."""

    VERSION = "1.1"

    def select(self, query: str, *, limit: int = 6, max_characters: int = 4200) -> IntelligentCharacterSelection:
        base = super().select(query, limit=limit, max_characters=max_characters)
        return IntelligentCharacterSelection(base)

    def snapshot(self) -> dict[str, Any]:
        result = super().snapshot()
        result["version"] = self.VERSION
        result["structured_character_intelligence"] = True
        result["external_graph_required"] = False
        return result
