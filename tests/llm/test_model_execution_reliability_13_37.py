from mary.llm.model_fabric import assess_local_capability_route, build_model_execution_fabric


class _Router:
    def routing_status(self):
        return {"providers": []}


def _route(*, latency=1000.0, success=1.0, accuracy=1.0, useful=20.0):
    return {
        "available": True,
        "selected_node_id": "node",
        "candidate_benchmarks": {
            "node": {
                "benchmark_latency_ms": latency,
                "benchmark_success_rate": success,
                "benchmark_accuracy": accuracy,
                "benchmark_useful_throughput": useful,
            }
        },
    }


def test_fast_but_inaccurate_model_is_not_promoted_for_coding():
    result = assess_local_capability_route(_route(latency=500, accuracy=0.5, useful=60), "coding_agent")
    assert result["status"] == "avoid"
    assert result["reason"] == "measured_accuracy_below_lane_requirement"


def test_correct_slower_model_can_remain_feasible_for_deep_reasoning():
    result = assess_local_capability_route(_route(latency=200_000, accuracy=0.95, useful=12), "deep_reasoning")
    assert result["status"] == "feasible_slow"


def test_model_fabric_exposes_correctness_weighted_policy_without_granting_authority():
    fabric = build_model_execution_fabric(_Router(), capability_routes={"llm.ollama": _route()})
    assert fabric["reliability_revision"] == "13.37"
    assert fabric["promotion_policy"]["correctness_matters_more_than_raw_speed"] is True
    assert fabric["authority"] == "planning_and_observability_only"
