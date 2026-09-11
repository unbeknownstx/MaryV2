from mary.avatar.transport_guard import SerializedRequestReplyTransport, normalized_mouth_level


def test_transport_returns_matching_reply():
    calls = []
    t = SerializedRequestReplyTransport(lambda p: calls.append(p) or {"request_id": p["request_id"]})
    assert t.call({"request_id": "a"})["request_id"] == "a"
    assert t.sequence == 1


def test_quiet_audio_opens_less_than_loud_audio():
    quiet = normalized_mouth_level(rms=.01, peak=.03)
    loud = normalized_mouth_level(rms=.2, peak=.5)
    assert quiet < loud
