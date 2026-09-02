from mary.realtime import SpeechDisposition, SpeechOutputArbiter, SpeechRequest


def test_speech_arbiter_queues_and_interrupts_one_floor():
    arbiter = SpeechOutputArbiter()
    first = SpeechRequest("first", priority=50, interruptible=True)
    assert arbiter.request(first).disposition == SpeechDisposition.PLAY

    queued = SpeechRequest("later", priority=60)
    assert arbiter.request(queued).disposition == SpeechDisposition.QUEUE

    urgent = SpeechRequest("creator barge-in reaction", priority=10, can_interrupt=True)
    decision = arbiter.request(urgent)
    assert decision.disposition == SpeechDisposition.INTERRUPT
    assert decision.interrupted_request_id == first.id
    assert arbiter.active.id == urgent.id


def test_speech_arbiter_promotes_queue_after_completion():
    arbiter = SpeechOutputArbiter()
    first = SpeechRequest("first")
    second = SpeechRequest("second")
    arbiter.request(first)
    arbiter.request(second)
    next_item = arbiter.finish_active(first.id)
    assert next_item is not None
    assert next_item.id == second.id
