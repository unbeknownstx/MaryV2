from __future__ import annotations

from http.client import HTTPConnection
from pathlib import Path
from threading import Thread, RLock
from types import SimpleNamespace
import json

from mary.desktop.projects import CreativeWorkspaceManager
from mary.mobile.server import MaryMobileRuntime, MaryMobileServer, MobileAuth


ROOT = Path(__file__).resolve().parents[2]


class _FakeRuntime:
    def status(self):
        return {"name": "Mary"}

    def dashboard_state(self):
        return {"live": {"character": {"name": "Mary"}}}

    def last_turn_trace(self):
        return {}

    def close(self):
        pass


def _serve(tmp_path: Path):
    (tmp_path / "index.html").write_text("<html><head></head><body>Mary</body></html>", encoding="utf-8")
    server = MaryMobileServer(
        ("127.0.0.1", 0),
        runtime=_FakeRuntime(),
        static_root=tmp_path,
        auth=MobileAuth("secret", "test", None),
    )
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    return server, thread


def test_native_cors_accepts_file_origin_and_requires_token(tmp_path):
    server, thread = _serve(tmp_path)
    try:
        conn = HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
        conn.request(
            "OPTIONS",
            "/api/health",
            headers={"Origin": "null", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "Authorization"},
        )
        response = conn.getresponse()
        response.read()
        assert response.status == 204
        assert response.getheader("Access-Control-Allow-Origin") == "null"

        conn.request("GET", "/api/health", headers={"Origin": "null", "Authorization": "Bearer secret"})
        response = conn.getresponse()
        payload = json.loads(response.read())
        assert response.status == 200
        assert response.getheader("Access-Control-Allow-Origin") == "null"
        assert payload["ok"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_mobile_studio_is_sandboxed_to_configured_workspace(tmp_path):
    chapter = tmp_path / "chapter.md"
    chapter.write_text("original", encoding="utf-8")
    runtime = object.__new__(MaryMobileRuntime)
    runtime._lock = RLock()
    runtime.creative_workspace = CreativeWorkspaceManager(tmp_path)
    runtime.ecosystem = SimpleNamespace(publish_workspace_event=lambda *args, **kwargs: None)

    status = runtime.bridge_call("getCreativeWorkspaceState")
    assert status["configured"] is True
    assert any(item["path"] == "chapter.md" for item in status["files"])

    read = runtime.bridge_call("readCreativeTextFile", ["chapter.md"])
    assert read["ok"] is True
    assert read["content"] == "original"

    saved = runtime.bridge_call("saveCreativeTextFile", ["chapter.md", "from phone"])
    assert saved["ok"] is True
    assert chapter.read_text(encoding="utf-8") == "from phone"

    escaped = runtime.bridge_call("readCreativeTextFile", ["../outside.md"])
    assert escaped["ok"] is False


def test_mobile_ui_exposes_desktop_workspaces():
    html = (ROOT / "mobile_web" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "mobile_web" / "app.js").read_text(encoding="utf-8")
    for workspace in (
        "memories", "personality", "mind", "studio", "study", "stream",
        "gallery", "media", "voice", "runtime", "settings", "search", "research", "arcade",
    ):
        assert f'data-open="{workspace}"' in html
        assert workspace in js


def test_native_xcode_project_is_bundled_and_has_privacy_strings():
    native = ROOT / "mobile_native"
    assert (native / "MaryMobile.xcodeproj" / "project.pbxproj").is_file()
    assert (native / "MaryMobile" / "MaryMobileApp.swift").is_file()
    assert (native / "MaryMobile" / "MaryViewController.swift").is_file()
    bridge = (native / "MaryMobile" / "MaryNativeBridge.swift").read_text(encoding="utf-8")
    assert "SFSpeechRecognizer" in bridge
    assert "AVSpeechSynthesizer" in bridge
    assert "UIImpactFeedbackGenerator" in bridge
    plist = (native / "MaryMobile" / "Info.plist").read_text(encoding="utf-8")
    assert "NSMicrophoneUsageDescription" in plist
    assert "NSSpeechRecognitionUsageDescription" in plist
    assert "NSLocalNetworkUsageDescription" in plist
    assert (native / "MaryMobile" / "www" / "index.html").is_file()
