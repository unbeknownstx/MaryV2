from threading import Thread
from types import SimpleNamespace

from mary.core.config import Config
from mary.core.service import MaryCoreService
from mary.distributed import NodeRegistry
from mary.llm.interface import LLMMessage
from mary.llm.router import LLMRouter


class FakeMary:
    def __init__(self):
        self.node_registry = NodeRegistry()
        self.llm = LLMRouter(Config())
        self.engagement = SimpleNamespace(status=lambda: {}, set_mode=lambda mode: {})
        self.realtime = SimpleNamespace(status=lambda: {})
        self.memory = SimpleNamespace(status=lambda: {})
        self.relationship = SimpleNamespace(governance_status=lambda: {})
        self.growth = SimpleNamespace(status=lambda: {})
        self.runtime_environment = SimpleNamespace(snapshot=lambda: {})

    def live_state(self, runtime_status=None):
        return {"name": "Mary"}


class FakeApplication:
    def __init__(self):
        self.mary = FakeMary()
        self.state = SimpleNamespace(to_dict=lambda: {})
        self.ecosystem = SimpleNamespace()

    def save(self):
        return True

    def close(self):
        return True


def test_core_ollama_provider_can_complete_while_canonical_turn_lock_is_held():
    service = MaryCoreService(FakeApplication(), instance_id="bridge-core")
    service.register_creator_surface({"surface_id": "test-creator"})
    registration = service.register_node({
        "node_id": "windows-pc",
        "display_name": "Windows PC",
        "host_type": "desktop",
        "platform": "windows",
        "surface": "desktop",
        "capabilities": [{
            "name": "llm.ollama",
            "private": True,
            "local": True,
            "metadata": {"general_model": "node-model"},
        }],
    })
    node_token = registration["node_token"]
    provider = service.mary.llm.get_provider("ollama")
    assert provider.is_available() is True

    def device_worker():
        polled = service.poll_capability_task(
            {"node_id": "windows-pc", "wait_seconds": 1.0},
            node_token=node_token,
        )
        task = polled["task"]
        assert task["args"]["role"] == "general"
        service.complete_capability_task({
            "node_id": "windows-pc",
            "task_id": task["task_id"],
            "status": "completed",
            "result": {
                "content": "node result",
                "model": "node-model",
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
        }, node_token=node_token)

    worker = Thread(target=device_worker)
    worker.start()
    # process_turn intentionally holds this lock around Mary's canonical state
    # mutation. The device task channel must remain able to poll and complete.
    with service._turn_lock:
        response = provider.generate(
            [LLMMessage(role="user", content="hello")],
            max_tokens=32,
        )
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert response.content == "node result"
    assert response.provider == "ollama"
    assert response.model == "node-model"
