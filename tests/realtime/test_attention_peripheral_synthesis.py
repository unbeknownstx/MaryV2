from mary.realtime import AttentionBus, AttentionDisposition, AttentionSource


def test_attention_direct_address_reacts_and_noise_drops():
    bus = AttentionBus()
    direct = bus.judge(AttentionSource.BACKGROUND, importance=0.1, addressed=True)
    noise = bus.judge(AttentionSource.BACKGROUND, importance=1.0, noise=True)
    assert direct.disposition == AttentionDisposition.REACT
    assert direct.score >= 0.82
    assert noise.disposition == AttentionDisposition.DROP


def test_peripheral_notes_dedupe_rank_and_consume():
    bus = AttentionBus()
    one = bus.note_peripheral(AttentionSource.BACKGROUND, "Chat keeps mentioning the purple beanie", importance=.62, dedupe_key="beanie")
    repeated = bus.note_peripheral(AttentionSource.BACKGROUND, "Chat keeps mentioning the purple beanie", importance=.7, dedupe_key="beanie")
    other = bus.note_peripheral(AttentionSource.VISUAL, "A window changed", importance=.4)
    assert one.note_id == repeated.note_id
    assert repeated.times_seen == 2
    ranked = bus.peripheral(limit=2)
    assert ranked[0].note_id == one.note_id
    assert bus.claim_peripheral([one.note_id]) == 1
    assert [item.note_id for item in bus.peripheral(limit=5)] == [other.note_id]
