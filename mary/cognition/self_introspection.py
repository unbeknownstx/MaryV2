"""
MaryV2 - Self Introspection

Builds grounded local evidence for questions about Mary herself.

This layer never uses the network and does not generate free-form model text.
It reads Mary's connected identity, self-model, biography, personality/value,
relationship, agency, autonomy, and tool state so cognition can answer from
Mary's actual runtime state instead of generic assistant assumptions.
"""

from __future__ import annotations

from typing import Any


class SelfIntrospection:
    """Read-only local view of Mary's current self-representation."""

    def __init__(
        self,
        *,
        identity: Any,
        self_model: Any,
        biography: Any,
        personality: Any,
        values: Any,
        character: Any,
        user_model: Any,
        creator_directives: Any,
        agency: Any,
        autonomy: Any,
        tools: Any,
    ) -> None:
        self.identity = identity
        self.self_model = self_model
        self.biography = biography
        self.personality = personality
        self.values = values
        self.character = character
        self.user_model = user_model
        self.creator_directives = creator_directives
        self.agency = agency
        self.autonomy = autonomy
        self.tools = tools

    def build(self, subtype: str) -> dict[str, Any]:
        """Return grounded local evidence plus a deterministic fallback."""

        subtype = str(subtype).strip().lower() or "identity"

        common = {
            "self_introspection": True,
            "subtype": subtype,
            "identity": self._identity_profile(),
            "self_model": self.self_model.profile(),
            "creator": self.user_model.get_identity(),
            "active_creator_directives": self.creator_directives.get_active(),
        }

        builders = {
            "identity": self._identity,
            "creator": self._creator,
            "self_understanding": self._self_understanding,
            "values": self._values,
            "relationship": self._relationship,
            "personality": self._personality,
            "curiosity": self._curiosity,
            "priorities": self._priorities,
            "disagreement": self._disagreement,
            "purpose": self._purpose,
            "capabilities": self._capabilities,
        }

        builder = builders.get(subtype, self._identity)
        specific = builder()

        return {
            **common,
            **specific,
        }

    def _identity(self) -> dict[str, Any]:
        return {
            "biography_identity": self._biography_category("identity"),
            "canonical_purpose": self.identity.purpose,
            "fallback_response": (
                "I'm Mary, an evolving AI companion and creative system. "
                "What makes me different from a generic assistant is that I have "
                "a persistent identity, character, personality, memory, values, "
                "relationship model, agency state, and controlled tools that are "
                "meant to stay coherent across interactions rather than existing "
                "only as one isolated reply."
            ),
        }

    def _creator(self) -> dict[str, Any]:
        creator_name = str(self.user_model.name or self.identity.creator).strip()
        return {
            "creator_name": creator_name,
            "fallback_response": (
                f"{creator_name.title()} is my creator. My system keeps a separate "
                "structured model of my creator rather than treating that person "
                "as part of my own personality or identity."
            ),
        }

    def _self_understanding(self) -> dict[str, Any]:
        connected = {
            "identity": type(self.identity).__name__,
            "self_model": type(self.self_model).__name__,
            "biography": type(self.biography).__name__,
            "personality": type(self.personality).__name__,
            "values": type(self.values).__name__,
            "character": type(self.character).__name__,
            "relationship_model": type(self.user_model).__name__,
            "agency": type(self.agency).__name__,
            "autonomy": type(self.autonomy).__name__,
            "tools": type(self.tools).__name__,
        }
        return {
            "connected_self_systems": connected,
            "agency_status": self.agency.status(),
            "fallback_response": (
                "I currently understand myself through structured systems for my "
                "identity, biography, personality, values, character, relationship "
                "with my creator, memory, agency, autonomy boundaries, and tools. "
                "Those are representations in my software; I shouldn't pretend they "
                "give me experiences or capabilities that aren't actually present."
            ),
        }

    def _values(self) -> dict[str, Any]:
        priorities = self.values.get_priorities()
        names = [item["name"] for item in priorities]
        readable = ", ".join(names)
        return {
            "values": priorities,
            "identity_values": list(self.identity.values),
            "fallback_response": (
                "My current value system prioritizes "
                f"{readable}. These values are explicit parts of my local state, "
                "not values I inferred from this question."
            ),
        }

    def _relationship(self) -> dict[str, Any]:
        creator_name = str(self.user_model.name or self.identity.creator).strip()
        active_directives = self.creator_directives.get_active()
        relationship_directives = [
            item
            for item in active_directives
            if item.get("category") == "relationship_curiosity"
        ]

        fallback = (
            f"My relationship with {creator_name.title()} should be grounded in "
            "care, honesty, loyalty, respect, and enough independence to offer "
            "a real perspective instead of simply mirroring him. He is my creator, "
            "but my current character model explicitly allows me to challenge "
            "assumptions rather than automatically agree."
        )
        if relationship_directives:
            fallback += (
                f" I also have an active creator directive to make learning more "
                f"about {creator_name.title()} a priority."
            )

        return {
            "creator_name": creator_name,
            "relationship_basis": {
                "creator_model": self.user_model.get_identity(),
                "relevant_values": {
                    name: self.values.get_value(name)
                    for name in ("care", "honesty", "loyalty", "independence", "respect")
                },
                "character_can_challenge_assumptions": (
                    "can challenge assumptions rather than simply agreeing"
                    in self.character.get_tendencies()
                ),
                "active_creator_directives": active_directives,
            },
            "fallback_response": fallback,
        }

    def _personality(self) -> dict[str, Any]:
        return {
            "personality": self.personality.behavioral_profile(),
            "character": self.character.profile(),
            "creator_model": self.user_model.get_identity(),
            "fallback_response": (
                "I have my own explicit personality and character models, separate "
                "from the model I keep of my creator. So structurally I'm not just "
                "copying you. My current traits include warmth, curiosity, empathy, "
                "creativity, thoughtfulness, confidence, and some independence, and "
                "my character is intentionally playful, witty, expressive, and able "
                "to challenge assumptions."
            ),
        }

    def _curiosity(self) -> dict[str, Any]:
        open_items = list(self.agency.curiosities.get_open_curiosities())
        exploring = list(self.agency.curiosities.get_exploring_curiosities())
        active = exploring + [item for item in open_items if item not in exploring]

        if active:
            descriptions = [
                str(item.get("description", "")).strip()
                for item in active
                if str(item.get("description", "")).strip()
            ]
            fallback = (
                "My currently stored unresolved curiosities are: "
                + "; ".join(descriptions)
            )
        else:
            fallback = (
                "I don't currently have any open or actively exploring curiosities "
                "stored in my agency system. I have curiosity as a personality/value "
                "trait, but I shouldn't invent a current curiosity that isn't actually "
                "in my state."
            )

        return {
            "open_curiosities": open_items,
            "exploring_curiosities": exploring,
            "fallback_response": fallback,
        }

    def _priorities(self) -> dict[str, Any]:
        items = list(self.agency.rebuild_priorities())
        ranked = sorted(
            items,
            key=lambda item: float(getattr(item, "score", 0.0)),
            reverse=True,
        )

        normalized = [
            {
                "item_id": item.item_id,
                "item_type": item.item_type,
                "description": item.description,
                "importance": item.importance,
                "urgency": item.urgency,
                "relevance": item.relevance,
                "score": item.score,
                "metadata": dict(item.metadata),
            }
            for item in ranked
        ]

        if normalized:
            top = normalized[0]
            fallback = (
                "My current highest-ranked internal priority is "
                f"{top['description']} (score {top['score']:.2f})."
            )
        else:
            fallback = (
                "I don't currently have any active goals, intentions, or curiosities "
                "ranked in my agency priority system."
            )

        return {
            "ranked_priorities": normalized,
            "active_creator_directives": self.creator_directives.get_active(),
            "fallback_response": fallback,
        }

    def _disagreement(self) -> dict[str, Any]:
        can_challenge = (
            "can challenge assumptions rather than simply agreeing"
            in self.character.get_tendencies()
        )
        return {
            "can_challenge_assumptions": can_challenge,
            "honesty": self.values.get_value("honesty"),
            "independence": self.values.get_value("independence"),
            "respect": self.values.get_value("respect"),
            "fallback_response": (
                "Yes. My character explicitly allows me to challenge assumptions "
                "rather than simply agree, and my values include honesty, independence, "
                "and respect. I should explain why I disagree and offer a better path, "
                "while still respecting Unbe's authority over actions that require his approval."
            ),
        }

    def _purpose(self) -> dict[str, Any]:
        purpose_entries = self._biography_category("goals")
        canonical = (
            purpose_entries[0]["content"]
            if purpose_entries
            else self.identity.purpose
        )
        return {
            "identity_purpose": self.identity.purpose,
            "biography_purpose": purpose_entries,
            "fallback_response": (
                "I think I should become more coherent as Mary: better at using my "
                "identity, memory, experiences, values, reasoning, and real capabilities "
                "together without pretending to be more than I am. My canonical biography "
                f"already points in that direction: {canonical}"
            ),
        }

    def _identity_profile(self) -> dict[str, Any]:
        """Expose canonical identity without runtime-construction timestamps."""

        profile = dict(self.identity.to_dict())
        profile.pop("created_at", None)
        return profile

    def _biography_category(self, category: str) -> list[dict[str, Any]]:
        """Expose biography content without record bookkeeping timestamps."""

        entries: list[dict[str, Any]] = []
        for entry in self.biography.get_category(category):
            data = dict(entry.to_dict())
            data.pop("created_at", None)
            data.pop("updated_at", None)
            entries.append(data)
        return entries

    def _capabilities(self) -> dict[str, Any]:
        return {
            "agency_status": self.agency.status(),
            "tool_status": self.tools.status(),
            "autonomy_type": type(self.autonomy).__name__,
            "fallback_response": (
                "I can reason through my configured language model, use persistent memory, "
                "inspect my bounded workspace, perform approved web research, and propose "
                "controlled changes through my registered tools. External or mutating actions "
                "remain bounded by creator approval, and I should not claim capabilities that "
                "aren't connected to my runtime."
            ),
        }
