from mary.runtime.performance_hardening import PerformanceHardeningBundle


class DummyPaths:
    def __init__(self, root):
        self.relationship = root


class DummyConfig:
    def __init__(self, root):
        self.paths = DummyPaths(root)


class DummyRelationshipHistory:
    events = []

    def get_shared_experiences(self):
        return []


class DummyRelationship:
    def __init__(self):
        self.history = DummyRelationshipHistory()

    def profile(self):
        return {}


class DummyProfiles:
    def status(self):
        return {"enabled": True}


class DummyMary:
    def __init__(self, root):
        self.config = DummyConfig(root)
        self.relationship = DummyRelationship()
        self.performance_profiles = DummyProfiles()


def test_bundle_exposes_relational_presence_and_delivery(tmp_path):
    bundle = PerformanceHardeningBundle(DummyMary(tmp_path))
    snapshot = bundle.snapshot()
    assert snapshot["version"] == "13.8"
    assert snapshot["relational_presence"]["relationship_mode"] == "friend"
    assert snapshot["social_delivery"]["authority"] == "delivery_projection_only"
