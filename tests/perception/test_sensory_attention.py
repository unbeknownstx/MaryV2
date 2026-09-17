from mary.perception import SensoryAttentionController


def test_private_mode_does_not_grant_screen_or_camera_ambient_access():
    senses = SensoryAttentionController()
    assert senses.allowed("microphone", mode="private") is True
    assert senses.allowed("photo", mode="private") is True
    assert senses.allowed("screen", mode="private") is False
    assert senses.allowed("camera", mode="private", explicit_consent=True) is False


def test_attention_inspects_meaningful_changes_not_duplicate_frames():
    senses = SensoryAttentionController()
    first = senses.should_inspect(source_id="desktop", change_signature="frame-a", importance=0.7)
    same = senses.should_inspect(source_id="desktop", change_signature="frame-a", importance=0.9)
    changed = senses.should_inspect(source_id="desktop", change_signature="frame-b", importance=0.7)
    assert first["inspect"] is True
    assert same["inspect"] is False
    assert changed["inspect"] is True


def test_mary_or_creator_can_request_inspection_without_change_trigger():
    senses = SensoryAttentionController()
    mary = senses.should_inspect(source_id="window", change_signature="same", requested_by_mary=True)
    creator = senses.should_inspect(source_id="window", change_signature="same", creator_requested=True)
    assert mary["reason"] == "mary_requested"
    assert creator["reason"] == "creator_requested"


def test_observation_projection_is_ephemeral_environment_context():
    context = SensoryAttentionController.observation_context({
        "id": "observation_1",
        "modality": "screen",
        "source": "windows_node",
        "description": "VS Code shows a failing test.",
        "confidence": 0.91,
    })
    assert context["authority"] == "environment_context_only"
    assert context["durable"] is False
    assert context["description"] == "VS Code shows a failing test."
