from __future__ import annotations

import json

from mary.cognition.context import CognitiveContext
from mary.cognition.reasoning import ReasoningEngine, ReasoningResult
from mary.cognition.reflection import ReflectionEngine, ReflectionDecision
from mary.llm.interface import LLMResponse
from mary.tools.manager import ToolManager


class CaptureLLM:
    def __init__(self) -> None:
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return LLMResponse(
            content="Grounded code analysis.",
            provider="test",
            model="capture",
        )


class ExplodingLLM:
    def generate(self, messages, **kwargs):
        raise AssertionError("reflection should reuse grounded local-tool result")


def test_code_analyze_includes_bounded_real_source_evidence(tmp_path):
    source = (
        "from pathlib import Path\n\n"
        "class Example:\n"
        "    def start(self):\n"
        "        return 'START_SENTINEL'\n\n"
        + "# middle filler\n" * 1200
        + "\n    def finish(self):\n"
        "        return 'END_SENTINEL'\n"
    )
    path = tmp_path / "example.py"
    path.write_text(source, encoding="utf-8")

    manager = ToolManager(workspace_root=tmp_path)
    result = manager.registry.execute_validated(
        "code_analyze",
        {"path": "example.py"},
    )

    assert result.success is True
    analysis = result.result
    assert analysis.valid_syntax is True
    assert analysis.metadata["source_grounded"] is True
    assert analysis.metadata["source_truncated"] is True
    excerpt = analysis.metadata["source_excerpt"]
    assert "START_SENTINEL" in excerpt
    assert "END_SENTINEL" in excerpt
    assert "middle of source omitted" in excerpt
    assert any(
        symbol["name"] == "finish"
        for symbol in analysis.metadata["symbols"]
    )


def test_reasoning_applies_strict_local_tool_grounding_rules():
    llm = CaptureLLM()
    engine = ReasoningEngine(llm=llm)

    tool_evidence = {
        "local_tool": True,
        "tool_name": "code_analyze",
        "request": "analyze mary/memory/manager.py",
        "content": json.dumps(
            {
                "metadata": {
                    "source_grounded": True,
                    "source_excerpt": (
                        "Working memory is intentionally not persisted.\n"
                        "payload = {'episodic': [], 'semantic': []}"
                    ),
                    "source_truncated": False,
                }
            }
        ),
        "truncated": False,
    }

    context = CognitiveContext(
        input_text="analyze mary/memory/manager.py",
        relevant_knowledge=[tool_evidence],
    )

    result = engine.reason(context)

    assert result.metadata["local_tool_grounded"] is True
    assert len(llm.calls) == 1
    messages, kwargs = llm.calls[0]
    prompt = messages[-1].content
    assert "Local tool grounding rules" in prompt
    assert "Do not fill missing implementation details" in prompt
    assert "Never invent imports, attributes, method signatures" in prompt
    assert "Working memory is intentionally not persisted" in prompt
    assert kwargs["max_tokens"] == 1400


def test_reflection_reuses_local_tool_grounded_result_without_second_llm_call():
    engine = ReflectionEngine(llm=ExplodingLLM())
    context = CognitiveContext(input_text="analyze example.py")
    reasoning = ReasoningResult(
        response="Grounded analysis",
        metadata={"local_tool_grounded": True},
    )

    result = engine.reflect(context=context, reasoning=reasoning)

    assert result.decision == ReflectionDecision.ACCEPT
    assert result.metadata["mode"] == "local_tool_grounding_reuse"
