from types import SimpleNamespace

from mary.cognition.self_introspection import SelfIntrospection


class _Tools:
    def __init__(self, *, web: bool) -> None:
        self.web = web

    def status(self):
        return {
            "registered": 4,
            "web_search_configured": self.web,
            "web_search_provider": "test-search",
            "workspace_root": "/bounded/workspace",
            "repository_map": {"registered": True, "execution": False, "mutation": False},
        }


class _Registry:
    def snapshot(self):
        return {
            "registered": 2,
            "nodes": [
                {
                    "node_id": "desktop-ready",
                    "display_name": "Desktop",
                    "platform": "windows",
                    "connected": True,
                    "capabilities": {
                        "llm.ollama": {
                            "available": True,
                            "readiness": "ready",
                            "metadata": {"execution_authorized": True},
                        },
                        "sensor.screen_describe": {
                            "available": True,
                            "readiness": "ready",
                            "metadata": {"execution_authorized": False},
                        },
                    },
                },
                {
                    "node_id": "old-mac",
                    "platform": "macos",
                    "connected": False,
                    "capabilities": {
                        "llm.ollama": {
                            "available": True,
                            "readiness": "ready",
                            "metadata": {"execution_authorized": True},
                        }
                    },
                },
            ],
        }


class _Competence:
    def status(self):
        return {"records": 2}

    def find(self, *, limit=500, **_kwargs):
        return [
            SimpleNamespace(capability="llm.ollama"),
            SimpleNamespace(capability="sensor.screen_describe"),
        ][:limit]

    def summary_for(self, capability, *, node_ids=(), limit=4):
        if capability != "llm.ollama":
            return []
        return [{
            "node_id": "desktop-ready",
            "skill_id": "skill-good",
            "implementation_fingerprint": "impl-ollama",
            "attempts": 8,
            "verified_successes": 7,
            "reliability": 0.88,
            "evidence_strength": 0.9,
            "mean_latency_ms": 820.0,
            "last_success": True,
            "last_observed_at": "2026-09-18T00:00:00+00:00",
        }]

    def skill_summary(self, skill_id, *, capability="", node_ids=()):
        if skill_id == "skill-good":
            return {
                "attempts": 8,
                "successes": 7,
                "failures": 1,
                "verified_successes": 7,
                "reliability": 0.8,
                "evidence_strength": 0.63,
                "demonstrated": True,
                "last_success": True,
                "last_observed_at": "2026-09-18T00:00:00+00:00",
            }
        if skill_id == "skill-degrading":
            return {
                "attempts": 5,
                "successes": 2,
                "failures": 3,
                "verified_successes": 2,
                "reliability": 0.43,
                "evidence_strength": 0.46,
                "demonstrated": True,
                "last_success": False,
                "last_observed_at": "2026-09-18T01:00:00+00:00",
            }
        if skill_id == "skill-revision":
            return {
                "attempts": 4,
                "successes": 3,
                "failures": 1,
                "verified_successes": 3,
                "reliability": 0.67,
                "evidence_strength": 0.39,
                "demonstrated": True,
                "last_success": True,
                "last_observed_at": "2026-09-18T02:00:00+00:00",
            }
        return {}


class _StatusOwner:
    def __init__(self, payload, substrate=None):
        self.payload = payload
        self.substrate = substrate or {}

    def status(self):
        return dict(self.payload)

    def substrate_profile(self):
        return dict(self.substrate)


class _KnowledgeEvaluationEvidence:
    def snapshot(self, *, current_substrate_fingerprint=""):
        return {
            "runs": 3,
            "latest_all_passed": True,
            "stale": False,
            "current_substrate_match": True,
            "content_retained": False,
        }


