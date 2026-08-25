from pathlib import Path
from mary.mobile.server import MOBILE_PROTOCOL_VERSION

ROOT = Path(__file__).resolve().parents[2]


def test_mobile_protocol_and_realtime_bridge_are_packaged():
    server = (ROOT / "mary/mobile/server.py").read_text(encoding="utf-8")
    app = (ROOT / "mobile_web/app.js").read_text(encoding="utf-8")
    native = (ROOT / "mobile_native/MaryMobile/www/app.js").read_text(encoding="utf-8")
    worker = (ROOT / "mobile_web/sw.js").read_text(encoding="utf-8")
    assert MOBILE_PROTOCOL_VERSION == "4"
    for name in ("getRealtimeState", "getAttentionState", "getNodeState", "getRetrievalState", "reportSpeechStarted", "reportSpeechEnded", "reportSpeechInterrupted", "rebuildSemanticVectors", "recordResponseFeedback", "getTrainingFeedbackState"):
        assert name in server
    assert "REALTIME INTERACTION" in app
    assert "ATTENTION BUS" in app
    assert "HYBRID MEMORY RETRIEVAL" in app
    assert "COMPUTE NODES" in app
    assert "MARY EVALUATION SET" in app
    assert "data-response-feedback" in app
    assert "maryv2-mobile-shell-v13-1" in worker
    assert app == native
