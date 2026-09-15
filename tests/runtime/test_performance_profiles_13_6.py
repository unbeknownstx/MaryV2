from mary.runtime.performance_profiles import RuntimePerformanceProfiles


def test_runtime_profiles_tune_resources_not_identity():
    profiles = RuntimePerformanceProfiles()
    fast = profiles.set("performance")
    status = profiles.status()
    assert fast.tts_chunk_chars < status["available"]["light"]["tts_chunk_chars"]
    assert status["authority"] == "mary_core_runtime_policy"
    assert status["identity_switch"] is False
