from __future__ import annotations

from mary.desktop import device_node as device_module
from mary.distributed import CapabilityDescriptor


class FakeGateway:
    device_id = "node-test"

    def register_node(self, **payload):
        self.payload = payload
        return {"ok": True}

    def heartbeat_node(self):
        return {"ok": True}

    def disconnect_node(self):
        return {"ok": True}


def test_explicit_headless_capabilities_do_not_require_desktop_application():
    capability = CapabilityDescriptor(
        name="llm.ollama",
        available=True,
        private=True,
        local=True,
    )
    gateway = FakeGateway()
    agent = device_module.DesktopCapabilityNodeAgent(
        gateway,
        capabilities=[capability],
        host_type="capability_node",
        surface="windows_node",
    )
    payload = agent.registration_payload()
    assert payload["host_type"] == "capability_node"
    assert payload["surface"] == "windows_node"
    assert [item["name"] for item in payload["capabilities"]] == ["llm.ollama"]


def test_headless_ollama_capabilities_advertises_nothing_when_ollama_missing(monkeypatch):
    monkeypatch.setattr(device_module, "_ollama_capability", lambda: None)
    assert device_module.headless_ollama_capabilities() == []