class _Procedures(_StatusOwner):
    def __init__(self):
        super().__init__({"approved": 5, "candidates": 2, "revision_attention": 1})

    def approved(self):
        return [
            SimpleNamespace(
                id="skill-good",
                name="stable local inference",
                version=2,
                required_capabilities=("llm.ollama",),
            ),
            SimpleNamespace(
                id="skill-degrading",
                name="fragile screen workflow",
                version=1,
                required_capabilities=("sensor.screen_describe",),
            ),
        ]

    def revision_queue(self, *, limit=200):
        return [{
            "skill_id": "skill-degrading",
            "revision_pressure": 0.48,
            "failure_rate": 0.6,
        }]

    def revision_lineage(self, *, limit=100, competence=None):
        return {
            "version": "13.78",
            "revisions": 1,
            "pending_review": 1,
            "approved_replacements": 0,
            "rows": [{
                "candidate_id": "skill-revision",
                "candidate_version": 2,
                "candidate_status": "candidate",
                "predecessor_id": "skill-degrading",
                "predecessor_version": 1,
                "predecessor_status": "approved",
                "revision_reason": "reduce failure rate",
                "changed_fields": ["steps"],
                "required_capabilities_unchanged": True,
                "required_permissions_unchanged": True,
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "candidate_trial_observed": True,
                "comparison": {
                    "state": "review_ready",
                    "review_ready": True,
                    "capability": "sensor.screen_describe",
                    "candidate": {
                        "attempts": 4,
                        "verified_successes": 3,
                        "reliability": 0.67,
                        "evidence_strength": 0.39,
                    },
                    "predecessor": {
                        "attempts": 5,
                        "verified_successes": 2,
                        "reliability": 0.43,
                        "evidence_strength": 0.46,
                    },
                    "reliability_delta": 0.24,
                    "evidence_needed": [
                        "creator review of the bounded comparison before any approval decision"
                    ],
                    "superiority_claimed": False,
                    "automatic_approval": False,
                },
                "evidence_needed": [
                    "explicit creator review before this revision can supersede the approved predecessor",
                    "creator review of the bounded comparison before any approval decision",
                ],
                "approval_required": True,
                "automatic_approval": False,
                "automatic_execution": False,
            }],
            "authority": "read-only procedure version lineage",
        }


class _ExperimentLedger:
    def snapshot(self):
        return {
            "count": 3,
            "trial_ready": 1,
            "records": [
                {
                    "id": "exp-reviewed",
                    "candidate_id": "mary-smoke",
                    "status": "reviewed",
                    "runtime": "mlx_lm",
                    "model": "mlx-community/Qwen3-0.6B-4bit",
                    "benchmark_verified": False,
                    "trial_ready": False,
                    "missing_scores": ["naturalism"],
                },
                {
                    "id": "exp-mismatch",
                    "candidate_id": "mary-mismatch",
                    "status": "benchmark_mismatch",
                    "runtime": "mlx_lm",
                    "model": "mlx-community/Qwen3-1.7B-4bit",
                    "benchmark_verified": False,
                    "trial_ready": False,
                },
                {
                    "id": "exp-ready",
                    "candidate_id": "mary-light",
                    "status": "benchmarked",
                    "runtime": "mlx_lm",
                    "model": "mlx-community/Qwen3-1.7B-4bit",
                    "node_id": "mac-m1",
                    "benchmark_verified": True,
                    "trial_ready": True,
                    "mary_fit": 0.91,
                    "trial_evidence": {
                        "dispatches": 1,
                        "attempts": 1,
                        "completed": 1,
                        "failed": 0,
                        "rejected": 0,
                        "expired": 0,
                        "completed_trial_observed": True,
                        "latest_status": "completed",
                        "last_observed_at": "2026-09-20T23:00:00+00:00",
                    },
                },
            ],
        }


def _introspection(
    *,
    web: bool = True,
    registry=None,
    substrate: bool = False,
    experiments: bool = False,
):
    value = object.__new__(SelfIntrospection)
    value.tools = _Tools(web=web)
    value.node_registry = registry
    value.agency = SimpleNamespace(status=lambda: {"active": True})
    value.autonomy = SimpleNamespace()
    value.competence = _Competence() if substrate else None
    value.knowledge_fabric = (
        _StatusOwner(
            {"packs": 4, "enabled": 2, "indexed_documents": 1200},
            {
                "counts": {
                    "active_local": 2,
                    "offline_reference": 1,
                    "semantic_derivative": 1,
                    "catalog_candidates": 0,
                },
                "enabled_retrieval_modes": ["fts", "direct", "vector"],
                "attention_required": True,
                "stale_derivatives": [{"pack_id": "vectors"}],
                "stale_local_indexes": [
                    {"pack_id": "notes", "state": "pipeline_stale"}
                ],
            },
        )
        if substrate else None
    )
    value.knowledge_evaluation_evidence = (
        _KnowledgeEvaluationEvidence() if substrate else None
    )
    value.procedural_skills = _Procedures() if substrate else None
    value.world_model = (
        _StatusOwner({"current_beliefs": 11, "reconciliation_groups": 2})
        if substrate else None
    )
    value.model_experiments = _ExperimentLedger() if experiments else None
    return value


