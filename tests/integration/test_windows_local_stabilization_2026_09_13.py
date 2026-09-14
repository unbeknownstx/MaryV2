from __future__ import annotations

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import Intent, IntentType
from mary.cognition.orchestrator import CognitiveOrchestrator
from mary.cognition.reasoning import ReasoningEngine
from mary.distributed import CapabilityDescriptor, DeviceExecutionPermissions
from mary.llm.interface import LLMResponse
from mary.runtime.introspection import RuntimeIntrospection
from mary.runtime import terminal
from scripts import run_home_node


class _PrivateRouter:
    def __init__(self) -> None:
        self.request = None
        self.last_generation_attempts = []
        self.last_generation_attempt_timings = []

    def session_override_status(self):
        return {"provider": None, "route": "private"}

    def conversation_provider_order(self):
        return ["ollama"]

    def generate_request(self, request, *, provider=None, route=None):
        self.request = request
        self.last_generation_attempts = [{"provider": "ollama", "status": "success"}]
        return LLMResponse(
            content="Yeah. I'm here.",
            provider="ollama",
            model="qwen3:1.7b",
            finish_reason="stop",
            usage={"prompt_tokens": 700, "completion_tokens": 7, "total_tokens": 707},
        )


def test_windows_node_role_question_is_runtime_self_query():
    cognition = CognitiveOrchestrator(None, None)

    intent = cognition.detect_intent(
        "Explain in your own words what role this Windows machine has in your architecture now."
    )

    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == "runtime_architecture"


def test_runtime_introspection_explains_node_without_moving_core_authority():
    runtime = RuntimeIntrospection()
    response = runtime.render(
        query="What role does this Windows machine play in your architecture?",
        environment={
            "host_type": "railway",
            "platform": "linux",
            "providers": {},
            "effective_conversation_route": ["groq", "ollama"],
            "effective_task_route": ["groq", "ollama"],
        },
        routing_strategy="free_first",
        configured_task_route=["groq", "ollama"],
        configured_conversation_route=["groq", "ollama"],
        nodes={
            "nodes": [
                {
                    "node_id": "DESKTOP-ATS5OPV",
                    "display_name": "DESKTOP-ATS5OPV",
                    "platform": "windows",
                    "connected": True,
                    "capabilities": {
                        "llm.ollama": {
                            "available": True,
                            "routable": True,
                            "metadata": {"configured_model": "qwen3:1.7b"},
                        },
                        "runtime.resource_profile": {
                            "available": True,
                            "routable": True,
                            "metadata": {
                                "cpu_count": 16,
                                "memory_gib": 31.89,
                                "vulkan": True,
                            },
                        },
                    },
                }
            ]
        },
    )

    lowered = response.lower()
    assert "desktop-ats5opv" in lowered
    assert "replaceable capability node" in lowered
    assert "railway / linux" in lowered
    assert "does not own my identity" in lowered
    assert "16 cpu threads" in lowered
    assert "vulkan" in lowered


def test_explicit_private_fast_chat_compiles_bounded_worker_context(monkeypatch):
    monkeypatch.setenv("MARY_LOCAL_FAST_CONTEXT_CHARS", "3200")
    monkeypatch.setenv("MARY_LOCAL_FAST_MAX_TOKENS", "80")
    router = _PrivateRouter()
    engine = ReasoningEngine(router)
    context = CognitiveContext(
        input_text="idk, I just want to talk for a minute",
        conversation=[
            {"role": "user", "content": "u" * 5000},
            {"role": "assistant", "content": "a" * 5000},
            {"role": "user", "content": "u2" * 2500},
            {"role": "assistant", "content": "a2" * 2500},
        ],
        memories=[{"content": "memory " * 600}],
        user_context={"name": "Unbe", "general": ["creator context " * 100]},
        mind_state={
            "disposition": {"preferred_length": "short", "mode": "conversation"},
            "continuity": {"drive": "react", "allow_follow_up_question": False},
            "conversation_engagement": {"effective_mode": "adaptive"},
            "local_mind": {"response_class": "open_conversation"},
        },
    )
    intent = Intent(
        intent_type=IntentType.CONVERSATION,
        confidence=0.9,
        description="ordinary conversation",
    )

    result = engine.reason(context, intent)

    assert router.request is not None
    assert router.request.purpose == "conversation_fast"
    assert router.request.max_tokens == 80
    assert len(router.request.messages) == 2
    assert len(router.request.messages[1].content) <= 3200
    assert result.metadata["local_fast_context"] is True
    assert result.metadata["prompt_characters"] < 5000
    assert result.metadata["provider"] == "ollama"


def test_home_node_does_not_advertise_denied_sensor_as_routable(tmp_path, monkeypatch):
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    permissions.allow("sensor.audio_transcribe")
    monkeypatch.setattr(
        run_home_node,
        "sensor_capabilities",
        lambda: [
            CapabilityDescriptor("sensor.audio_transcribe"),
            CapabilityDescriptor("sensor.screen_capture"),
        ],
    )

    capabilities = run_home_node._authorized_sensor_capabilities(permissions)

    assert [item.name for item in capabilities] == ["sensor.audio_transcribe"]


class _FailingProbeGateway:
    def __init__(self) -> None:
        self.closed = False

    def connect_surface(self):
        return {"ok": True}

    def state(self):
        return {
            "core": {"service": "mary-core", "architecture": "13.3"},
            "mary": {"name": "Mary"},
        }

    def runtime_action(self, *_args, **_kwargs):
        raise RuntimeError("simulated probe failure")

    def close(self):
        self.closed = True


def test_terminal_diagnostic_failure_does_not_kill_remote_session(monkeypatch, capsys):
    gateway = _FailingProbeGateway()
    commands = iter(["/probe-ollama", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(commands))

    terminal.run_remote_interactive(gateway)

    output = capsys.readouterr().out
    assert "[Mary Diagnostic Error] RuntimeError: simulated probe failure" in output
    assert gateway.closed is True
