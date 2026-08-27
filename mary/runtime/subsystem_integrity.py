"""
MaryV2 - Subsystem Wiring Integrity

Read-only checks for Mary's internal live object graph.

The purpose of this module is deliberately narrower than feature diagnostics:
it proves that major subsystems are connected to the exact authoritative
objects they are supposed to share.

A PASS here means "wired to the correct owner", not "actively participating
in every turn". Runtime participation/activity is diagnosed separately.
"""

from __future__ import annotations

from typing import Any


def _same(
    owner: Any,
    attribute: str,
    expected: Any,
) -> bool:
    return (
        owner is not None
        and getattr(
            owner,
            attribute,
            None,
        )
        is expected
    )


def subsystem_integrity_report(
    mary: Any,
) -> dict[str, Any]:
    """
    Return a read-only wiring report for one live Mary runtime.

    The checks use object identity rather than names, serialization, or source
    formatting. They do not mutate Mary or initialize missing systems.
    """

    turn_mind = getattr(
        mary,
        "turn_mind",
        None,
    )
    self_introspection = getattr(
        mary,
        "self_introspection",
        None,
    )
    relationship_curiosity = getattr(
        mary,
        "relationship_curiosity",
        None,
    )
    conversation_learning = getattr(
        mary,
        "conversation_learning",
        None,
    )
    cognition = getattr(
        mary,
        "cognition",
        None,
    )
    reasoning = getattr(
        mary,
        "reasoning",
        None,
    )
    reflection = getattr(
        mary,
        "reflection",
        None,
    )
    runtime_environment = getattr(
        mary,
        "runtime_environment",
        None,
    )
    perception = getattr(
        mary,
        "perception_director",
        None,
    )
    realtime = getattr(
        mary,
        "realtime",
        None,
    )
    avatar = getattr(
        mary,
        "avatar",
        None,
    )
    growth = getattr(
        mary,
        "growth",
        None,
    )
    mind = getattr(
        mary,
        "mind",
        None,
    )
    knowledge_learning = getattr(
        mary,
        "knowledge_learning",
        None,
    )
    knowledge_state = getattr(
        mary,
        "knowledge_state",
        None,
    )

    checks = {
        # ------------------------------------------------------------
        # TurnMind receives the authoritative Mary subsystems.
        # ------------------------------------------------------------
        "turn_mind.identity": _same(
            turn_mind,
            "identity",
            getattr(mary, "identity", None),
        ),
        "turn_mind.self_model": _same(
            turn_mind,
            "self_model",
            getattr(mary, "self_model", None),
        ),
        "turn_mind.biography": _same(
            turn_mind,
            "biography",
            getattr(mary, "biography", None),
        ),
        "turn_mind.personality": _same(
            turn_mind,
            "personality",
            getattr(mary, "personality", None),
        ),
        "turn_mind.character": _same(
            turn_mind,
            "character",
            getattr(mary, "character", None),
        ),
        "turn_mind.values": _same(
            turn_mind,
            "values",
            getattr(mary, "values", None),
        ),
        "turn_mind.preferences": _same(
            turn_mind,
            "preferences",
            getattr(mary, "preferences", None),
        ),
        "turn_mind.self_provenance": _same(
            turn_mind,
            "self_provenance",
            getattr(mary, "self_provenance", None),
        ),
        "turn_mind.relationship": _same(
            turn_mind,
            "relationship",
            getattr(mary, "relationship", None),
        ),
        "turn_mind.knowledge": _same(
            turn_mind,
            "knowledge",
            getattr(mary, "knowledge", None),
        ),
        "turn_mind.learner": _same(
            turn_mind,
            "learner",
            getattr(mary, "learner", None),
        ),
        "turn_mind.agency": _same(
            turn_mind,
            "agency",
            getattr(mary, "agency", None),
        ),
        "agency.decisions_share_priorities": (
            getattr(
                getattr(
                    getattr(
                        mary,
                        "agency",
                        None,
                    ),
                    "decisions",
                    None,
                ),
                "priority_system",
                None,
            )
            is getattr(
                getattr(
                    mary,
                    "agency",
                    None,
                ),
                "priorities",
                None,
            )
        ),
        "turn_mind.autonomy": _same(
            turn_mind,
            "autonomy",
            getattr(mary, "autonomy", None),
        ),
        "turn_mind.tools": _same(
            turn_mind,
            "tools",
            getattr(mary, "tools", None),
        ),
        "turn_mind.emotion": _same(
            turn_mind,
            "emotion",
            getattr(mary, "emotion", None),
        ),
        "turn_mind.dialogue": _same(
            turn_mind,
            "dialogue",
            getattr(mary, "dialogue", None),
        ),
        "continuity.shared_with_turn_mind": (
            getattr(
                mary,
                "continuity",
                None,
            )
            is getattr(
                turn_mind,
                "continuity",
                None,
            )
        ),
        "performance.shared_with_turn_mind": (
            getattr(
                mary,
                "performance",
                None,
            )
            is getattr(
                turn_mind,
                "performance",
                None,
            )
        ),

        # ------------------------------------------------------------
        # Relationship learning uses the authoritative relationship /
        # agency-curiosity objects rather than parallel copies.
        # ------------------------------------------------------------
        "relationship_curiosity.relationship": _same(
            relationship_curiosity,
            "relationship",
            getattr(mary, "relationship", None),
        ),
        "relationship_curiosity.curiosities": _same(
            relationship_curiosity,
            "curiosity_system",
            getattr(
                getattr(mary, "agency", None),
                "curiosities",
                None,
            ),
        ),
        "conversation_learning.relationship_curiosity": _same(
            conversation_learning,
            "relationship_curiosity",
            relationship_curiosity,
        ),

        # ------------------------------------------------------------
        # Self-introspection reads Mary's authoritative self systems.
        # ------------------------------------------------------------
        "self_introspection.identity": _same(
            self_introspection,
            "identity",
            getattr(mary, "identity", None),
        ),
        "self_introspection.self_model": _same(
            self_introspection,
            "self_model",
            getattr(mary, "self_model", None),
        ),
        "self_introspection.biography": _same(
            self_introspection,
            "biography",
            getattr(mary, "biography", None),
        ),
        "self_introspection.personality": _same(
            self_introspection,
            "personality",
            getattr(mary, "personality", None),
        ),
        "self_introspection.values": _same(
            self_introspection,
            "values",
            getattr(mary, "values", None),
        ),
        "self_introspection.preferences": _same(
            self_introspection,
            "preferences",
            getattr(mary, "preferences", None),
        ),
        "self_introspection.character": _same(
            self_introspection,
            "character",
            getattr(mary, "character", None),
        ),
        "self_introspection.user_model": _same(
            self_introspection,
            "user_model",
            getattr(mary, "user_model", None),
        ),
        "self_introspection.creator_directives": _same(
            self_introspection,
            "creator_directives",
            getattr(mary, "creator_directives", None),
        ),
        "self_introspection.agency": _same(
            self_introspection,
            "agency",
            getattr(mary, "agency", None),
        ),
        "self_introspection.autonomy": _same(
            self_introspection,
            "autonomy",
            getattr(mary, "autonomy", None),
        ),
        "self_introspection.tools": _same(
            self_introspection,
            "tools",
            getattr(mary, "tools", None),
        ),
        "self_introspection.emotion": _same(
            self_introspection,
            "emotion",
            getattr(mary, "emotion", None),
        ),

        # ------------------------------------------------------------
        # Cognition and provider routing share the configured live engines.
        # ------------------------------------------------------------
        "cognition.reasoning_engine": _same(
            cognition,
            "reasoning_engine",
            reasoning,
        ),
        "cognition.reflection_engine": _same(
            cognition,
            "reflection_engine",
            reflection,
        ),
        "reasoning.llm": _same(
            reasoning,
            "llm",
            getattr(mary, "llm", None),
        ),
        "reflection.llm": _same(
            reflection,
            "llm",
            getattr(mary, "llm", None),
        ),
        "runtime_environment.router": _same(
            runtime_environment,
            "router",
            getattr(mary, "llm", None),
        ),

        # ------------------------------------------------------------
        # Learning/knowledge uses the same candidate, learner, and durable
        # knowledge owners instead of parallel stores.
        # ------------------------------------------------------------
        "knowledge_learning.candidates": _same(
            knowledge_learning,
            "candidates",
            getattr(mary, "learning_knowledge", None),
        ),
        "knowledge_learning.knowledge": _same(
            knowledge_learning,
            "knowledge",
            getattr(mary, "knowledge", None),
        ),
        "knowledge_learning.learner": _same(
            knowledge_learning,
            "learner",
            getattr(mary, "learner", None),
        ),
        "knowledge_state.candidates": _same(
            knowledge_state,
            "candidates",
            getattr(mary, "learning_knowledge", None),
        ),
        "knowledge_state.knowledge": _same(
            knowledge_state,
            "knowledge",
            getattr(mary, "knowledge", None),
        ),

        # ------------------------------------------------------------
        # Supporting runtime systems remain attached to this Mary.
        # ------------------------------------------------------------
        "growth.mary": _same(
            growth,
            "mary",
            mary,
        ),
        "character_mind.mary": _same(
            mind,
            "mary",
            mary,
        ),
        "perception.realtime_attention": (
            perception is not None
            and realtime is not None
            and getattr(
                perception,
                "attention",
                None,
            )
            is getattr(
                realtime,
                "attention",
                None,
            )
        ),
        "avatar.emotion": _same(
            avatar,
            "emotion_manager",
            getattr(mary, "emotion", None),
        ),
    }

    failed = [
        name
        for name, passed in checks.items()
        if not passed
    ]

    groups = {
        "turn_mind": [
            name
            for name in checks
            if name.startswith("turn_mind.")
            or name.startswith("continuity.")
            or name.startswith("performance.")
        ],
        "relationship_learning": [
            name
            for name in checks
            if name.startswith("relationship_curiosity.")
            or name.startswith("conversation_learning.")
        ],
        "agency": [
            name
            for name in checks
            if name.startswith("agency.")
        ],
        "self_introspection": [
            name
            for name in checks
            if name.startswith("self_introspection.")
        ],
        "cognition_routing": [
            name
            for name in checks
            if name.startswith("cognition.")
            or name.startswith("reasoning.")
            or name.startswith("reflection.")
            or name.startswith("runtime_environment.")
        ],
        "learning_knowledge": [
            name
            for name in checks
            if name.startswith("knowledge_learning.")
            or name.startswith("knowledge_state.")
        ],
        "supporting_runtime": [
            name
            for name in checks
            if name.startswith("growth.")
            or name.startswith("character_mind.")
            or name.startswith("perception.")
            or name.startswith("avatar.")
        ],
    }

    group_status = {
        group: all(
            checks[name]
            for name in names
        )
        for group, names in groups.items()
    }

    return {
        "ok": not failed,
        "checks": checks,
        "failed": failed,
        "groups": group_status,
        "checked": len(checks),
        "note": (
            "Wiring integrity proves shared authoritative objects only. "
            "It does not claim that a subsystem is active on every turn."
        ),
    }


def require_subsystem_integrity(
    mary: Any,
) -> dict[str, Any]:
    """
    Return the wiring report or raise if Mary's live graph has split.
    """

    report = subsystem_integrity_report(
        mary
    )

    if not report["ok"]:
        raise RuntimeError(
            "Mary subsystem wiring integrity failed: "
            + ", ".join(
                report["failed"]
            )
        )

    return report
