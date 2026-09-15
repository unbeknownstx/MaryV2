from mary.realtime.presentation_session import PresentationSessionManager


def test_interrupt_invalidates_all_registered_presentation_effects():
    mgr = PresentationSessionManager()
    s = mgr.start(turn_id="turn_1")
    cancelled = []
    assert mgr.register_cancel(s.id, cancelled.append)
    assert mgr.accepts(s.id)
    assert mgr.interrupt(reason="barge_in") == s.id
    assert not mgr.accepts(s.id)
    assert cancelled == ["barge_in"]


def test_stale_finish_cannot_end_newer_session():
    mgr = PresentationSessionManager()
    old = mgr.start(turn_id="old")
    new = mgr.start(turn_id="new")
    assert not mgr.finish(old.id)
    assert mgr.accepts(new.id)
