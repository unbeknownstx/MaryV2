from mary.llm.model_fabric import (
    TASK_LANES,
    assess_local_capability_route,
    build_model_execution_fabric,
)
from mary.llm.provider_catalog import get_provider_preset


class _Provider:
    def __init__(self, available: bool, model: str) -> None:
        self._available = available
        self._model = model

    def is_available(self):
        return self._available

    def model_name(self):
        return self._model


class _Router:
    def routing_status(self):
        return {
            "providers": [
                {
                    "provider": "groq",
                    "available": True,
                    "model": "fast-cloud",
                    "source": "configured_host",
                    "cost_class": "free_cloud",
                    "privacy_modes": ["cloud_ok"],
                    "operations": ["conversation", "task_generation"],
                },
                {
                    "provider": "ollama",
                    "available": True,
                    "model": "qwen3:4b-instruct",
                    "source": "capability_node",
                    "cost_class": "zero_local",
                    "privacy_modes": ["local_only", "cloud_ok"],
                    "operations": ["conversation", "task_generation"],
                },
                {
                    "provider": "deepseek",
                    "available": True,
                    "model": "deepseek-v4-flash",
                    "source": "configured_host",
                    "cost_class": "paid_low",
                    "privacy_modes": ["cloud_ok"],
                    "operations": ["conversation", "expert_reasoning"],
                },
            ]
        }

    def get_provider(self, name):
        raise AssertionError("model-fabric diagnostics must not construct providers")


def _route(latency_ms=55_000.0, success=0.9):
    return {
        "available": True,
        "selected_node_id": "windows",
        "candidate_benchmarks": {
            "windows": {
                "benchmark_latency_ms": latency_ms,
                "benchmark_success_rate": success,
                "benchmark_throughput": 8.5,
            }
        },
    }


def test_same_local_engine_can_be_bad_for_banter_but_good_for_deep_work():
    route = _route()

    social = assess_local_capability_route(route, "social_instant")
    private = assess_local_capability_route(route, "private_conversation")
    deep = assess_local_capability_route(route, "deep_reasoning")

    assert social["status"] == "avoid"
    assert private["status"] == "preferred"
    assert deep["status"] == "preferred"


def test_unbenchmarked_local_engine_is_experimental_not_preferred():
    result = assess_local_capability_route(
        {
            "available": True,
            "selected_node_id": "windows",
            "candidate_benchmarks": {"windows": {}},
        },
        "conversation",
    )
    assert result["status"] == "experimental"
    assert result["measured"] is False


def test_model_execution_fabric_keeps_frontier_models_opt_in_and_measured():
    fabric = build_model_execution_fabric(
        _Router(),
        capability_routes={"llm.ollama": _route()},
    )

    deepseek = next(
        item for item in fabric["frontier_catalog"]
        if item["name"] == "deepseek"
    )
    assert deepseek["configured"] is True
    assert deepseek["active_model"] == "deepseek-v4-flash"
    assert deepseek["auto_promoted"] is False
    assert deepseek["promotion"] == "benchmark_required"
    assert fabric["promotion_policy"]["paid_requires_existing_authorization"] is True
    assert fabric["operating_policy"]["ordinary_budget"] == "zero_cost_and_free_only"
    assert fabric["operating_policy"]["local_preference"] == "prefer_when_lane_suitable"
    assert fabric["operating_policy"]["free_cloud_fallback_order"] == [
        "groq", "gemini", "openrouter"
    ]
    assert fabric["operating_policy"]["paid_frontier"] == "explicit_only"
    assert "coding_agent" in TASK_LANES


def test_deepseek_preset_tracks_current_v4_flash_model_id():
    preset = get_provider_preset("deepseek")
    assert preset is not None
    assert preset.default_model == "deepseek-v4-flash"


def test_model_fabric_status_is_passive_and_does_not_construct_optional_providers():
    fabric = build_model_execution_fabric(
        _Router(),
        capability_routes={"llm.ollama": _route()},
    )

    deepseek = next(
        item for item in fabric["frontier_catalog"]
        if item["name"] == "deepseek"
    )
    assert deepseek["configured"] is True
    assert deepseek["active_model"] == "deepseek-v4-flash"