def test_capability_introspection_uses_live_tools_and_connected_nodes():
    evidence = _introspection(registry=_Registry())._capabilities()
    live = evidence["live_capabilities"]

    assert live["web_search"]["available"] is True
    assert live["nodes"]["connected"] == 1
    assert live["nodes"]["registered"] == 2
    assert live["nodes"]["advertised_capabilities"] == ["llm.ollama", "sensor.screen_describe"]
    assert live["nodes"]["execution_ready_capabilities"] == ["llm.ollama"]
    assert evidence["authority"].startswith("live Core/tool/node state plus bounded competence")
    assert "provider model priors are not capability evidence" in evidence["authority"]


def test_capability_introspection_projects_competence_and_local_substrates():
    evidence = _introspection(registry=_Registry(), substrate=True)._capabilities()
    live = evidence["live_capabilities"]

    assert live["nodes"]["competence_records"] == 2
    assert live["nodes"]["demonstrated_competence"]["llm.ollama"][0]["attempts"] == 8
    assert live["knowledge_substrate"]["packs"] == 4
    assert live["knowledge_substrate"]["enabled"] == 2
    assert live["knowledge_substrate"]["indexed_documents"] == 1200
    assert live["knowledge_substrate"]["available"] is True
    assert live["knowledge_substrate"]["tiers"]["active_local"] == 2
    assert live["knowledge_substrate"]["enabled_retrieval_modes"] == [
        "fts", "direct", "vector"
    ]
    assert live["knowledge_substrate"]["attention_required"] is True
    assert live["knowledge_substrate"]["stale_derivatives"] == 1
    assert live["knowledge_substrate"]["stale_local_indexes"] == 1
    assert live["knowledge_substrate"]["evaluation_runs"] == 3
    assert live["knowledge_substrate"]["latest_evaluation_passed"] is True
    assert live["knowledge_substrate"]["evaluation_stale"] is False
    assert live["knowledge_substrate"]["evaluation_current_substrate_match"] is True
    assert live["knowledge_substrate"]["evaluation_content_retained"] is False
    assert live["procedural_memory"]["approved"] == 5
    assert live["procedural_memory"]["revision_attention"] == 1
    assert live["procedural_memory"]["demonstrated"] == 2
    assert live["procedural_memory"]["degrading"] == 1
    assert live["procedural_memory"]["procedures"][0]["state"] == "degrading"
    assert live["procedural_memory"]["revision_lineage"]["pending_review"] == 1
    lineage = live["procedural_memory"]["revision_lineage"]["rows"][0]
    assert lineage["candidate_id"] == "skill-revision"
    assert lineage["predecessor_id"] == "skill-degrading"
    assert lineage["automatic_approval"] is False
    assert lineage["comparison"]["state"] == "review_ready"
    assert lineage["comparison"]["review_ready"] is True
    assert lineage["comparison"]["reliability_delta"] == 0.24
    assert lineage["comparison"]["superiority_claimed"] is False
    assert live["capability_improvement"]["llm.ollama"]["demonstrated"] is True
    assert live["capability_improvement"]["sensor.screen_describe"]["evidence_needed"]
    assert live["world_model"]["reconciliation_groups"] == 2
    assert "advertised capability is separate from demonstrated competence" in evidence["fallback_response"]


def test_disconnected_capability_keeps_historical_competence_but_loses_current_availability():
    evidence = _introspection(
        registry=None,
        substrate=True,
    )._capabilities(
        "what capabilities have you demonstrated even if a node is offline?"
    )
    live = evidence["live_capabilities"]

    assert live["nodes"]["advertised_capabilities"] == []
    assert "llm.ollama" in live["nodes"]["known_competence_capabilities"]
    assert live["nodes"]["historical_demonstrated_competence"]["llm.ollama"][0]["attempts"] == 8
    improvement = live["capability_improvement"]["llm.ollama"]
    assert improvement["demonstrated"] is True
    assert improvement["currently_advertised"] is False
    assert improvement["execution_authorized"] is False


def test_capability_introspection_does_not_invent_browse_or_device_execution():
    evidence = _introspection(web=False, registry=None)._capabilities()
    live = evidence["live_capabilities"]

    assert live["web_search"]["available"] is False
    assert live["nodes"]["connected"] == 0
    assert live["nodes"]["advertised_capabilities"] == []
    assert "Web search is not currently configured" in evidence["fallback_response"]
    assert "do not currently have a connected capability node" in evidence["fallback_response"]


