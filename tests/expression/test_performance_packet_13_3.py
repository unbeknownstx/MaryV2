from mary.expression.performance_packet import build_performance_packet


def test_performance_packet_keeps_canonical_display_and_separate_spoken_variant():
    packet = build_performance_packet("OpenAI costs $10.50.", None)
    payload = packet.to_dict()
    assert payload["text"] == "OpenAI costs $10.50."
    assert payload["display_text"] == payload["text"]
    assert payload["spoken_text"]
    assert payload["spoken_text"] != ""
    assert packet.text == "OpenAI costs $10.50."
