import pytest

from mary.distributed import CapabilityDescriptor, DeviceTaskBroker, NodeDescriptor, NodeRegistry


def _registry(*capability_names: str):
    registry = NodeRegistry()
    names = capability_names or ("personal_search",)
    capabilities = {
        name: CapabilityDescriptor(name, private=True, local=True)
        for name in names
    }
    registry.register(NodeDescriptor(
        node_id="windows-pc",
        role="capability_node",
        host_type="desktop",
        platform="windows",
        capabilities=capabilities,
    ))
    return registry


def test_broker_routes_typed_task_and_only_selected_node_can_complete():
    broker = DeviceTaskBroker()
    task = broker.enqueue(
        _registry(),
        capability="personal_search",
        intent="Find my manuscript",
        args={"query": "Unbeknownst", "limit": 99},
        requester_device_id="iphone",
    )
    assert task.selected_node_id == "windows-pc"
    assert task.args == {"query": "Unbeknownst", "limit": 12}

    claimed = broker.poll("windows-pc")
    assert claimed is not None
    assert claimed.task_id == task.task_id
    assert claimed.status == "claimed"

    with pytest.raises(PermissionError):
        broker.complete(
            node_id="other-pc",
            task_id=task.task_id,
            status="completed",
            result={},
        )

    completed = broker.complete(
        node_id="windows-pc",
        task_id=task.task_id,
        status="completed",
        result={"count": 1},
    )
    assert completed.status == "completed"
    assert broker.get(task.task_id).result == {"count": 1}


def test_execution_policy_blocks_enqueue_and_claim_but_not_completion():
    registry = _registry()

    def deny(kind: str) -> None:
        raise RuntimeError(f"denied: {kind}")

    broker = DeviceTaskBroker(execution_policy=deny)
    with pytest.raises(RuntimeError, match="denied: device_task.enqueue"):
        broker.enqueue(
            registry,
            capability="personal_search",
            intent="Find manuscript",
            args={"query": "Unbeknownst"},
            requester_device_id="iphone",
        )
    assert broker.snapshot()["tasks"] == []

    broker.set_execution_policy(None)
    task = broker.enqueue(
        registry,
        capability="personal_search",
        intent="Find manuscript",
        args={"query": "Unbeknownst"},
        requester_device_id="iphone",
    )
    broker.set_execution_policy(deny)
    with pytest.raises(RuntimeError, match="denied: device_task.claim"):
        broker.poll("windows-pc")
    assert broker.get(task.task_id).status == "queued"

    # Completing work already executing does not invoke the execution gate.
    task.claimed = True
    task.status = "claimed"
    completed = broker.complete(
        node_id="windows-pc",
        task_id=task.task_id,
        status="completed",
        result={"count": 1},
    )
    assert completed.status == "completed"

    broker.set_execution_policy(None)
    follow_up = broker.enqueue(
        registry,
        capability="personal_search",
        intent="Find notes",
        args={"query": "notes"},
        requester_device_id="iphone",
    )
    assert broker.poll("windows-pc").task_id == follow_up.task_id


def test_broker_has_no_shell_execution_contract():
    broker = DeviceTaskBroker()
    with pytest.raises(ValueError):
        broker.enqueue(
            _registry(),
            capability="shell",
            intent="run a command",
            args={"command": "whoami"},
            requester_device_id="client",
        )


def test_broker_sanitizes_bounded_ollama_chat_task():
    broker = DeviceTaskBroker()
    task = broker.enqueue(
        _registry("llm.ollama"),
        capability="llm.ollama",
        intent="Use the private local model",
        args={
            "messages": [
                {"role": "system", "content": " Stay grounded. "},
                {"role": "user", "content": " Hello Mary "},
            ],
            "temperature": 9.0,
            "max_tokens": 99999,
        },
        requester_device_id="mary-core",
    )

    assert task.args == {
        "messages": [
            {"role": "system", "content": "Stay grounded."},
            {"role": "user", "content": "Hello Mary"},
        ],
        "role": "general",
        "temperature": 1.5,
        "max_tokens": 2048,
    }


def test_broker_rejects_unbounded_or_invalid_ollama_messages():
    broker = DeviceTaskBroker()
    registry = _registry("llm.ollama")

    with pytest.raises(ValueError):
        broker.enqueue(
            registry,
            capability="llm.ollama",
            intent="invalid role",
            args={"messages": [{"role": "tool", "content": "no"}]},
            requester_device_id="mary-core",
        )

    with pytest.raises(ValueError):
        broker.enqueue(
            registry,
            capability="llm.ollama",
            intent="oversized content",
            args={"messages": [{"role": "user", "content": "x" * 12_001}]},
            requester_device_id="mary-core",
        )


def test_core_broker_discards_unexpected_ollama_result_fields():
    broker = DeviceTaskBroker()
    task = broker.enqueue(
        _registry("llm.ollama"),
        capability="llm.ollama",
        intent="Use private local model",
        args={"messages": [{"role": "user", "content": "Hello"}]},
        requester_device_id="mary-core",
    )
    broker.poll("windows-pc")
    completed = broker.complete(
        node_id="windows-pc",
        task_id=task.task_id,
        status="completed",
        result={
            "content": "hello from local",
            "provider": "spoofed",
            "model": "qwen3:4b",
            "usage": {"prompt_tokens": 2, "completion_tokens": 4, "total_tokens": 6},
            "raw": {"secret": "do not retain"},
            "unexpected": "discard me",
        },
    )

    assert completed.result == {
        "content": "hello from local",
        "provider": "ollama",
        "model": "qwen3:4b",
        "finish_reason": "",
        "usage": {"prompt_tokens": 2, "completion_tokens": 4, "total_tokens": 6},
        "privacy": "generated on selected device; raw provider payload not retained by Core",
    }
    assert "secret" not in repr(completed.result)
    assert "unexpected" not in repr(completed.result)


def test_broker_sanitizes_bounded_llama_cpp_chat_task_and_result():
    broker = DeviceTaskBroker()
    task = broker.enqueue(
        _registry("llm.llama_cpp"),
        capability="llm.llama_cpp",
        intent="Use Mac local model",
        args={
            "messages": [{"role": "user", "content": " Hello Mary "}],
            "role": "fast",
            "temperature": 9,
            "max_tokens": 99999,
        },
        requester_device_id="mary-core",
    )
    assert task.args["messages"] == [{"role": "user", "content": "Hello Mary"}]
    assert task.args["role"] == "fast"
    assert task.args["temperature"] == 1.5
    assert task.args["max_tokens"] == 2048
    broker.poll("windows-pc")
    completed = broker.complete(
        node_id="windows-pc",
        task_id=task.task_id,
        status="completed",
        result={
            "content": "local hello",
            "provider": "spoofed",
            "model": "Qwen3-0.6B",
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            "raw": {"secret": "drop"},
        },
    )
    assert completed.result["provider"] == "llama_cpp"
    assert completed.result["content"] == "local hello"
    assert "secret" not in repr(completed.result)
