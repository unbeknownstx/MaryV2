from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from mary.core.service import MaryCoreService
from mary.distributed import NodeRegistry
from mary.protocol.server import create_app


class FakeMary:
    def __init__(self):
        self.node_registry = NodeRegistry()
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


def test_typed_task_dispatch_poll_completion_round_trip(monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "task-secret")
    service = MaryCoreService(FakeApplication(), instance_id="task-core")
    app = create_app(service)
    headers = {"Authorization": "Bearer task-secret"}

    with TestClient(app) as client:
        reg = client.post("/v1/nodes/register", headers=headers, json={
            "node_id": "windows-pc",
            "display_name": "Windows PC",
            "host_type": "desktop",
            "platform": "windows",
            "surface": "desktop",
            "capabilities": [{"name": "personal_search", "private": True, "local": True}],
        })
        assert reg.status_code == 200

        dispatch = client.post("/v1/nodes/task/dispatch", headers=headers, json={
            "capability": "personal_search",
            "intent": "Find newest manuscript",
            "args": {"query": "Unbeknownst", "limit": 6},
            "device_id": "diagnostic",
        })
        assert dispatch.status_code == 200
        task = dispatch.json()["task"]
        assert task["selected_node_id"] == "windows-pc"
        assert dispatch.json()["execution"]["device_permission_required"] is True

        poll = client.post("/v1/nodes/task/poll", headers=headers, json={"node_id": "windows-pc"})
        assert poll.status_code == 200
        assert poll.json()["task"]["task_id"] == task["task_id"]

        completion = client.post("/v1/nodes/task/complete", headers=headers, json={
            "node_id": "windows-pc",
            "task_id": task["task_id"],
            "status": "completed",
            "result": {
                "query": "Unbeknownst",
                "count": 1,
                "items": [{"name": "Unbeknownst.docx", "relative_path": "Books/Unbeknownst.docx"}],
            },
        })
        assert completion.status_code == 200
        assert completion.json()["task"]["status"] == "completed"

        status = client.get(f"/v1/nodes/task/{task['task_id']}", headers=headers)
        assert status.status_code == 200
        assert status.json()["task"]["result"]["count"] == 1

        routes = {route.path for route in app.routes}
        assert "/v1/nodes/task/execute" not in routes


def test_dispatch_refuses_shell_and_wrong_node_cannot_complete(monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "task-secret")
    service = MaryCoreService(FakeApplication(), instance_id="task-core")
    app = create_app(service)
    headers = {"Authorization": "Bearer task-secret"}

    with TestClient(app) as client:
        bad = client.post("/v1/nodes/task/dispatch", headers=headers, json={
            "capability": "shell",
            "intent": "Run command",
            "args": {"command": "whoami"},
        })
        assert bad.status_code in {409, 422}


def test_ollama_task_uses_same_typed_core_broker_and_sanitizes_completion(monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "task-secret")
    service = MaryCoreService(FakeApplication(), instance_id="task-core")
    app = create_app(service)
    headers = {"Authorization": "Bearer task-secret"}

    with TestClient(app) as client:
        reg = client.post("/v1/nodes/register", headers=headers, json={
            "node_id": "windows-pc",
            "display_name": "Windows PC",
            "host_type": "desktop",
            "platform": "windows",
            "surface": "desktop",
            "capabilities": [{"name": "llm.ollama", "private": True, "local": True}],
        })
        assert reg.status_code == 200

        dispatch = client.post("/v1/nodes/task/dispatch", headers=headers, json={
            "capability": "llm.ollama",
            "intent": "Generate with the private Windows Ollama model",
            "args": {
                "messages": [{"role": "user", "content": "Hello Mary"}],
                "temperature": 0.5,
                "max_tokens": 80,
            },
            "device_id": "mary-core",
        })
        assert dispatch.status_code == 200
        task = dispatch.json()["task"]
        assert task["selected_node_id"] == "windows-pc"
        assert task["args"]["max_tokens"] == 80

        poll = client.post("/v1/nodes/task/poll", headers=headers, json={"node_id": "windows-pc"})
        assert poll.status_code == 200
        assert poll.json()["task"]["capability"] == "llm.ollama"

        completion = client.post("/v1/nodes/task/complete", headers=headers, json={
            "node_id": "windows-pc",
            "task_id": task["task_id"],
            "status": "completed",
            "result": {
                "content": "Hi from the PC.",
                "provider": "spoofed",
                "model": "qwen3:4b",
                "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
                "raw": {"secret": "discard"},
            },
        })
        assert completion.status_code == 200
        result = completion.json()["task"]["result"]
        assert result["content"] == "Hi from the PC."
        assert result["provider"] == "ollama"
        assert result["model"] == "qwen3:4b"
        assert "raw" not in result
        assert "discard" not in repr(result)
