from types import SimpleNamespace

from mary.cognition.self_introspection import SelfIntrospection


class _Tools:
    def __init__(self, *, web: bool) -> None:
        self.web = web

    def status(self):
        return {
            "registered": 4,
            "web_search_configured": self.web,
            "web_search_provider": "test-search",
            "workspace_root": "/bounded/workspace",
            "repository_map": {"registered": True, "execution": False, "mutation": False},
        }


class _Registry:
    def snapshot(self):
        return {
            "registered": 2,
            "nodes": [
                {
                    "node_id": "desktop-ready",
                    "display_name": "Desktop",
                    "platform": "windows",
                    "connected": True,
                    "capabilities": {
                        "llm.ollama": {
                            "available": True,
                            "readiness": "ready",
                            "metadata": {"execution_authorized": True},
                        },
                        "sensor.screen_describe": {
                            "available": True,
                            "readiness": "ready",
                            "metadata": {"execution_authorized": False},
                        },
                    },
                },
                {
                    "node_id": "old-mac",
                    "platform": "macos",
                    "connected": False,
                    "capabilities": {
                        "llm.ollama": {
                            "available": True,
                            "readiness": "ready",
                            "metadata": {"execution_authorized": True},
                        }
                    },
                },
            ],
        }


def _introspection(*, web: bool = True, registry=None):
    value = object.__new__(SelfIntrospection)
    value.tools = _Tools(web=web)
    value.node_registry = registry
    value.agency = SimpleNamespace(status=lambda: {"active": True})
    value.autonomy = SimpleNamespace()
    return value


def test_capability_introspection_uses_live_tools_and_connected_nodes():
    evidence = _introspection(registry=_Registry())._capabilities()
    live = evidence["live_capabilities"]

    assert live["web_search"]["available"] is True
    assert live["nodes"]["connected"] == 1
    assert live["nodes"]["registered"] == 2
    assert live["nodes"]["advertised_capabilities"] == ["llm.ollama", "sensor.screen_describe"]
    assert live["nodes"]["execution_ready_capabilities"] == ["llm.ollama"]
    assert evidence["authority"].startswith("live Core/tool/node state is authoritative")
    assert "provider model priors are not capability evidence" in evidence["authority"]


def test_capability_introspection_does_not_invent_browse_or_device_execution():
    evidence = _introspection(web=False, registry=None)._capabilities()
    live = evidence["live_capabilities"]

    assert live["web_search"]["available"] is False
    assert live["nodes"]["connected"] == 0
    assert live["nodes"]["advertised_capabilities"] == []
    assert "Web search is not currently configured" in evidence["fallback_response"]
    assert "do not currently have a connected capability node" in evidence["fallback_response"]
