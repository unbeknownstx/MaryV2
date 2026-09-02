from mary.mind.fast_brain import DeterministicFastBrain, FastBrainRequest


def test_fast_brain_is_small_decision_not_character_authority():
    brain = DeterministicFastBrain()
    result = brain.classify(FastBrainRequest(task="stream_attention", text="Mary what do you think about this?"))
    assert result.label == "respond"
    assert result.confidence >= .68


def test_provider_fast_brain_returns_only_allowed_label():
    from types import SimpleNamespace
    from mary.mind.fast_brain import FastBrainRequest, ProviderFastBrain

    class Provider:
        def generate(self, messages, temperature=.7, max_tokens=2048):
            return SimpleNamespace(content="respond", provider="llama_cpp", model="tiny")

    result = ProviderFastBrain(Provider()).classify(
        FastBrainRequest(
            task="stream_attention",
            text="Mary check this out",
            labels=("ignore", "notice", "respond"),
        )
    )
    assert result.label == "respond"
    assert result.provider == "llama_cpp"
    assert result.metadata["authority"] == "ranking_only"


def test_provider_fast_brain_falls_back_to_first_allowed_label_on_freeform_output():
    from types import SimpleNamespace
    from mary.mind.fast_brain import FastBrainRequest, ProviderFastBrain

    class Provider:
        def generate(self, messages, temperature=.7, max_tokens=2048):
            return SimpleNamespace(content="I cannot decide", provider="test", model="tiny")

    result = ProviderFastBrain(Provider()).classify(
        FastBrainRequest(task="attention", text="x", labels=("ignore", "respond"))
    )
    assert result.label == "ignore"
    assert result.confidence < .5
