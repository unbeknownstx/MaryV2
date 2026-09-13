from mary.distributed.cognitive_workload import workload_from_cognitive_plan


def test_relational_plan_becomes_realtime_local_workload():
    request = workload_from_cognitive_plan("llm.local", {
        "cognitive_mode": "relational",
        "reasoning_depth": "moderate",
        "latency_priority": "responsive",
        "local_preference": 0.82,
    })
    assert request.operation == "conversation"
    assert request.realtime is True
    assert request.local_preferred is True


def test_deliberate_plan_becomes_deep_reasoning_workload():
    request = workload_from_cognitive_plan("llm.local", {
        "cognitive_mode": "deliberate",
        "reasoning_depth": "deep",
        "latency_priority": "quality_first",
        "local_preference": 0.42,
    })
    assert request.operation == "deep_reasoning"
    assert request.realtime is False
    assert request.local_preferred is False
    assert request.estimated_seconds >= 10


def test_privacy_requirement_is_preserved_for_scheduler():
    request = workload_from_cognitive_plan("llm.local", {}, privacy_required=True)
    assert request.privacy_required is True
    assert request.cost_sensitive is True
