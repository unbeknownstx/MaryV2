"""
MaryV2 - Relationship Manager

Persistent coordinator for Mary's structured understanding of Unbe.

Memory remains the record of what was said or experienced.  The relationship
manager maintains a current, source-aware creator model derived only from
explicitly shared, high-confidence information.  Inferences stay separate and
are never silently promoted to facts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .history import RelationshipHistory
from .milestones import MilestoneManager
from .understanding import RelationshipUnderstanding
from .user import UserModel


class RelationshipManager:
    """Own and persist Mary's relationship state for her creator."""

    def __init__(
        self,
        path: str | Path = "data/relationship/relationship.json",
        *,
        creator_id: str = "creator",
        creator_name: str = "unbe",
    ) -> None:
        self.path = Path(path)
        self.user_model = UserModel(
            creator_id=creator_id,
            name=creator_name,
        )
        self.history = RelationshipHistory(
            creator_id=creator_id,
        )
        self.understanding = RelationshipUnderstanding(
            user_model=self.user_model,
            history=self.history,
        )
        self.milestones = MilestoneManager()

    # ============================================================
    # LIFECYCLE
    # ============================================================

    def load(self) -> None:
        """Load relationship state if present, otherwise create a clean file."""

        if not self.path.exists():
            self.save()
            return

        try:
            with self.path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return

        if not isinstance(payload, dict):
            return

        self.user_model = UserModel.from_dict(
            payload.get("user_model")
        )
        self.history = RelationshipHistory.from_dict(
            payload.get("history")
        )
        self.understanding = RelationshipUnderstanding.from_dict(
            payload.get("understanding"),
            user_model=self.user_model,
            history=self.history,
        )

        milestones = payload.get("milestones", [])
        self.milestones = MilestoneManager(
            milestones if isinstance(milestones, list) else []
        )

    def save(self) -> None:
        """Atomically persist all relationship state."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 2,
            "user_model": self.user_model.to_dict(),
            "history": self.history.to_dict(),
            "understanding": self.understanding.to_dict(),
            "milestones": self.milestones.export(),
        }

        temporary = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(
                payload,
                file,
                indent=2,
                ensure_ascii=False,
            )
        temporary.replace(self.path)

    # ============================================================
    # EXPLICIT CREATOR SHARING
    # ============================================================

    def learn_explicit(
        self,
        content: str,
        *,
        source: str = "creator_explicit",
        evidence_id: str | None = None,
        force_general: bool = False,
    ) -> dict[str, Any] | None:
        """
        Learn a high-confidence creator statement into structured relationship state.

        The parser is intentionally narrow.  If the statement does not match an
        explicit creator-profile form, it stays ordinary memory unless
        ``force_general`` was explicitly requested through a relationship-share
        command such as ``learn this about me: ...``.
        """

        content = str(content).strip()
        if not content:
            return None

        if evidence_id:
            for existing in self.user_model.get_profile_records(current_only=False):
                if existing.get("evidence_id") == evidence_id:
                    return {
                        "category": existing.get("category"),
                        "key": existing.get("key"),
                        "value": existing.get("value"),
                        "label": str(existing.get("category", "profile item")),
                        "profile_record": existing,
                        "observation": None,
                        "already_known": True,
                    }

        parsed = self._parse_explicit_profile_statement(content)
        if parsed is None and not force_general:
            return None

        if parsed is None:
            parsed = {
                "category": "general",
                "key": self._general_key(content),
                "value": content,
                "label": "explicit statement",
            }

        category = parsed["category"]
        key = parsed["key"]
        value = parsed["value"]

        observation = self.understanding.add_observation(
            content,
            category=category,
            source=source,
            confidence=1.0,
            evidence=evidence_id or content,
        )

        record = self.user_model.record_profile(
            category=category,
            key=key,
            value=value,
            source=source,
            confidence=1.0,
            explicitly_shared=True,
            evidence_id=evidence_id,
            observation_id=observation.get("id"),
        )

        self.history.record(
            "creator_information_shared",
            f"Unbe explicitly shared {parsed['label']}: {value}",
            importance=0.7,
            source="relationship_understanding",
            metadata={
                "category": category,
                "key": key,
                "profile_record_id": record.get("id"),
                "evidence_id": evidence_id,
            },
        )

        self.save()

        return {
            "category": category,
            "key": key,
            "value": value,
            "label": parsed["label"],
            "profile_record": record,
            "observation": observation,
        }

    # ============================================================
    # READ / QUERY
    # ============================================================

    def profile(self) -> dict[str, Any]:
        """Return Mary's current structured understanding of Unbe."""

        return self.user_model.current_profile()

    def answer_query(self, query_type: str = "overview") -> str:
        """Render a deterministic relationship-model answer."""

        query_type = str(query_type).strip().lower() or "overview"
        profile = self.user_model.current_profile()
        creator_name = str(
            profile.get("identity", {}).get("name", "unbe")
        ).title()

        if query_type == "interests":
            items = profile.get("interests", [])
            if not items:
                return f"I don't have any explicitly shared interests stored for {creator_name} yet."
            return f"The interests {creator_name} has explicitly shared with me are: " + "; ".join(items)

        if query_type == "goals":
            items = profile.get("goals", [])
            if not items:
                return f"I don't have any explicitly shared goals stored for {creator_name} yet."
            return f"The goals {creator_name} has explicitly shared with me are: " + "; ".join(items)

        if query_type == "values":
            items = profile.get("values", [])
            if not items:
                return f"I don't have any explicitly shared creator values stored for {creator_name} yet."
            return f"The values {creator_name} has explicitly shared with me are: " + "; ".join(items)

        if query_type == "preferences":
            items = profile.get("preferences", {})
            if not items:
                return f"I don't have any explicitly shared preferences stored for {creator_name} yet."
            rendered = "; ".join(
                f"{self._readable_key(key)} = {value}"
                for key, value in items.items()
            )
            return f"The current preferences {creator_name} has explicitly shared with me are: {rendered}"

        if query_type == "history":
            records = self.user_model.get_profile_records(
                current_only=False,
            )
            if not records:
                return f"I don't have any structured relationship history about {creator_name} yet."
            rendered = "; ".join(
                f"{item.get('category')}: {item.get('value')} ({item.get('status')})"
                for item in records[-10:]
            )
            return f"My recent structured relationship history for {creator_name} is: {rendered}"

        sections: list[str] = []
        preferences = profile.get("preferences", {})
        interests = profile.get("interests", [])
        values = profile.get("values", [])
        goals = profile.get("goals", [])
        facts = profile.get("facts", {})
        general = profile.get("general", [])

        if preferences:
            sections.append(
                "preferences: " + ", ".join(
                    f"{self._readable_key(key)} = {value}"
                    for key, value in preferences.items()
                )
            )
        if interests:
            sections.append("interests: " + ", ".join(interests))
        if values:
            sections.append("values: " + ", ".join(values))
        if goals:
            sections.append("goals: " + ", ".join(goals))
        if facts:
            sections.append(
                "facts: " + ", ".join(
                    f"{self._readable_key(key)} = {value}"
                    for key, value in facts.items()
                )
            )
        if general:
            sections.append("other explicitly shared information: " + "; ".join(general))

        if not sections:
            return (
                f"I know {creator_name} is my creator, but my structured creator model "
                "doesn't contain any additional explicitly shared profile information yet."
            )

        return (
            f"My current structured understanding of {creator_name} is based on "
            "information he explicitly shared with me. "
            + " | ".join(sections)
        )

    def summary(self) -> dict[str, Any]:
        return {
            "profile": self.user_model.current_profile(),
            "understanding": self.understanding.summary(),
            "history": self.history.summary(),
            "milestones": len(self.milestones.get_milestones()),
        }

    # ============================================================
    # PARSING
    # ============================================================

    @classmethod
    def _parse_explicit_profile_statement(
        cls,
        content: str,
    ) -> dict[str, str] | None:
        text = re.sub(r"\s+", " ", content.strip())
        lowered = text.lower().rstrip(".!?")

        favorite = re.fullmatch(
            r"my favou?rite ([a-z0-9 _-]+?) is (.+)",
            lowered,
        )
        if favorite:
            subject = favorite.group(1).strip()
            value = cls._original_tail(text, favorite.group(2))
            return {
                "category": "preference",
                "key": f"favorite_{cls._slug(subject)}",
                "value": value,
                "label": f"favorite {subject}",
            }

        interest_patterns = (
            r"i love (.+)",
            r"i enjoy (.+)",
            r"i am interested in (.+)",
            r"i'm interested in (.+)",
        )
        for pattern in interest_patterns:
            match = re.fullmatch(pattern, lowered)
            if match:
                value = cls._original_tail(text, match.group(1))
                return {
                    "category": "interest",
                    "key": cls._slug(value),
                    "value": value,
                    "label": "interest",
                }

        goal_patterns = (
            r"my goal is (.+)",
            r"my main goal is (.+)",
            r"one of my goals is (.+)",
        )
        for pattern in goal_patterns:
            match = re.fullmatch(pattern, lowered)
            if match:
                value = cls._original_tail(text, match.group(1))
                return {
                    "category": "goal",
                    "key": cls._slug(value),
                    "value": value,
                    "label": "goal",
                }

        communication_patterns = (
            r"my communication preference is (.+)",
            r"i prefer you to (.+)",
            r"i prefer when you (.+)",
        )
        for pattern in communication_patterns:
            match = re.fullmatch(pattern, lowered)
            if match:
                value = cls._original_tail(text, match.group(1))
                return {
                    "category": "communication",
                    "key": "preferred_style",
                    "value": value,
                    "label": "communication preference",
                }

        value_match = re.fullmatch(r"i value (.+)", lowered)
        if value_match:
            value = cls._original_tail(text, value_match.group(1))
            return {
                "category": "value",
                "key": cls._slug(value),
                "value": value,
                "label": "value",
            }

        generic_fact = re.fullmatch(
            r"my ([a-z0-9 _-]+?) is (.+)",
            lowered,
        )
        if generic_fact:
            subject = generic_fact.group(1).strip()
            value = cls._original_tail(text, generic_fact.group(2))
            return {
                "category": "fact",
                "key": cls._slug(subject),
                "value": value,
                "label": subject,
            }

        fact_match = re.fullmatch(r"fact about me:\s*(.+)", lowered)
        if fact_match:
            value = cls._original_tail(text, fact_match.group(1))
            return {
                "category": "fact",
                "key": cls._general_key(value),
                "value": value,
                "label": "fact",
            }

        return None

    @staticmethod
    def _original_tail(original: str, lowered_value: str) -> str:
        """Return clean display text while keeping deterministic parsing simple."""
        value = str(lowered_value).strip().rstrip(".!?")
        # Preserve original capitalization when the same tail can be found.
        index = original.lower().rfind(value.lower())
        if index >= 0:
            return original[index:].strip().rstrip(".!?")
        return value

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_") or "item"

    @classmethod
    def _general_key(cls, value: str) -> str:
        return "statement_" + cls._slug(value)[:64]

    @staticmethod
    def _readable_key(key: str) -> str:
        return str(key).replace("_", " ").strip()
