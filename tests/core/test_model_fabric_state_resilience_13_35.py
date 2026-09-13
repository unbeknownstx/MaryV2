from mary.core.service import MaryCoreService


class _Router:
    def routing_status(self):
        return {
            "strategy": "free_first",
            "providers": [],
        }


class _Registry:
    def snapshot(self):
        return {"nodes": [], "connected": 0, "registered": 0}

    def route_preview(self, capability):
        assert capability == "llm.ollama"
        return {
            "capability": capability,
            "available": False,
            "selected_node_id": None,
        }


class _Tasks:
    def snapshot(self):
        return {"pending": 0, "tasks": []}


class _Mary:
    def __init__(self):
        self.llm = _Router()
        self.node_registry = _Registry()


def test_compute_fabric_advisory_failure_never_breaks_core_state_projection(monkeypatch):
    service = object.__new__(MaryCoreService)
    service.mary = _Mary()
    service.device_tasks = _Tasks()

    def _explode(*_args, **_kwargs):
        raise RuntimeError("optional diagnostic exploded")

    monkeypatch.setattr("mary.core.service.build_model_execution_fabric", _explode)

    payload = service.compute_fabric_status()

    assert payload["routing"]["strategy"] == "free_first"
    assert payload["nodes"]["connected"] == 0
    assert payload["model_execution"]["status"] == "degraded"
    assert payload["model_execution"]["error_type"] == "RuntimeError"
    assert payload["model_execution"]["authority"] == "planning_and_observability_only"
    assert payload["private_route_ready"] is False
