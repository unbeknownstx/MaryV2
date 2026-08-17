"""
MaryV2 - Relationship Curiosity Development

Turns Mary's broad creator-directed curiosity into concrete, local knowledge gaps.

This subsystem is deliberately non-autonomous:
- it does not ask questions on its own,
- it does not browse the web,
- it does not execute tools,
- it only derives curiosity state from Mary's existing structured relationship model.

The broad creator curiosity remains the umbrella priority. Specific child
curiosities are created for unresolved relationship categories and are resolved
when Unbe explicitly shares enough information to fill that category.
"""

from __future__ import annotations

from typing import Any


class RelationshipCuriosityDevelopment:
    """Develop creator-directed relationship curiosity from structured gaps."""

    GAP_SPECS: tuple[dict[str, str], ...] = (
        {
            "category": "preferences",
            "description": "Learn more about Unbe's personal preferences",
            "question": "what personal preferences matter to Unbe",
        },
        {
            "category": "interests",
            "description": "Learn more about Unbe's interests",
            "question": "what Unbe most enjoys or is interested in",
        },
        {
            "category": "goals",
            "description": "Learn what goals matter most to Unbe",
            "question": "what goals matter most to Unbe",
        },
        {
            "category": "values",
            "description": "Learn which values matter most to Unbe",
            "question": "which values Unbe considers most important",
        },
        {
            "category": "communication",
            "description": "Learn how Unbe prefers Mary to communicate",
            "question": "how Unbe prefers Mary to communicate with him",
        },
    )

    def __init__(
        self,
        *,
        relationship: Any,
        curiosity_system: Any,
        creator_name: str = "Unbe",
    ) -> None:
        self.relationship = relationship
        self.curiosity_system = curiosity_system
        self.creator_name = str(creator_name).strip() or "Unbe"

    # ============================================================
    # PUBLIC STATE
    # ============================================================

    def knowledge_gaps(self) -> list[dict[str, Any]]:
        """Return deterministic relationship knowledge gaps from current state."""

        profile = self.relationship.profile()
        gaps: list[dict[str, Any]] = []

        for spec in self.GAP_SPECS:
            category = spec["category"]
            known = self._category_is_known(profile, category)
            gaps.append({
                "category": category,
                "description": spec["description"],
                "question": spec["question"],
                "known": known,
                "status": "resolved" if known else "unresolved",
            })

        return gaps

    def unresolved_gaps(self) -> list[dict[str, Any]]:
        return [gap for gap in self.knowledge_gaps() if not gap["known"]]

    def resolved_gaps(self) -> list[dict[str, Any]]:
        return [gap for gap in self.knowledge_gaps() if gap["known"]]

    def sync(self) -> dict[str, Any]:
        """
        Synchronize child curiosities with Mary's structured creator knowledge.

        Child curiosities are only created while an active broad creator-directed
        curiosity exists. Existing child curiosities are still resolved if their
        corresponding relationship category becomes known.
        """

        parent = self._active_parent_curiosity()
        created: list[str] = []
        resolved: list[str] = []
        changed = False

        for gap in self.knowledge_gaps():
            category = str(gap["category"])
            child = self._find_gap_curiosity(category)

            if gap["known"]:
                if child is not None and child.get("status") in {"open", "exploring"}:
                    child["resolved_by_relationship"] = True
                    child["resolved_category"] = category
                    self.curiosity_system.resolve_curiosity(str(child.get("id", "")))
                    resolved.append(category)
                    changed = True
                continue

            if parent is None:
                continue

            if child is None:
                child = self.curiosity_system.add_curiosity(
                    description=str(gap["description"]),
                    importance=0.82,
                    source="relationship_gap",
                    metadata={
                        "relationship_gap": True,
                        "gap_category": category,
                        "parent_curiosity_id": parent.get("id"),
                        "creator_name": self.creator_name,
                        "creator_directed": True,
                    },
                )
                if child is not None:
                    child["urgency"] = 0.35
                    child["relevance"] = 0.95
                    child["relationship_gap"] = True
                    child["gap_category"] = category
                    child["parent_curiosity_id"] = parent.get("id")
                    child["creator_directed"] = True
                    self.curiosity_system.save()
                    created.append(category)
                    changed = True
                continue

            if child.get("status") == "resolved":
                # A resolved child is historical proof that Mary previously filled
                # the gap. Do not reopen it automatically.
                continue

        if parent is not None:
            unresolved = self.unresolved_gaps()
            parent["relationship_gap_count"] = len(unresolved)
            parent["relationship_resolved_gap_count"] = len(self.resolved_gaps())
            parent["relationship_gap_categories"] = [
                gap["category"] for gap in unresolved
            ]
            if parent.get("status") == "open" and self.resolved_gaps():
                parent["status"] = "exploring"
            self.curiosity_system.save()
            changed = True

        return {
            "parent_curiosity_id": parent.get("id") if parent else None,
            "created": created,
            "resolved": resolved,
            "unresolved": [gap["category"] for gap in self.unresolved_gaps()],
            "changed": changed,
        }

    def answer_query(self) -> str:
        """Render Mary's specific creator-relationship curiosities locally."""

        unresolved = self.unresolved_gaps()
        resolved = self.resolved_gaps()

        if not unresolved:
            return (
                f"I don't currently have any unresolved structured relationship gaps "
                f"for {self.creator_name}. That doesn't mean I know everything about him; "
                "it only means the relationship categories I currently track have explicit information."
            )

        gap_text = "; ".join(str(item["question"]) for item in unresolved)
        response = (
            f"Based on what {self.creator_name} has explicitly shared with me, I'm still curious about: "
            f"{gap_text}."
        )

        if resolved:
            resolved_text = ", ".join(str(item["category"]) for item in resolved)
            response += f" I already have explicit information in these tracked areas: {resolved_text}."

        response += (
            " These are internal knowledge gaps, not permission for me to interrogate you, "
            "browse, or take external action on my own."
        )
        return response

    def status(self) -> dict[str, Any]:
        parent = self._active_parent_curiosity()
        gaps = self.knowledge_gaps()
        return {
            "connected": True,
            "creator_name": self.creator_name,
            "parent_curiosity_id": parent.get("id") if parent else None,
            "tracked_gap_count": len(gaps),
            "unresolved_gap_count": sum(not gap["known"] for gap in gaps),
            "resolved_gap_count": sum(gap["known"] for gap in gaps),
        }

    # ============================================================
    # INTERNAL
    # ============================================================

    def _active_parent_curiosity(self) -> dict[str, Any] | None:
        expected = f"learn more about {self.creator_name}".strip().lower()
        for curiosity in self.curiosity_system.get_curiosities():
            if curiosity.get("status") not in {"open", "exploring"}:
                continue
            description = str(curiosity.get("description", "")).strip().lower()
            if description != expected:
                continue
            if not bool(curiosity.get("creator_directed")) and curiosity.get("source") != "creator_directive":
                continue
            return curiosity
        return None

    def _find_gap_curiosity(self, category: str) -> dict[str, Any] | None:
        category = str(category).strip().lower()
        for curiosity in reversed(self.curiosity_system.get_curiosities()):
            metadata = curiosity.get("metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            gap_category = str(
                curiosity.get("gap_category")
                or metadata.get("gap_category")
                or ""
            ).strip().lower()
            relationship_gap = bool(
                curiosity.get("relationship_gap")
                or metadata.get("relationship_gap")
            )
            if relationship_gap and gap_category == category:
                return curiosity
        return None

    @staticmethod
    def _category_is_known(profile: dict[str, Any], category: str) -> bool:
        if category == "preferences":
            return bool(profile.get("preferences"))
        if category == "interests":
            return bool(profile.get("interests"))
        if category == "goals":
            return bool(profile.get("goals"))
        if category == "values":
            return bool(profile.get("values"))
        if category == "communication":
            return bool(profile.get("communication_style"))
        return False
