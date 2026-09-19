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

    def summary_for(self, capability, *, node_ids=(), limit=4):
        if capability != "llm.ollama":
            return []
        return [{
            "node_id": "desktop-ready",
            "attempts": 8,
            "verified_successes": 7,
            "reliability": 0.88,
            "evidence_strength": 0.9,
            "mean_latency_ms": 820.0,
            "last_success": True,
            "last_observed_at": "2026-09-18T00:00:00+00:00",
        }]


class _StatusOwner:
    def __init__(self, payload, substrate=None):
        self.payload = payload
        self.substrate = substrate or {}

    def status(self):
        return dict(self.payload)

    def substrate_profile(self):
        return dict(self.substrate)


def _introspection(*, web: bool = True, registry=None, substrate: bool = False):
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
            },
        )
        if substrate else None
    )
    value.procedural_skills = (
        _StatusOwner({"approved": 5, "candidates": 2, "revision_attention": 1})
        if substrate else None
    )
    value.world_model = (
        _StatusOwner({"current_beliefs": 11, "reconciliation_groups": 2})
        if substrate else None
    )
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
    assert live["procedural_memory"]["approved"] == 5
    assert live["procedural_memory"]["revision_attention"] == 1
    assert live["world_model"]["reconciliation_groups"] == 2
    assert "advertised capability is separate from demonstrated competence" in evidence["fallback_response"]


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
