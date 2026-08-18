"""MaryV2 self-fact provenance.

This module does *not* become a second identity database.  It projects Mary's
existing authoritative systems into explicit provenance classes so cognition
can distinguish:

    canonical   - deliberately authored/stable Mary facts
    developed   - durable state that changed through an approved development path
    situational - temporary conversational imagination; never persisted by speech
    unknown     - absent from Mary's represented self-state

The language model is an expression engine.  Model output is never, by itself,
a persistence source for Mary's identity, personality, values, or preferences.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANONICAL = "canonical"
DEVELOPED = "developed"
SITUATIONAL = "situational"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class SelfFactRecord:
    """Compact provenance record for one represented self fact."""

    domain: str
    key: str
    value: Any
    provenance: str
    source: str
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "key": self.key,
            "value": self.value,
            "provenance": self.provenance,
            "source": self.source,
            "confidence": max(0.0, min(1.0, float(self.confidence))),
        }


class SelfProvenance:
    """Read-only provenance view over Mary's existing self systems."""

    # Sources that represent deliberate authored Mary state rather than later
    # experience.  Other preference sources are treated as developed state.
    CANONICAL_PREFERENCE_SOURCES = {
        "character_core",
        "canonical",
        "authored",
    }

    def __init__(
        self,
        *,
        biography: Any,
        personality: Any,
        character: Any,
        values: Any,
        preferences: Any,
        personality_development: Any = None,
    ) -> None:
        self.biography = biography
        self.personality = personality
        self.character = character
        self.values = values
        self.preferences = preferences
        self.personality_development = personality_development

    def snapshot(self) -> dict[str, Any]:
        """Return a compact provenance snapshot for one cognitive turn."""

        canonical: list[dict[str, Any]] = []
        developed: list[dict[str, Any]] = []

        canonical.extend(self._biography_records())
        canonical.extend(self._preference_records(canonical_only=True))
        developed.extend(self._preference_records(canonical_only=False))
        developed.extend(self._development_records())

        return {
            "canonical": canonical,
            "developed": developed,
            "source_map": {
                "biography": CANONICAL,
                "character_core": CANONICAL,
                "personality_baseline": CANONICAL,
                "values_baseline": CANONICAL,
                "authored_preferences": CANONICAL,
                "approved_personality_development": DEVELOPED,
                "experience_preferences": DEVELOPED,
                "model_dialogue": SITUATIONAL,
                "absent_self_fact": UNKNOWN,
            },
            "policy": {
                "model_output_is_persistence_source": False,
                "situational_imagination_is_allowed": True,
                "situational_imagination_is_persisted": False,
                "unknown_self_fact_must_remain_unknown": True,
                "durable_change_requires_explicit_system_path": True,
            },
            "definitions": {
                CANONICAL: "Deliberately authored or stable Mary state.",
                DEVELOPED: "Durable Mary state changed through an explicit development/experience path.",
                SITUATIONAL: "Temporary conversational imagination that does not mutate Mary.",
                UNKNOWN: "A self fact not represented by Mary's current systems.",
            },
        }

    def known_preference_names(self) -> set[str]:
        """Return all represented Mary preference names."""

        names: set[str] = set()
        getter = getattr(self.preferences, "get_preferences", None)
        if not callable(getter):
            return names
        for item in getter():
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip().lower()
            if name:
                names.add(name)
        return names

    def _biography_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        try:
            raw = self.biography.to_dict()
        except Exception:
            raw = {}
        for item in raw.get("entries", []) if isinstance(raw, dict) else []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            records.append(
                SelfFactRecord(
                    domain=str(item.get("category", "biography") or "biography"),
                    key=title,
                    value=item.get("content", ""),
                    provenance=CANONICAL,
                    source="biography",
                    confidence=1.0,
                ).to_dict()
            )
        return records

    def _preference_records(self, *, canonical_only: bool) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        getter = getattr(self.preferences, "get_preferences", None)
        if not callable(getter):
            return records

        for item in getter():
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", "system") or "system").strip().lower()
            is_canonical = source in self.CANONICAL_PREFERENCE_SOURCES
            if canonical_only != is_canonical:
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            records.append(
                SelfFactRecord(
                    domain="preference",
                    key=name,
                    value={
                        "category": item.get("category", "general"),
                        "polarity": item.get("polarity", 0.0),
                        "strength": item.get("strength", 0.0),
                    },
                    provenance=CANONICAL if is_canonical else DEVELOPED,
                    source=source,
                    confidence=float(item.get("confidence", 0.5) or 0.5),
                ).to_dict()
            )
        return records

    def _development_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        development = self.personality_development
        history = getattr(development, "history", []) if development is not None else []
        if not isinstance(history, list):
            return records

        for item in history[-12:]:
            if not isinstance(item, dict) or item.get("status") != "applied":
                continue
            trait = str(item.get("trait", "")).strip()
            if not trait:
                continue
            records.append(
                SelfFactRecord(
                    domain="personality_trait",
                    key=trait,
                    value=item.get("new_value"),
                    provenance=DEVELOPED,
                    source=str(item.get("source", "experience") or "experience"),
                    confidence=float(item.get("confidence", 0.5) or 0.5),
                ).to_dict()
            )
        return records
