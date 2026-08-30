"""MaryV2 root authority hierarchy.

This is executable documentation, not a new state database.  Its job is to make
the hierarchy every surface/model/node must obey explicit and testable.
"""
from __future__ import annotations

from typing import Any


class MaryRootAuthority:
    VERSION = "maryv2-convergence-1"

    LAYERS = (
        {
            "rank": 0,
            "name": "runtime_invariants",
            "owner": "MaryV2 repository / validated composition",
            "purpose": "Defines one-Mary ownership, boundaries, permissions, and conflict resolution.",
            "mutable_by_model": False,
        },
        {
            "rank": 1,
            "name": "authored_character",
            "owner": "creator-authored Character Core + Character Sourcebook",
            "purpose": "Who Mary is and how her character is realized across media.",
            "mutable_by_model": False,
        },
        {
            "rank": 2,
            "name": "lived_continuity",
            "owner": "memory / relationship / developed-self / agency owners",
            "purpose": "What AI Mary has actually learned, experienced, developed, or is doing now.",
            "mutable_by_model": False,
        },
        {
            "rank": 3,
            "name": "turn_context",
            "owner": "TurnMind / context lifecycle / retrieval",
            "purpose": "Smallest sufficient authoritative context for the current intention.",
            "mutable_by_model": False,
        },
        {
            "rank": 4,
            "name": "capability_fabric",
            "owner": "routers / tools / integrations / capability registry",
            "purpose": "Replaceable models, search, creative generators, files, applications, and services.",
            "mutable_by_model": False,
        },
        {
            "rank": 5,
            "name": "nodes",
            "owner": "NodeRegistry / Core device broker",
            "purpose": "Replaceable places capabilities execute: cloud, Windows, Mac, future GPU/server.",
            "mutable_by_model": False,
        },
        {
            "rank": 6,
            "name": "surfaces",
            "owner": "desktop / mobile / terminal / future performer clients",
            "purpose": "Ways the same Mary is presented and controlled.",
            "mutable_by_model": False,
        },
    )

    INVARIANTS = (
        "There is one canonical Mary per live application composition; surfaces and nodes never create competing identity owners.",
        "Language/image/video/voice models are capabilities. Their outputs are evidence or artifacts, never identity authority by themselves.",
        "Creator-authored fictional canon may inform shared character DNA but is never automatically an AI-Mary lived memory.",
        "AI-Mary continuity is written only through the subsystem that owns that kind of state.",
        "Everything may be addressable without everything being loaded into each model prompt; context is selected and bounded.",
        "Capability and permission are separate. Paid, external, destructive, publishing, and privacy-sensitive actions remain governed.",
        "Cloud, PC, Mac, phone, and future servers are habitats/capability locations, not different Mary identities.",
        "Derived indexes/caches are rebuildable and must never become the only copy of Mary's authoritative state.",
        "A failed optional capability must degrade functionality, not erase Mary's identity or continuity.",
    )

    def snapshot(self, mary: Any | None = None) -> dict[str, Any]:
        sourcebook = getattr(mary, "character_sourcebook", None) if mary is not None else None
        evaluation = getattr(mary, "character_evaluation", None) if mary is not None else None
        nodes = getattr(mary, "node_registry", None) if mary is not None else None
        return {
            "version": self.VERSION,
            "layers": [dict(item) for item in self.LAYERS],
            "invariants": list(self.INVARIANTS),
            "context_principle": "everything_addressable_not_everything_in_prompt",
            "one_mary_principle": "many_surfaces_many_nodes_one_mary",
            "character_sourcebook": (
                sourcebook.snapshot()
                if callable(getattr(sourcebook, "snapshot", None))
                else {"enabled": False}
            ),
            "character_evaluation": (
                evaluation.snapshot()
                if callable(getattr(evaluation, "snapshot", None))
                else {"enabled": False}
            ),
            "nodes": (
                nodes.snapshot()
                if callable(getattr(nodes, "snapshot", None))
                else {"registered": 0}
            ),
        }

    def validate(self, mary: Any) -> list[str]:
        issues: list[str] = []
        sourcebook = getattr(mary, "character_sourcebook", None)
        if sourcebook is None:
            issues.append("character sourcebook bridge is not installed")
        if getattr(mary, "turn_mind", None) is None:
            issues.append("TurnMind is not installed")
        elif getattr(mary.turn_mind, "character_sourcebook", None) is not sourcebook:
            issues.append("TurnMind is not sharing Mary's CharacterSourcebook")
        if getattr(mary, "llm", None) is None:
            issues.append("LLMRouter is unavailable")
        if getattr(mary, "node_registry", None) is None:
            issues.append("NodeRegistry is unavailable")
        return issues
