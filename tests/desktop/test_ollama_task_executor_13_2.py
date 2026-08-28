from types import SimpleNamespace

from mary.desktop import device_node as device_module
from mary.desktop.device_node import DesktopCapabilityNodeAgent
from mary.distributed import DeviceExecutionPermissions
from mary.llm.interface import LLMResponse


class FakeGateway:
    device_id = "windows-pc"

    def __init__(self):
        self.completions = []

    def register_node(self, **kwargs):
        return {"ok": True}

    def heartbeat_node(self):
        return {"ok": True}

    def disconnect_node(self):
        return {"ok": True}

    def complete_capability_task(self, task_id, *, status, result=None, error=""):
        payload = {"task_id": task_id, "status": status, "result": result or {}, "error": error}
        self.completions.append(payload)
        return {"ok": True, "task": payload}


class FakeBridge:
    integrations = SimpleNamespace(status=lambda: [])
    creative_workspace = SimpleNamespace(configured=False)


class FakeApplication:
    ecosystem = SimpleNamespace(search=None)


class FakeOllamaProvider:
    calls = []
    base_url = "http://127.0.0.1:11434"

    def __init__(self):
        self.model = "qwen3:4b"

    def is_available(self):
        return True

    def model_name(self):
        return self.model

    def generate(self, messages, *, temperature=0.7, max_tokens=2048):
        self.__class__.calls.append({
            "messages": [(item.role, item.content) for item in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        })
        return LLMResponse(
            content="Local Mary node response",
            provider="ollama",
            model=self.model,
            finish_reason="stop",
            usage={"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16},
            raw={"secret_internal": "must-not-cross-node-boundary"},
        )


def _task():
    return {
        "task_id": "capability_task_ollama123",
        "capability": "llm.ollama",
        "intent": "Generate through the selected private local model",
        "args": {
            "messages": [
                {"role": "system", "content": "Stay grounded."},
                {"role": "user", "content": "Say hello."},
            ],
            "temperature": 0.55,
            "max_tokens": 96,
        },
    }


def test_ollama_task_is_rejected_until_local_permission_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(device_module, "OllamaProvider", FakeOllamaProvider)
    gateway = FakeGateway()
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    agent = DesktopCapabilityNodeAgent(
        gateway,
        application=FakeApplication(),
        bridge=FakeBridge(),
        permissions=permissions,
    )

    result = agent._handle_task(_task())

    assert result["task"]["status"] == "rejected"
    assert "does not allow" in gateway.completions[-1]["error"]
    assert FakeOllamaProvider.calls == []


def test_authorized_ollama_task_uses_local_provider_and_returns_bounded_result(tmp_path, monkeypatch):
    FakeOllamaProvider.calls = []
    monkeypatch.setattr(device_module, "OllamaProvider", FakeOllamaProvider)
    gateway = FakeGateway()
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    permissions.allow("llm.ollama")
    agent = DesktopCapabilityNodeAgent(
        gateway,
        application=FakeApplication(),
        bridge=FakeBridge(),
        permissions=permissions,
    )

    result = agent._handle_task(_task())

    assert result["task"]["status"] == "completed"
    assert FakeOllamaProvider.calls == [{
        "messages": [("system", "Stay grounded."), ("user", "Say hello.")],
        "temperature": 0.55,
        "max_tokens": 96,
    }]
    payload = gateway.completions[-1]["result"]
    assert payload["content"] == "Local Mary node response"
    assert payload["provider"] == "ollama"
    assert payload["model"] == "qwen3:4b"
    assert payload["usage"]["total_tokens"] == 16
    assert "raw" not in payload
    assert "must-not-cross-node-boundary" not in repr(payload)
