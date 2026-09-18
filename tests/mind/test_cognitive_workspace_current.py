from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from mary.continuity import CompetenceLedger, ExecutivePlanGraph, SkillLibrary, WorldModel
from mary.knowledge import KnowledgeFabric
from mary.mind import CognitiveWorkspace


class _Memory:
    def recall(self, query, *, limit=5):
        return [{"id": "memory_1", "content": "Creator is working on MaryV2."}]

    def status(self):
        return {"counts": {"episodic": 2, "semantic": 1, "working": 0}}


class _Sourcebook:
    sourcebook_hash = "sourcebook-test"

    def select(self, query, *, limit=5, max_characters=4200):
        record = SimpleNamespace(
            record_id="char_1",
            heading="Mary under pressure",
            text="Humor is often control under pressure.",
            labels=("DNA",),
            source_name="fixture",
            provenance="creator_authored",
        )
        return SimpleNamespace(records=(record,))


class _Nodes:
    def snapshot(self):
        return {
            "nodes": [
                {
                    "node_id": "desktop",
                    "connected": True,
                    "capabilities": {
                        "llm.ollama": {
                            "available": True,
                            "metadata": {"execution_authorized": True},
                        },
                        "knowledge.search": {
                            "available": True,
                            "metadata": {"execution_authorized": False},
                        },
                    },
                }
            ]
        }


def test_cognitive_workspace_binds_existing_authorities_without_owning_them(tmp_path: Path):
    world = WorldModel(tmp_path / "world.json")
    world.observe(
        subject="MaryV2",
        predicate="canonical_branch",
        value="main",
        source="repo",
        authority="canonical",
        verification="verified",
        confidence=1.0,
    )

    skills = SkillLibrary(tmp_path / "skills.json")
    skill = skills.register_candidate(
        name="repair MaryV2",
        description="Inspect before patching.",
        source="creator",
        required_capabilities=("llm.ollama",),
        required_permissions=("llm.ollama",),
        tags=("repair", "maryv2"),
        steps=("inspect", "propose", "verify"),
    )
    skills.approve(skill.id)

    plans = ExecutivePlanGraph(tmp_path / "plans.json")
    plans.create(
        objective="Improve MaryV2",
        source="creator",
        steps=("inspect architecture",),
        tags=("maryv2",),
    )

    knowledge = KnowledgeFabric(tmp_path / "knowledge.json")
    knowledge.seed_recommended_candidates()

    competence = CompetenceLedger(tmp_path / "competence.json")
    competence.record(
        capability="llm.ollama",
        operation="conversation",
        node_id="desktop",
        success=True,
        verified=True,
        evidence_ids=("task-1",),
    )

    mary = SimpleNamespace(
        node_registry=_Nodes(),
        memory=_Memory(),
        character_sourcebook=_Sourcebook(),
        world_model=world,
        procedural_skills=skills,
        executive_plans=plans,
        knowledge_fabric=knowledge,
        competence=competence,
        identity=SimpleNamespace(name="Mary"),
        lifecycle=SimpleNamespace(state=SimpleNamespace(value="ACTIVE")),
        self_model=SimpleNamespace(to_dict=lambda: {"entity_type": "AI character"}),
    )

    snapshot = CognitiveWorkspace(mary).build("repair MaryV2 with local ollama").to_dict()

    assert snapshot["identity"]["name"] == "Mary"
    assert snapshot["memory"]["relevant"][0]["id"] == "memory_1"
    assert snapshot["character"]["records"][0]["record_id"] == "char_1"
    assert snapshot["world"]["beliefs"][0]["predicate"] == "canonical_branch"
    assert snapshot["skills"]["eligible"][0]["name"] == "repair MaryV2"
    assert snapshot["plans"]["active"][0]["objective"] == "Improve MaryV2"
    assert snapshot["compute"]["connected_nodes"] == 1
    assert "llm.ollama" in snapshot["compute"]["authorized_capabilities"]
    assert snapshot["compute"]["demonstrated"][0]["capability"] == "llm.ollama"
    assert snapshot["compute"]["demonstrated"][0]["reliability"] == 0.6667
    assert snapshot["epistemic"]["knowledge_hits_are_evidence_not_memory"] is True
    assert snapshot["policy"]["persistent"] is False
    assert snapshot["policy"]["identity_owner"] is False
    assert snapshot["policy"]["tool_authority"] is False
    budget = snapshot["policy"]["context_budget"]
    assert budget["authority"].startswith("prompt-context budget only")
    assert budget["used_characters"] <= budget["total_budget_characters"]
    assert {row["lane"] for row in budget["lanes"]} == {
        "world", "plans", "skills", "compute", "knowledge"
    }
