from types import SimpleNamespace
from mary.runtime.system_fabric import build_system_fabric_projection

class _Owner:
    def __init__(self, payload): self.payload = payload
    def status(self): return dict(self.payload)
    def snapshot(self): return dict(self.payload)
    def capability_evidence(self): return dict(self.payload)

def test_system_fabric_projection_is_structural_and_authority_safe():
    continuity = _Owner({"world_model":{"current_beliefs":3,"reconciliation_groups":2},"temporal":{"relations":4,"current":2},"experience":{"records":5},"replay":{"lessons":1},"skills":{"approved":2,"candidates":1,"revision_attention":1,"revision_candidates":1},"plans":{"active_plans":1},"workflows":{},"verification":{},"competence":{"records":7}})
    mary = SimpleNamespace(
        experiential_continuity=continuity,
        knowledge_fabric=_Owner({"packs":2,"enabled":1,"indexed_documents":9}),
        node_registry=_Owner({"registered":1,"connected":1,"nodes":[]}),
        training_feedback=_Owner({"records":4}),
        character_evaluation=_Owner({"cases":12}),
        self_introspection=_Owner({
            "procedural_memory": {
                "demonstrated": 2,
                "degrading": 1,
                "procedures": [
                    {"skill_id": "skill-a", "evidence_needed": ["more outcomes"]},
                    {"skill_id": "skill-b", "evidence_needed": ["review failures", "compare revision"]},
                ],
            },
            "capability_improvement": {
                "knowledge.search": {"evidence_needed": ["one verified success"]},
            },
            "model_experiments": {"count": 1, "trial_ready": 1},
        }),
        model_experiments=_Owner({
            "version": 4,
            "count": 1,
            "trial_ready": 1,
            "event_count": 2,
            "records": [{
                "id": "model_exp_shared",
                "status": "benchmarked",
                "candidate_id": "mary-light",
                "runtime": "mlx_lm",
                "model": "mlx-community/Qwen3-1.7B-4bit",
                "node_id": "mac-m1",
                "mary_fit": 0.91,
                "benchmark_verified": True,
                "trial_ready": True,
            }],
            "recent_events": [],
        }),
    )
    ecosystem = SimpleNamespace(
        adapter_lab=_Owner({"configurations": [], "evaluations": []}),
        model_candidates=_Owner({"version":"2","count":1,"candidates":[{"id":"candidate-a","kind":"base_model","runtime":"llama.cpp","roles":["conversation"],"license":"Apache-2.0","repository":"do-not-project","filename":"do-not-project.gguf"}]}),
        presence=SimpleNamespace(scene=_Owner({
            "mode": "companion",
            "activity": "PRIVATE CURRENT ACTIVITY",
            "project": "PRIVATE PROJECT NAME",
            "workspace": "PRIVATE WORKSPACE",
            "selected_asset": "PRIVATE FILE PATH",
            "floor_owner": "creator",
            "realtime_phase": "listening",
            "mary_target": "PRIVATE PERSON",
            "mary_goal": "PRIVATE GOAL",
            "participants": {"creator": {}, "mary": {}},
            "recent_events": [{"summary": "PRIVATE EVENT"}],
            "updated_at": "2026-09-21T04:00:00+00:00",
        })),
    )
    result = build_system_fabric_projection(SimpleNamespace(mary=mary, ecosystem=ecosystem))
    assert result["knowledge"]["indexed_documents"] == 9
    assert result["world"]["temporal"]["current"] == 2
    assert result["continuity"]["skills"]["approved"] == 2
    assert result["continuity"]["procedure_review"]["revision_attention"] == 1
    assert result["world"]["review"]["reconciliation_groups"] == 2
    assert result["models"]["candidates"]["count"] == 1
    assert result["models"]["experiments"]["count"] == 1
    assert result["models"]["experiments"]["trial_ready"] == 1
    assert result["models"]["experiments"]["records"][0]["id"] == "model_exp_shared"
    assert "repository" not in result["models"]["candidates"]["candidates"][0]
    assert result["authority"]["execution_permission"] is False
    assert result["authority"]["promotion_permission"] is False
    assert result["compute"]["node_intelligence"]["registered"] == 1
    assert result["compute"]["node_intelligence"]["execution_permission_granted"] is False
    assert result["intelligence_loop"]["terminal_outcomes_feed_competence"] is True
    assert result["intelligence_loop"]["evidence_selected_dispatch_supported"] is True
    assert result["intelligence_loop"]["demonstrated_procedures"] == 2
    assert result["intelligence_loop"]["degrading_procedures"] == 1
    assert result["intelligence_loop"]["procedure_evidence_gaps"] == 3
    assert result["intelligence_loop"]["capability_evidence_gaps"] == 1
    assert result["intelligence_loop"]["automatic_permission"] is False
    assert result["semantics"]["procedure_selection"] == "approved_demonstrated_non_degrading_ephemeral_only"
    assert result["semantics"]["node_intelligence"].startswith("advertisement_readiness")

    assert result["compute"]["capability_contract"]["capabilities"][0]["capability"] == "knowledge.search"
    assert result["compute"]["capability_contract"]["evidence_gaps"] == 1
    assert result["knowledge"]["evaluation_readiness"]["enabled_packs"] == 1
    assert result["knowledge"]["evaluation_readiness"]["indexed_chunks"] == 9
    assert result["knowledge"]["evaluation_readiness"]["deterministic_evaluator"] == "KnowledgeFabricEvaluator"
    assert result["knowledge"]["evaluation_readiness"]["automatic_rebuild"] is False
    assert result["embodiment"]["canonical_score"] == "PerformancePacket"
    assert result["embodiment"]["one_character_many_bodies"] is True
    assert result["embodiment"]["body_identity_authority"] is False
    assert result["embodiment"]["surfaces"]["desktop"]["semantic_motion"] is True
    assert result["embodiment"]["surfaces"]["ios_native"]["head_motion"] is True
    assert result["embodiment"]["surfaces"]["vr"]["locomotion"] is False
    assert result["semantics"]["knowledge_evaluation"].startswith("deterministic_regression")
    assert result["semantics"]["embodiment"].startswith("one_character_many_bodies")
    assert result["embodiment"]["live_scene"]["mode"] == "companion"
    assert result["embodiment"]["live_scene"]["floor_owner"] == "creator"
    assert result["embodiment"]["live_scene"]["realtime_phase"] == "listening"
    assert result["embodiment"]["live_scene"]["participant_count"] == 2
    assert result["embodiment"]["live_scene"]["recent_event_count"] == 1
    assert result["embodiment"]["live_scene"]["has_activity"] is True
    assert result["embodiment"]["live_scene"]["has_project"] is True
    assert "PRIVATE" not in str(result["embodiment"]["live_scene"])
    assert result["improvement_agenda"]["open_items"] == 3
    assert result["improvement_agenda"]["evidence_items"] == 3
    assert result["improvement_agenda"]["automatic_execution"] is False
    assert result["improvement_agenda"]["automatic_permission"] is False
    assert result["improvement_agenda"]["automatic_model_promotion"] is False
    assert result["semantics"]["improvement_agenda"].startswith("read_only_evidence_gaps")
