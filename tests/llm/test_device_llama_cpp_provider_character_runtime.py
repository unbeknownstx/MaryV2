from threading import Thread

from mary.distributed import CapabilityDescriptor, DeviceTaskBroker, NodeDescriptor, NodeRegistry
from mary.llm.interface import LLMMessage
from mary.llm.providers.device_llama_cpp import DeviceLlamaCppProvider


def _registry():
    registry = NodeRegistry()
    registry.register(NodeDescriptor(
        node_id="mac-node",
        role="capability_node",
        host_type="desktop",
        platform="macos",
        capabilities={
            "llm.llama_cpp": CapabilityDescriptor(
                "llm.llama_cpp",
                private=True,
                local=True,
                metadata={"configured_model": "Qwen3-0.6B-Q4_0"},
            )
        },
    ))
    return registry


def test_device_llama_cpp_provider_roundtrip_through_broker():
    registry = _registry()
    broker = DeviceTaskBroker()
    provider = DeviceLlamaCppProvider(registry, broker, timeout_seconds=2.0)

    def worker():
        task = broker.poll("mac-node", wait_seconds=1.0)
        assert task is not None
        assert task.capability == "llm.llama_cpp"
        broker.complete(
            node_id="mac-node",
            task_id=task.task_id,
            status="completed",
            result={
                "content": "MARY LLAMA CPP NODE OK",
                "model": "Qwen3-0.6B-Q4_0",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 2, "completion_tokens": 5, "total_tokens": 7},
            },
        )

    thread = Thread(target=worker)
    thread.start()
    response = provider.generate([LLMMessage(role="user", content="hello")], max_tokens=32)
    thread.join(timeout=2.0)
    assert response.content == "MARY LLAMA CPP NODE OK"
    assert response.provider == "llama_cpp"
    assert response.model == "Qwen3-0.6B-Q4_0"
    assert provider.is_available() is True
    assert provider.model_name() == "Qwen3-0.6B-Q4_0"
