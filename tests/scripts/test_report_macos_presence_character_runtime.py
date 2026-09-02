from scripts.report_macos_presence import ForegroundContext, foreground_context, publish


class _Client:
    def __init__(self):
        self.calls = []

    def runtime_action(self, action, args=None):
        self.calls.append((action, args))
        return {"ok": True}


def test_foreground_context_falls_back_when_window_title_is_not_allowed():
    calls = []

    def runner(script):
        calls.append(script)
        if "front window" in script:
            raise RuntimeError("accessibility denied")
        return "Safari"

    context = foreground_context(runner=runner)
    assert context == ForegroundContext("Safari", "")
    assert len(calls) == 2


def test_publish_uses_bounded_non_authoritative_presence_action():
    client = _Client()
    result = publish(client, ForegroundContext("Adobe Photoshop", "Mary concept.psd"))
    assert result["ok"] is True
    action, args = client.calls[0]
    assert action == "presence.observe"
    assert args["event_type"] == "foreground_app"
    assert args["metadata"]["platform"] == "macos"
    assert "Mary concept.psd" in args["summary"]
