from mary.distributed.resource_profile import RuntimeResourceProfile


def test_resource_profile_is_capability_hint_only():
    profile = RuntimeResourceProfile.detect().to_dict()
    assert profile["authority"] == "capability_hint_only"
    assert profile["cpu_count"] >= 1
