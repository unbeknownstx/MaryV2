from mary.conversation.cross_surface import CrossSurfaceAwareness, SurfaceNote


def test_cross_surface_awareness_exposes_elsewhere_without_merging_current_surface():
    awareness = CrossSurfaceAwareness(capacity=16)
    awareness.record(surface="desktop", direction="outbound", role="mary", summary="We were comparing storyboard versions.")
    awareness.record(surface="mobile", direction="inbound", role="creator", summary="What were we doing?")
    elsewhere = awareness.elsewhere("mobile")
    assert len(elsewhere) == 1
    assert elsewhere[0]["surface"] == "desktop"
    assert elsewhere[0]["summary"] == "We were comparing storyboard versions."
    assert "canonical" in awareness.snapshot()["policy"].lower()


def test_cross_surface_awareness_coalesces_adjacent_duplicate_notes():
    awareness = CrossSurfaceAwareness(capacity=16)
    awareness.record(surface="desktop", direction="outbound", role="mary", summary="Same beat")
    awareness.record(surface="desktop", direction="outbound", role="mary", summary="Same beat")
    assert awareness.snapshot()["count"] == 1


def test_public_surface_never_receives_private_stage_note_content():
    awareness = CrossSurfaceAwareness(capacity=16)
    awareness.record(surface="mobile", direction="inbound", role="creator", summary="private phone topic", visibility="private")
    awareness.record(surface="desktop", direction="event", role="environment", summary="stream started", visibility="public")
    notes = awareness.elsewhere("stream", current_visibility="public", limit=8)
    assert [item["summary"] for item in notes] == ["stream started"]
