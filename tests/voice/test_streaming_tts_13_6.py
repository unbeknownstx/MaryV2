from time import sleep

from mary.realtime.streaming import SentenceSegment, TurnCancellation
from mary.voice.streaming_tts import SentenceSpeechScheduler


def test_synthesis_may_finish_out_of_order_but_playback_is_ordered():
    segments = [SentenceSegment("slow", 0), SentenceSegment("fast", 1), SentenceSegment("last", 2, True)]
    played = []

    def synth(text):
        if text == "slow":
            sleep(0.02)
        return text.upper()

    result = SentenceSpeechScheduler(max_workers=3, max_pending=3).run(
        segments, synthesize=synth, play=played.append
    )
    assert played == ["SLOW", "FAST", "LAST"]
    assert [item.sequence for item in result] == [0, 1, 2]


def test_barge_in_cancels_future_playback():
    cancellation = TurnCancellation()
    played = []

    def play(payload):
        played.append(payload)
        cancellation.cancel("barge_in")

    SentenceSpeechScheduler(max_workers=2, max_pending=2).run(
        [SentenceSegment("one", 0), SentenceSegment("two", 1), SentenceSegment("three", 2)],
        synthesize=lambda text: text,
        play=play,
        cancellation=cancellation,
    )
    assert played == ["one"]
    assert cancellation.cancelled
