from types import SimpleNamespace

import mary.mobile.server as mobile_server


class FakeRemoteClient:
    def __init__(self, base_url, *, token, device_id, timeout=120.0):
        self.base_url = base_url
        self.token = token
        self.device_id = device_id
    def state(self):
        return {"core": {"architecture": "13.2"}, "mary": {"name": "Mary"}, "nodes": {"nodes": []}}
    def conversation_status(self):
        return {"engagement": {"mode": "adaptive"}, "realtime": {"phase": "idle"}}
    def growth_status(self):
        return {"version": "13.0"}
    def nodes(self):
        return {"nodes": []}
    def turn(self, text, *, conversation_id=None, requested_mode=None, voice_input=False):
        return SimpleNamespace(
            response="hello from core",
            turn_id="turn-1",
            provenance={"provider": "groq"},
            conversation_state=self.conversation_status(),
            display_hints={"delivery_plan": {}, "dialogue_plan": {}},
            state_changes={},
        )


def test_remote_mobile_runtime_does_not_construct_local_mary(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_server, "MaryClient", FakeRemoteClient)
    monkeypatch.setenv("MARY_MOBILE_PROXY_DATA_DIR", str(tmp_path / "proxy"))
    monkeypatch.setattr(mobile_server, "create_application", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not construct Mary")))
    runtime = mobile_server.MaryRemoteMobileRuntime("https://core.example", token="secret", device_id="iphone")
    payload = runtime.chat("hi")
    assert payload["text"] == "hello from core"
    assert payload["runtime"]["trace"]["authority"] == "remote_mary_core"
    assert runtime.status()["mobile"]["authority"] == "remote_mary_core"
