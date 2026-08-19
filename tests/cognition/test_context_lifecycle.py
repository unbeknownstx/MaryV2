from __future__ import annotations

from mary.cognition.context_lifecycle import ConversationContextLifecycle
from mary.core.mary import Mary
from mary.llm.interface import LLMResponse


class EchoSequenceRouter:
    def __init__(self):
        self.calls = []
        self.counter = 0

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        self.counter += 1
        system = str(messages[0].content) if messages else ""
        if "Mary's response editor" in system:
            return LLMResponse(
                content="Yeah, I remember the thread. I'm keeping it compact instead of replaying everything.",
                provider="test",
                model="fake",
            )
        return LLMResponse(
            content=f"Turn {self.counter}: I'm following you without dragging the whole transcript forward.",
            provider="test",
            model="fake",
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "fake"

    def is_available(self, provider=None):
        return True


def _mary(router: EchoSequenceRouter | None = None) -> Mary:
    mary = Mary()
    router = router or EchoSequenceRouter()
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    return mary


def test_context_lifecycle_keeps_newest_complete_turns_under_budget():
    lifecycle = ConversationContextLifecycle(
        max_turns=2,
        max_characters=1_000,
        max_message_characters=300,
        max_anchors=2,
        anchor_characters=80,
    )
    history = []
    for index in range(5):
        history.extend([
            {"role": "user", "content": f"user turn {index} " + ("u" * 120)},
            {"role": "assistant", "content": f"mary turn {index} " + ("m" * 120)},
        ])

    window = lifecycle.select(history)
    result = window.to_dict()

    assert result["selected_messages"] == 4
    assert result["dropped_messages"] == 6
    assert result["selected_characters"] <= 1_000
    assert result["anchors"]
    assert len(result["anchors"]) <= 2
    assert window.messages[0]["content"].startswith("user turn 3")
    assert window.messages[-1]["content"].startswith("mary turn 4")


def test_long_session_llm_context_stays_bounded_and_exposes_ephemeral_anchors():
    router = EchoSequenceRouter()
    mary = _mary(router)

    for index in range(12):
        mary.process(
            f"Session topic {index}: "
            + ("I'm explaining a deliberately long conversational detail. " * 8)
        )

    result = mary.process("Okay, keep following the thread without replaying everything.")
    lifecycle = result.context.mind_state["conversation"]["lifecycle"]

    assert lifecycle["selected_messages"] <= 8
    assert lifecycle["selected_characters"] <= lifecycle["max_characters"]
    assert lifecycle["dropped_messages"] > 0
    assert 1 <= len(lifecycle["anchors"]) <= 3
    assert lifecycle["promotion_policy"] == "explicit_or_existing_development_paths_only"
    assert len(result.context.conversation) <= 8

    messages, _kwargs = router.calls[-1]
    combined = "\n".join(str(message.content) for message in messages)
    assert "Earlier session anchors" in combined
    # The prompt should remain bounded even after many deliberately verbose turns.
    assert len(combined) < 22_000


def test_ordinary_conversation_does_not_auto_promote_into_durable_memory():
    mary = _mary()
    before_episodic = len(mary.memory.episodic.all())
    before_semantic = len(mary.memory.semantic.all())

    result = mary.process("I had pancakes this morning and the weather was nice.")

    assert len(mary.memory.episodic.all()) == before_episodic
    assert len(mary.memory.semantic.all()) == before_semantic
    lifecycle = result.context.mind_state["conversation"]["lifecycle"]
    assert lifecycle["promotion_policy"] == "explicit_or_existing_development_paths_only"


def test_context_lifecycle_is_connected_as_a_mary_cognition_component():
    mary = _mary()
    assert mary.context_lifecycle is not None
    status = mary.status()
    assert status["cognition"]["context_lifecycle"] is True
