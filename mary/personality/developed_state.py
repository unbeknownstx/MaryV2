"""
MaryV2 - Developed Self-State Persistence

Persists only Mary's explicitly developed durable self-state.

Canonical authored character/personality/value/preference defaults remain in
code and are re-seeded on every construction. This store records only durable
overrides produced through MaryV2's existing development paths.

Model dialogue, temporary imagination, conversation context, and working memory
are never persistence sources here.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import json
import os
from pathlib import Path
from typing import Any, Mapping


class DevelopedSelfStateStore:
    """Persistence boundary for Mary's durable developed self-state."""

    SCHEMA_VERSION = 1
    CANONICAL_PREFERENCE_SOURCES = {
        "character_core",
        "canonical",
        "authored",
        "authored_preferences",
    }

    def __init__(
        self,
        *,
        personality: Any,
        values: Any,
        preferences: Any,
        personality_development: Any,
    ) -> None:
        self.personality = personality
        self.values = values
        self.preferences = preferences
        self.personality_development = personality_development

        self.path: Path | None = None
        self.auto_save = False
        self.loaded = False

        self._personality_baseline = self._current_personality_traits()
        self._approved_personality_traits: set[str] = set()

    # ============================================================
    # WIRING
    # ============================================================

    def rebind(
        self,
        *,
        personality: Any,
        values: Any,
        preferences: Any,
        personality_development: Any,
    ) -> None:
        """Rebind the store to Mary's authoritative live subsystem objects."""

        self.personality = personality
        self.values = values
        self.preferences = preferences
        self.personality_development = personality_development

    # ============================================================
    # CONFIGURATION
    # ============================================================

    def configure(
        self,
        path: str | Path,
        *,
        auto_save: bool = True,
        load: bool = True,
    ) -> bool:
        """Enable persistence. Construction alone never touches the filesystem."""

        self.path = Path(path)
        self.auto_save = bool(auto_save)

        if load:
            return self.load()

        return True

    @property
    def configured(self) -> bool:
        return self.path is not None

    # ============================================================
    # APPROVED DEVELOPMENT TRACKING
    # ============================================================

    def record_approved_personality_change(
        self,
        proposal: Any,
    ) -> None:
        """Mark the trait changed by a successfully approved proposal."""

        trait = self._proposal_trait(proposal)
        if trait:
            self._approved_personality_traits.add(trait)

        if self.auto_save and self.configured:
            self.save()

    def save_if_configured(self) -> bool:
        if not self.configured:
            return True
        if not self.auto_save:
            return True
        return self.save()

    # ============================================================
    # SAVE / LOAD
    # ============================================================

    def save(self) -> bool:
        """Atomically save developed state if persistence is configured."""

        if self.path is None:
            return True

        payload = self.to_dict()
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)

        temporary = path.with_name(f".{path.name}.tmp")

        try:
            temporary.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass

        return True

    def load(self) -> bool:
        """Load durable developed state without replacing canonical systems."""

        if self.path is None:
            return True

        path = self.path
        if not path.exists():
            self.loaded = True
            return True

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return False

        if not isinstance(payload, dict):
            return False

        # Reconstruct development/history first when the subsystem exposes its
        # public loader. Any trait mutation caused by loading is normalized back
        # to canonical baseline + explicitly approved exact overrides below.
        development_data = payload.get("personality_development")
        development_load = getattr(
            self.personality_development,
            "load",
            None,
        )
        if isinstance(development_data, dict) and callable(development_load):
            try:
                development_load(deepcopy(development_data))
            except (TypeError, ValueError, KeyError):
                # The exact approved end-state below remains authoritative even
                # when an older development payload cannot be reconstructed.
                pass

        overrides = payload.get("personality_overrides", {})
        if not isinstance(overrides, dict):
            overrides = {}

        self._approved_personality_traits = {
            str(name).strip()
            for name in overrides
            if str(name).strip()
        }

        # Reset every personality trait to the authored baseline first. This
        # prevents a development-history loader from accidentally replaying a
        # delta twice or promoting an unapproved proposal into identity.
        set_trait = getattr(self.personality, "set_trait", None)
        if callable(set_trait):
            for trait, value in self._personality_baseline.items():
                set_trait(trait, value)

            for trait, value in overrides.items():
                try:
                    set_trait(str(trait), float(value))
                except (TypeError, ValueError):
                    continue

        preference_overrides = payload.get("preference_overrides", {})
        if isinstance(preference_overrides, dict):
            preference_load = getattr(self.preferences, "load", None)
            if callable(preference_load):
                preference_load(deepcopy(preference_overrides))

        self.loaded = True
        return True

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self) -> dict[str, Any]:
        """Return only durable developed overrides plus development metadata."""

        current_traits = self._current_personality_traits()
        personality_overrides: dict[str, float] = {}

        for trait in sorted(self._approved_personality_traits):
            if trait in current_traits:
                personality_overrides[trait] = current_traits[trait]

        preference_overrides = self._developed_preferences()

        development_data: dict[str, Any] = {}
        development_to_dict = getattr(
            self.personality_development,
            "to_dict",
            None,
        )
        if callable(development_to_dict):
            try:
                result = development_to_dict()
            except (TypeError, ValueError, KeyError):
                result = {}
            if isinstance(result, dict):
                development_data = result

        return self._json_safe({
            "schema_version": self.SCHEMA_VERSION,
            "personality_overrides": personality_overrides,
            "preference_overrides": preference_overrides,
            "personality_development": development_data,
            "policy": {
                "canonical_defaults_live_in_code": True,
                "model_output_is_persistence_source": False,
                "situational_imagination_is_persisted": False,
                "approved_personality_changes_only": True,
                "authored_preferences_are_not_duplicated": True,
            },
        })

    def status(self) -> dict[str, Any]:
        payload = self.to_dict()
        return {
            "configured": self.configured,
            "path": str(self.path) if self.path is not None else None,
            "auto_save": self.auto_save,
            "loaded": self.loaded,
            "personality_overrides": len(payload["personality_overrides"]),
            "preference_overrides": len(payload["preference_overrides"]),
        }

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    def _current_personality_traits(self) -> dict[str, float]:
        getter = getattr(self.personality, "get_traits", None)
        if not callable(getter):
            return {}
        result = getter()
        if not isinstance(result, dict):
            return {}
        normalized: dict[str, float] = {}
        for key, value in result.items():
            try:
                normalized[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        return normalized

    def _developed_preferences(self) -> dict[str, dict[str, Any]]:
        to_dict = getattr(self.preferences, "to_dict", None)
        if not callable(to_dict):
            return {}

        result = to_dict()
        if not isinstance(result, dict):
            return {}

        developed: dict[str, dict[str, Any]] = {}
        for name, preference in result.items():
            if not isinstance(preference, dict):
                continue
            source = str(preference.get("source", "")).strip().lower()
            if source in self.CANONICAL_PREFERENCE_SOURCES:
                continue
            developed[str(name)] = deepcopy(preference)

        return developed

    @staticmethod
    def _proposal_trait(proposal: Any) -> str:
        if isinstance(proposal, Mapping):
            for key in ("trait", "name", "target"):
                value = proposal.get(key)
                if value:
                    return str(value).strip()

        for key in ("trait", "name", "target"):
            value = getattr(proposal, key, None)
            if value:
                return str(value).strip()

        return ""

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Mapping):
            return {
                str(key): cls._json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [cls._json_safe(item) for item in value]

        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            try:
                return cls._json_safe(to_dict())
            except Exception:
                pass

        return str(value)
