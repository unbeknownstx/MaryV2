"""
MaryV2 - Relationship User Model

Represents Mary's structured, source-aware understanding of her creator.

Memory stores experiences.  The user model stores Mary's current structured
understanding while preserving historical creator-profile records and their
provenance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class UserModel:
    """Structured model of Mary's creator, Unbe."""

    VALID_PROFILE_CATEGORIES = {
        "fact",
        "preference",
        "interest",
        "value",
        "goal",
        "communication",
        "general",
    }

    def __init__(
        self,
        creator_id: str = "creator",
        name: str = "unbe",
    ):
        self.creator_id = creator_id
        self.name = name

        # Backward-compatible current-value facade.
        self.facts: Dict[str, Any] = {}
        self.preferences: Dict[str, Any] = {}
        self.interests: List[str] = []
        self.values: List[str] = []
        self.goals: List[str] = []
        self.communication_style: Dict[str, Any] = {}

        # Source-aware append-only relationship profile history.
        self.profile_records: List[Dict[str, Any]] = []

        self.created_at = self._timestamp()
        self.updated_at = self.created_at

    # ============================================================
    # IDENTITY
    # ============================================================

    def get_identity(self) -> Dict[str, Any]:
        return {
            "id": self.creator_id,
            "name": self.name,
        }

    def set_name(self, name: str) -> None:
        if not name:
            return
        self.name = str(name).strip()
        self._touch()

    # ============================================================
    # SOURCE-AWARE PROFILE
    # ============================================================

    def record_profile(
        self,
        *,
        category: str,
        key: str,
        value: Any,
        source: str,
        confidence: float = 1.0,
        explicitly_shared: bool = False,
        evidence_id: str | None = None,
        observation_id: str | None = None,
    ) -> Dict[str, Any]:
        """Record structured creator information while preserving history."""

        category = str(category).strip().lower()
        key = str(key).strip().lower()
        if category not in self.VALID_PROFILE_CATEGORIES:
            raise ValueError(f"Unsupported profile category: {category}")
        if not key:
            raise ValueError("Profile key cannot be empty.")

        confidence = self._clamp(confidence)
        now = self._timestamp()

        # Current scalar values supersede earlier values for the same key but
        # remain available as historical records.
        if category in {"fact", "preference", "communication", "general"}:
            for record in self.profile_records:
                if record.get("status") != "current":
                    continue
                if record.get("category") != category:
                    continue
                if record.get("key") != key:
                    continue
                if record.get("value") == value:
                    record["confidence"] = confidence
                    record["source"] = source
                    record["explicitly_shared"] = bool(explicitly_shared)
                    record["evidence_id"] = evidence_id
                    record["observation_id"] = observation_id
                    record["updated_at"] = now
                    self._apply_current(category, key, value)
                    self._touch()
                    return record
                record["status"] = "historical"
                record["updated_at"] = now

        # Set-like categories deduplicate by normalized value.
        if category in {"interest", "value", "goal"}:
            normalized_value = str(value).strip().lower()
            for record in self.profile_records:
                if record.get("status") != "current":
                    continue
                if record.get("category") != category:
                    continue
                if str(record.get("value", "")).strip().lower() != normalized_value:
                    continue
                record["confidence"] = confidence
                record["source"] = source
                record["explicitly_shared"] = bool(explicitly_shared)
                record["evidence_id"] = evidence_id
                record["observation_id"] = observation_id
                record["updated_at"] = now
                self._apply_current(category, key, value)
                self._touch()
                return record

        record = {
            "id": self._next_profile_id(),
            "category": category,
            "key": key,
            "value": value,
            "status": "current",
            "source": str(source),
            "confidence": confidence,
            "explicitly_shared": bool(explicitly_shared),
            "evidence_id": evidence_id,
            "observation_id": observation_id,
            "created_at": now,
            "updated_at": now,
        }
        self.profile_records.append(record)
        self._apply_current(category, key, value)
        self._touch()
        return record

    def get_profile_records(
        self,
        *,
        category: str | None = None,
        current_only: bool = True,
        explicitly_shared_only: bool = False,
    ) -> List[Dict[str, Any]]:
        records = list(self.profile_records)
        if category is not None:
            normalized = str(category).strip().lower()
            records = [
                record for record in records
                if record.get("category") == normalized
            ]
        if current_only:
            records = [
                record for record in records
                if record.get("status") == "current"
            ]
        if explicitly_shared_only:
            records = [
                record for record in records
                if bool(record.get("explicitly_shared"))
            ]
        return records

    def current_profile(self) -> Dict[str, Any]:
        general = [
            str(item.get("value"))
            for item in self.get_profile_records(category="general")
        ]
        return {
            "identity": self.get_identity(),
            "facts": dict(self.facts),
            "preferences": dict(self.preferences),
            "interests": list(self.interests),
            "values": list(self.values),
            "goals": list(self.goals),
            "communication_style": dict(self.communication_style),
            "general": general,
            "profile_record_count": len(self.profile_records),
        }

    def _apply_current(self, category: str, key: str, value: Any) -> None:
        if category == "fact":
            self.facts[key] = value
        elif category == "preference":
            self.preferences[key] = value
        elif category == "interest":
            self._append_unique(self.interests, value)
        elif category == "value":
            self._append_unique(self.values, value)
        elif category == "goal":
            self._append_unique(self.goals, value)
        elif category == "communication":
            self.communication_style[key] = value
        elif category == "general":
            pass

    # ============================================================
    # BACKWARD-COMPATIBLE FACTS / PREFERENCES / INTERESTS / VALUES / GOALS
    # ============================================================

    def set_fact(self, key: str, value: Any) -> None:
        if not key:
            return
        self.facts[str(key)] = value
        self._touch()

    def get_fact(self, key: str, default: Any = None) -> Any:
        return self.facts.get(key, default)

    def remove_fact(self, key: str) -> bool:
        if key not in self.facts:
            return False
        del self.facts[key]
        self._touch()
        return True

    def set_preference(self, key: str, value: Any) -> None:
        if not key:
            return
        self.preferences[str(key)] = value
        self._touch()

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self.preferences.get(key, default)

    def add_interest(self, interest: str) -> bool:
        return self._add_unique(self.interests, interest)

    def remove_interest(self, interest: str) -> bool:
        return self._remove_unique(self.interests, interest)

    def add_value(self, value: str) -> bool:
        return self._add_unique(self.values, value)

    def remove_value(self, value: str) -> bool:
        return self._remove_unique(self.values, value)

    def add_goal(self, goal: str) -> bool:
        return self._add_unique(self.goals, goal)

    def remove_goal(self, goal: str) -> bool:
        return self._remove_unique(self.goals, goal)

    def set_communication_trait(self, key: str, value: Any) -> None:
        if not key:
            return
        self.communication_style[str(key)] = value
        self._touch()

    def get_communication_trait(self, key: str, default: Any = None) -> Any:
        return self.communication_style.get(key, default)

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creator_id": self.creator_id,
            "name": self.name,
            "facts": dict(self.facts),
            "preferences": dict(self.preferences),
            "interests": list(self.interests),
            "values": list(self.values),
            "goals": list(self.goals),
            "communication_style": dict(self.communication_style),
            "profile_records": list(self.profile_records),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(
        cls,
        data: Optional[Dict[str, Any]],
    ) -> "UserModel":
        if not isinstance(data, dict):
            return cls()

        model = cls(
            creator_id=data.get("creator_id", "creator"),
            name=data.get("name", "unbe"),
        )

        if isinstance(data.get("facts"), dict):
            model.facts = dict(data["facts"])
        if isinstance(data.get("preferences"), dict):
            model.preferences = dict(data["preferences"])
        if isinstance(data.get("interests"), list):
            model.interests = list(data["interests"])
        if isinstance(data.get("values"), list):
            model.values = list(data["values"])
        if isinstance(data.get("goals"), list):
            model.goals = list(data["goals"])
        if isinstance(data.get("communication_style"), dict):
            model.communication_style = dict(data["communication_style"])
        if isinstance(data.get("profile_records"), list):
            model.profile_records = [
                item for item in data["profile_records"]
                if isinstance(item, dict)
            ]

        model.created_at = data.get("created_at", model.created_at)
        model.updated_at = data.get("updated_at", model.updated_at)
        return model

    # ============================================================
    # INTERNAL
    # ============================================================

    def _add_unique(self, collection: List[str], value: str) -> bool:
        if not value:
            return False
        value = str(value).strip()
        if not value:
            return False
        if value.lower() in {str(item).lower() for item in collection}:
            return False
        collection.append(value)
        self._touch()
        return True

    def _remove_unique(self, collection: List[str], value: str) -> bool:
        if not value:
            return False
        for index, item in enumerate(collection):
            if str(item).lower() == str(value).lower():
                collection.pop(index)
                self._touch()
                return True
        return False

    @staticmethod
    def _append_unique(collection: List[str], value: Any) -> None:
        rendered = str(value).strip()
        if not rendered:
            return
        if rendered.lower() in {str(item).lower() for item in collection}:
            return
        collection.append(rendered)

    def _next_profile_id(self) -> str:
        highest = 0
        for record in self.profile_records:
            record_id = str(record.get("id", ""))
            if not record_id.startswith("profile_"):
                continue
            try:
                highest = max(highest, int(record_id.rsplit("_", 1)[-1]))
            except ValueError:
                continue
        return f"profile_{highest + 1}"

    @staticmethod
    def _clamp(value: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.5
        return max(0.0, min(1.0, number))

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _touch(self) -> None:
        self.updated_at = self._timestamp()
