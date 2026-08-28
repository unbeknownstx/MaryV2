from __future__ import annotations

from mary.core.config import Config
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.llm.output_quality import inspect_output_quality
from mary.llm.router import LLMRouter


class ContentProvider(LLMInterface):
    def __init__(self, name: str, content: str):
        self.name = name
        self.content = content
        self.calls = 0

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        return LLMResponse(content=self.content, provider=self.name, model="fake")

    def is_available(self):
        return True

    def provider_name(self):
        return self.name

    def model_name(self):
        return "fake"


def test_unrequested_mixed_script_is_rejected():
    issue = inspect_output_quality(
        "쨩. Just a㣩/癞넴 conversation, then.",
        [LLMMessage(role="user", content="not much just want to have a conversation with you")],
    )
    assert issue is not None
    assert issue.code in {"unexpected_script", "mixed_script_fragment"}


def test_legitimate_translation_request_allows_requested_script():
    issue = inspect_output_quality(
        "こんにちは",
        [LLMMessage(role="user", content="translate hello into japanese")],
    )
    assert issue is None


def test_corrupt_provider_output_fails_over_before_reaching_mary():
    config = Config()
    config.llm.provider = "primary"
    config.llm.fallback_providers = ["secondary"]
    config.llm.routing_strategy = "configured"
    router = LLMRouter(config)
    bad = ContentProvider("primary", "쨩. Just a㣩/癞넴 conversation, then.")
    good = ContentProvider("secondary", "Just a conversation, then. I'm here with you.")
    router.register_provider("primary", bad)
    router.register_provider("secondary", good)

    response = router.generate([
        LLMMessage(role="user", content="not much just want to have a conversation with you"),
    ])

    assert response.provider == "secondary"
    assert "癞" not in response.content
    assert bad.calls == 1
    assert good.calls == 1
    assert router.last_generation_attempts[0]["status"] == "invalid_output"
    assert router.last_generation_attempts[-1]["status"] == "success"


def test_classifier_label_leakage_is_rejected():
    issue = inspect_output_quality(
        "User Safety: safe",
        [LLMMessage(role="user", content="hey Mary what's up")],
    )
    assert issue is not None
    assert issue.code == "classifier_leakage"


def test_classifier_label_block_leakage_is_rejected():
    issue = inspect_output_quality(
        "User Safety: safe\nResponse Safety: safe",
        [LLMMessage(role="user", content="what have you learned about me from our recent conversations?")],
    )
    assert issue is not None
    assert issue.code == "classifier_leakage"


def test_classifier_words_inside_real_dialogue_are_not_rejected():
    issue = inspect_output_quality(
        "The diagnostic showed User Safety: safe, but that isn't my answer to you.",
        [LLMMessage(role="user", content="explain the diagnostic output")],
    )
    assert issue is None


def test_classifier_label_block_leakage_fails_over_before_reaching_mary():
    config = Config()
    config.llm.provider = "primary"
    config.llm.fallback_providers = ["secondary"]
    config.llm.routing_strategy = "configured"
    router = LLMRouter(config)
    leaked = ContentProvider("primary", "User Safety: safe\nResponse Safety: safe")
    good = ContentProvider("secondary", "You've shared several grounded things with me recently.")
    router.register_provider("primary", leaked)
    router.register_provider("secondary", good)

    response = router.generate([
        LLMMessage(role="user", content="what have you learned about me from our recent conversations?"),
    ])

    assert response.provider == "secondary"
    assert response.content == "You've shared several grounded things with me recently."
    assert router.last_generation_attempts[0]["status"] == "invalid_output"


def test_classifier_label_leakage_fails_over_before_reaching_mary():
    config = Config()
    config.llm.provider = "primary"
    config.llm.fallback_providers = ["secondary"]
    config.llm.routing_strategy = "configured"
    router = LLMRouter(config)
    leaked = ContentProvider("primary", "User Safety: safe")
    good = ContentProvider("secondary", "Not much. I'm here with you.")
    router.register_provider("primary", leaked)
    router.register_provider("secondary", good)

    response = router.generate([
        LLMMessage(role="user", content="hey Mary what's up"),
    ])

    assert response.provider == "secondary"
    assert response.content == "Not much. I'm here with you."
    assert router.last_generation_attempts[0]["status"] == "invalid_output"