def test_concrete_screen_question_reports_advertised_but_not_authorized():
    evidence = _introspection(registry=_Registry(), substrate=True)._capabilities(
        "can you see my screen right now?"
    )

    answer = evidence["fallback_response"]
    assert "screen vision" in answer
    assert "sensor.screen_describe" in answer
    assert "not presently execution-authorized" in answer


def test_concrete_local_model_question_reports_ready_authorized_route():
    evidence = _introspection(registry=_Registry(), substrate=True)._capabilities(
        "can you use a local model?"
    )

    answer = evidence["fallback_response"]
    assert "local model inference" in answer
    assert "llm.ollama" in answer
    assert "execution-authorize" in answer


def test_broad_node_capability_question_enumerates_live_and_ready_sets():
    evidence = _introspection(registry=_Registry(), substrate=True)._capabilities(
        "what can your nodes actually do?"
    )

    answer = evidence["fallback_response"]
    assert "currently advertise: llm.ollama, sensor.screen_describe" in answer
    assert "execution-authorized ready subset is: llm.ollama" in answer


def test_local_knowledge_question_uses_core_substrate_and_reports_staleness():
    evidence = _introspection(registry=_Registry(), substrate=True)._capabilities(
        "is your local knowledge corpus current?"
    )

    answer = evidence["fallback_response"]
    assert "local knowledge substrate is available" in answer
    assert "fts, direct, vector" in answer
    assert "1 local index is stale" in answer
    assert "explicit reindexing" in answer
    assert "1 semantic derivative" in answer
    assert "No connected node currently advertises local knowledge search" not in answer


def test_model_experiment_question_reports_evidence_without_claiming_training_or_promotion():
    evidence = _introspection(
        registry=_Registry(),
        substrate=True,
        experiments=True,
    )._capabilities(
        "is the Mary LoRA model experiment training ready or trial-ready?"
    )
    live = evidence["live_capabilities"]
    model_lab = live["model_experiments"]

    assert model_lab["count"] == 3
    assert model_lab["reviewed_only"] == 1
    assert model_lab["benchmarked"] == 1
    assert model_lab["benchmark_mismatch"] == 1
    assert model_lab["benchmark_verified"] == 1
    assert model_lab["trial_ready"] == 1
    assert model_lab["experimental_records"] == 3
    assert all(item["experimental"] is True for item in model_lab["records"])
    assert all(item["production_authority"] is False for item in model_lab["records"])
    reviewed = next(
        item for item in model_lab["records"]
        if item["id"] == "exp-reviewed"
    )
    assert any("naturalism" in item for item in reviewed["evidence_needed"])
    ready = next(
        item for item in model_lab["records"]
        if item["id"] == "exp-ready"
    )
    assert ready["trial_evidence"]["attempts"] == 1
    assert ready["trial_evidence"]["completed"] == 1
    assert ready["trial_evidence"]["completed_trial_observed"] is True
    assert ready["trial_evidence"]["quality_verified"] is False
    assert not any("bounded explicit trial outcomes" in item for item in ready["evidence_needed"])
    assert any("creator-reviewed comparison" in item for item in ready["evidence_needed"])
    assert model_lab["training_readiness_claimed"] is False
    assert model_lab["automatic_training"] is False
    assert model_lab["automatic_promotion"] is False

    answer = evidence["fallback_response"]
    assert "1 with verified benchmark lineage" in answer
    assert "1 trial-ready" in answer
    assert "does not mean production promotion" in answer
    assert "host/package preflight" in answer
    assert "training is never automatic" in answer

def test_procedure_self_awareness_reports_demonstrated_degrading_and_needed_evidence():
    evidence = _introspection(
        registry=_Registry(),
        substrate=True,
        experiments=True,
    )._capabilities(
        "What procedures are you good at, what is degrading, and what evidence do you need to improve?"
    )

    live = evidence["live_capabilities"]
    procedures = live["procedural_memory"]

    assert procedures["demonstrated"] == 2
    assert procedures["degrading"] == 1
    degrading = next(
        item for item in procedures["procedures"]
        if item["skill_id"] == "skill-degrading"
    )
    assert degrading["state"] == "degrading"
    assert degrading["revision_pressure"] == 0.48
    assert any("creator review" in item for item in degrading["evidence_needed"])

    answer = evidence["fallback_response"]
    assert "verified successful evidence" in answer
    assert "degradation/revision review" in answer
    assert "never approves, binds, authorizes, or executes" in answer
    assert "evidence gaps" in answer

