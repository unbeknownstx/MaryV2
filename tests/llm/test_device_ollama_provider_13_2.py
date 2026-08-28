from threading import Thread

from mary.distributed import CapabilityDescriptor, DeviceTaskBroker, NodeDescriptor, NodeRegistry
from mary.llm.interface import LLMMessage
from mary.llm.providers.device_ollama import DeviceOllamaProvider


def _registry():
    registry = NodeRegistry()
    registry.register(NodeDescriptor(
        node_id="windows-pc",
        role="capability_node",
        host_type="desktop",
        platform="windows",
        capabilities={
            "llm.ollama": CapabilityDescriptor(
                "llm.ollama",
                private=True,
                local=True,
                metadata={
                    "general_model": "general-model",
                    "conversation_model": "conversation-model",
                    "fast_model": "fast-model",
                },
            ),
        },
    ))
    return registry


def test_device_ollama_provider_uses_existing_broker_and_sanitized_result():
    registry = _registry()
    broker = DeviceTaskBroker()
    provider = DeviceOllamaProvider(registry, broker, timeout_seconds=2.0)

    def worker():
        task = broker.poll("windows-pc", wait_seconds=1.0)
        assert task is not None
        assert task.args["role"] == "general"
        broker.complete(
            node_id="windows-pc",
            task_id=task.task_id,
            status="completed",
            result={
                "content": "hello from the node",
                "provider": "spoofed",
                "model": "general-model",
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
                "raw": {"secret": "discard"},
            },
        )

    thread = Thread(target=worker)
    thread.start()
    response = provider.generate([LLMMessage(role="user", content="hello")], max_tokens=64)
    thread.join(timeout=1.0)

    assert response.provider == "ollama"
    assert response.model == "general-model"
    assert response.content == "hello from the node"
    assert response.usage["total_tokens"] == 7
    assert response.raw is None


def test_device_ollama_provider_maps_existing_generation_purposes_to_local_roles():
    provider = DeviceOllamaProvider(_registry(), DeviceTaskBroker())

    assert provider.for_purpose("conversation").role == "conversation"
    assert provider.for_purpose("social_instant").role == "fast"
    assert provider.for_purpose("conversation_fast").role == "fast"
    assert provider.for_purpose(None).role == "general"
    assert provider.for_purpose("task").role == "general"
    assert provider.for_purpose("conversation").model_name() == "conversation-model"
    assert provider.for_purpose("social_instant").model_name() == "fast-model"
