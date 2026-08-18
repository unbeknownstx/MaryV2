from __future__ import annotations

from mary.core.mary import Mary
from mary.expression.emotion import Emotion
from mary.llm.interface import LLMResponse


class StaticProvider:
    name = "static"
    model = "static"

    def generate(self, messages, **kwargs):
        return LLMResponse(
            content="I'm curious where you want to take that next.",
            provider=self.name,
            model=self.model,
            finish_reason="stop",
            usage={},
        )


def test_completed_turn_updates_shared_emotion_state_without_second_llm_call(tmp_path) -> None:
    mary = Mary()
    provider = StaticProvider()
    mary.llm.providers["static"] = provider
    mary.llm.config.llm.provider = "static"

    result = mary.process("What do you think about this idea?")

    assert mary.emotion.state.primary == Emotion.CURIOSITY
    assert result.metadata["emotion_appraisal"]["emotion"] == "curiosity"
    assert mary.avatar.emotion_manager is mary.emotion
