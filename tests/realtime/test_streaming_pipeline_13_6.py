from mary.realtime.streaming import GenerationDelta, SentenceStreamAssembler, TurnCancellation, segment_deltas


def test_fragmented_deltas_reconstruct_exact_text_and_emit_sentences():
    text = "Mary is here. She can speak while the rest is still generating! Right?"
    deltas = [text[:8], text[8:21], text[21:39], text[39:55], text[55:]]
    segments = list(segment_deltas(deltas))
    assert "".join(segment.text for segment in segments) == text
    assert len(segments) >= 3
    assert [segment.sequence for segment in segments] == list(range(len(segments)))


def test_decimal_and_abbreviation_do_not_split_early():
    assembler = SentenceStreamAssembler()
    assert assembler.feed("Dr. Mary measured 3.14 seconds. ")
    segments = assembler.finish()
    # The completed sentence is emitted as one unit despite abbreviation/decimal punctuation.
    all_text = assembler.reconstructed_text
    assert all_text == "Dr. Mary measured 3.14 seconds. "
    assert segments == []


def test_one_shot_completion_uses_same_pipeline():
    text = "One shot still works. No provider streaming required."
    segments = list(segment_deltas([GenerationDelta(text=text, sequence=0, final=True)]))
    assert "".join(segment.text for segment in segments) == text


def test_cancellation_stops_future_generation_segments():
    cancellation = TurnCancellation()

    def source():
        yield "First sentence. "
        cancellation.cancel("microphone_barge_in")
        yield "This must never be spoken."

    segments = list(segment_deltas(source(), cancellation=cancellation))
    assert "".join(segment.text for segment in segments) == "First sentence. "
    assert cancellation.reason == "microphone_barge_in"
