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


def test_environment_fast_brain_late_binds_capability_provider_after_core_start(monkeypatch):
    from types import SimpleNamespace
    from mary.mind.fast_brain import fast_brain_from_environment

    class Provider:
        def __init__(self):
            self.available = False

        def is_available(self):
            return self.available

        def generate(self, messages, temperature=.7, max_tokens=2048):
            return SimpleNamespace(content="respond", provider="llama_cpp", model="mac-tiny")

    class Router:
        def __init__(self, provider):
            self.provider = provider

        def get_provider(self, name):
            assert name == "llama_cpp"
            return self.provider

    provider = Provider()
    mary = SimpleNamespace(llm=Router(provider))
    monkeypatch.setenv("MARY_FAST_BRAIN_PROVIDER", "llama_cpp")
    brain = fast_brain_from_environment(mary)
    request = FastBrainRequest(
        task="stream_attention",
        text="Mary check this out?",
        labels=("ignore", "notice", "respond"),
    )

    before = brain.classify(request)
    provider.available = True
    after = brain.classify(request)

    assert before.provider == "deterministic"
    assert after.provider == "llama_cpp"
    assert after.model == "mac-tiny"
    assert after.label == "respond"
