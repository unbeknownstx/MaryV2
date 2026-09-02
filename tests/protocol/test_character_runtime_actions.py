from mary.protocol.models import RuntimeActionRequest


def test_character_runtime_actions_are_typed_protocol_actions():
    for name in (
        "presence.scene.status",
        "presence.observe",
        "perception.status",
        "perception.observe",
        "stream.status",
        "stream.chat.ingest",
        "world.status",
        "world.ingest",
        "world.refresh_plan",
        "realtime.speech_request",
        "model.adapter.status",
    ):
        request = RuntimeActionRequest.from_dict({"action": name, "args": {}, "device_id": "test"})
        assert request.action == name
