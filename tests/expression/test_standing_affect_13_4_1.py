from mary.expression.standing_affect import StandingAffectStore


class State:
    valence = 0.0
    arousal = 0.0
    intensity = 0.2
    metadata = {}


def test_standing_affect_persists_and_is_derived(tmp_path):
    path = tmp_path / "standing.json"
    store = StandingAffectStore(path, half_life_seconds=600)
    store.observe(valence=.8, arousal=.6, intensity=.9, source="conversation")
    again = StandingAffectStore(path, half_life_seconds=600)
    assert again.load()
    snap = again.snapshot()
    assert snap["valence"] > 0
    assert snap["authority"] == "derived expressive continuity only"


def test_weak_attribution_never_becomes_person_standing(tmp_path):
    store = StandingAffectStore(tmp_path / "a.json")
    state = store.observe(
        valence=-.8,
        arousal=.8,
        source="stream",
        attributed_person="viewer42",
        attribution_confidence=.4,
    )
    assert state.attributed_person is None
