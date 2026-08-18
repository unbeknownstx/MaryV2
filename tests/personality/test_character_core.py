from mary.core.mary import Mary


def test_character_core_is_connected_to_live_mary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    assert mary.self_model.preferences is mary.preferences
    assert mary.personality.get_trait("sociability") >= 0.9
    assert mary.personality.get_trait("artistic_sensitivity") >= 0.9
    assert mary.character.get_behavior("bubbliness") >= 0.9
    assert "twinnn" in mary.character.get_speech()["vocabulary"]
    assert "abandonment" in mary.character.get_vulnerabilities()["fears"]
    assert mary.character.get_romance()["orientation"] == "hopeless romantic"


def test_character_core_appearance_is_structured_biography(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    expected = {
        "Height": "5'5\" to 5'6\"",
        "Hair color": "red",
        "Eye color": "blue",
        "Signature headwear": "purple beanie",
        "Signature jacket": "blue jacket",
        "Signature shirt": "purple shirt",
        "Signature skirt": "blue skirt",
        "Signature socks": "knee-high socks",
        "Signature footwear": "boots",
    }

    for title, content in expected.items():
        entry = mary.biography.get("appearance", title)
        assert entry is not None
        assert entry.content == content


def test_authored_preferences_are_real_mary_state_without_fake_favorite_color(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    assert mary.preferences.get_preference("drawing")["polarity"] > 0
    assert mary.preferences.get_preference("banter")["strength"] >= 0.9
    assert mary.preferences.get_preference("shrimp")["polarity"] < 0
    assert mary.preferences.get_preference("liver")["polarity"] < 0
    assert not any(
        item.get("category") == "favorite_color"
        for item in mary.preferences.get_preferences()
    )


def test_turn_mind_carries_character_expression_without_copying_creator(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    intent = mary.cognition.detect_intent("Hey Mary")
    mind = mary.turn_mind.build(
        input_text="Hey Mary",
        intent=intent,
        relevant_memories=[],
        recent_conversation=[],
    ).prompt_view()

    assert "speech" in mind["character"]
    assert "reactions" in mind["character"]
    assert "vulnerabilities" in mind["character"]
    assert mind["preferences"]
    assert any(item["name"] == "banter" for item in mind["preferences"])


def test_personal_goals_are_separate_from_runtime_purpose(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    goals = {
        entry.title: entry.content
        for entry in mary.biography.get_category("goals")
    }

    assert "Purpose" in goals
    assert "Homestead" in goals
    assert "Love" in goals
    assert "Travel" in goals
    assert "Justice" in goals
