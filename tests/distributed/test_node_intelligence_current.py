from mary.distributed.node_intelligence import build_node_intelligence


class _Registry:
    def snapshot(self):
        return {
            "registered": 2,
            "nodes": [
                {
                    "node_id": "pc",
                    "display_name": "Main PC",
                    "platform": "windows",
                    "host_type": "desktop",
                    "surface": "device_node",
                    "transport": "https",
                    "connected": True,
                    "trusted": True,
                    "capabilities": {
                        "llm.ollama": {
                            "available": True,
                            "readiness": "ready",
                            "routable": True,
                            "metadata": {"execution_authorized": True},
                        },
                        "sensor.screen_describe": {
                            "available": True,
                            "readiness": "ready",
                            "routable": True,
                            "metadata": {"execution_authorized": False},
                        },
                    },
                },
                {
                    "node_id": "mac",
                    "platform": "macos",
                    "connected": False,
                    "capabilities": {
                        "llm.mlx": {
                            "available": True,
                            "readiness": "ready",
                            "metadata": {
                                "execution_authorized": True,
                                "model_experiment_id": "model_exp_1",
                                "model_experiment_trial_ready": True,
                                "model_experiment_benchmark_verified": True,
                            },
                        }
                    },
                },
            ],
        }


class _Competence:
    def summary_for(self, capability, *, node_ids=(), limit=4):
        if capability == "llm.ollama" and tuple(node_ids) == ("pc",):
            return [{
                "node_id": "pc",
                "attempts": 6,
                "successes": 5,
                "failures": 1,
                "verified_successes": 4,
                "reliability": 0.83,
                "evidence_strength": 0.8,
                "mean_latency_ms": 900.0,
                "last_success": True,
                "last_observed_at": "2026-09-18T00:00:00+00:00",
            }]
        return []


def test_node_intelligence_separates_presence_permission_and_competence():
    result = build_node_intelligence(_Registry(), _Competence())
    pc = next(item for item in result["nodes"] if item["node_id"] == "pc")
    ollama = next(
        item for item in pc["capabilities"] if item["name"] == "llm.ollama"
    )
    screen = next(
        item
        for item in pc["capabilities"]
        if item["name"] == "sensor.screen_describe"
    )

    assert ollama["execution_authorized"] is True
    assert ollama["evidence_state"] == "demonstrated"
    assert ollama["evidence"][0]["verified_successes"] == 4
    assert screen["execution_authorized"] is False
    assert screen["evidence_state"] == "advertised_unverified"
    assert pc["counts"]["demonstrated"] == 1
    assert result["execution_permission_granted"] is False
    assert result["routing_performed"] is False


def test_offline_node_never_becomes_demonstrated_from_advertisement():
    result = build_node_intelligence(_Registry(), _Competence())
    mac = next(item for item in result["nodes"] if item["node_id"] == "mac")
    mlx = mac["capabilities"][0]

    assert mlx["evidence_state"] == "offline"
    assert mlx["experiment"]["trial_ready"] is True
    assert mac["counts"]["trial_ready_experiments"] == 1
    assert result["promotion_performed"] is False
