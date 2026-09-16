from __future__ import annotations

from mary.desktop import runtime_supervisor


def test_creator_desktop_local_compute_auto_authorize_defaults_on(monkeypatch, tmp_path):
    monkeypatch.delenv("MARY_DESKTOP_LOCAL_COMPUTE_AUTO_AUTHORIZE", raising=False)
    monkeypatch.delenv("MARY_DESKTOP_LOCAL_COMPUTE", raising=False)
    assert runtime_supervisor._env_bool("MARY_DESKTOP_LOCAL_COMPUTE", True) is True
    assert runtime_supervisor._env_bool("MARY_DESKTOP_LOCAL_COMPUTE_AUTO_AUTHORIZE", True) is True


def test_creator_can_explicitly_disable_local_compute_auto_authorize(monkeypatch):
    monkeypatch.setenv("MARY_DESKTOP_LOCAL_COMPUTE_AUTO_AUTHORIZE", "false")
    assert runtime_supervisor._env_bool("MARY_DESKTOP_LOCAL_COMPUTE_AUTO_AUTHORIZE", True) is False


def test_product_auto_authorize_is_scoped_to_llm_local_only():
    source = (runtime_supervisor.PathConfig().root / "mary" / "desktop" / "runtime_supervisor.py").read_text(encoding="utf-8")
    assert 'permissions.allow("llm.local")' in source
    assert 'permissions.allow("filesystem")' not in source
    assert 'permissions.allow("personal_search")' not in source
    assert 'permissions.allow("desktop_apps")' not in source

def test_existing_ollama_can_enable_desktop_node_without_auto_authorizing_ollama(monkeypatch):
    class _UnavailableLocal:
        def __init__(self, role="conversation"):
            self.role = role

        def runtime_status(self):
            return {
                "available": False,
                "runtime": "",
                "model": "",
                "role": self.role,
            }

    monkeypatch.setattr(runtime_supervisor, "ensure_lm_studio_runtime", lambda: {
        "runtime": "lm_studio",
        "ready": False,
        "state": "cli_not_found",
    })
    monkeypatch.setattr(runtime_supervisor, "LocalRuntimeProvider", _UnavailableLocal)
    monkeypatch.setattr(
        runtime_supervisor,
        "_available_local_llm_capabilities",
        lambda: ["llm.ollama"],
    )
    monkeypatch.delenv("MARY_DESKTOP_CAPABILITY_NODE_ENABLED", raising=False)
    monkeypatch.delenv("MARY_DESKTOP_LOCAL_COMPUTE", raising=False)
    monkeypatch.delenv("MARY_DESKTOP_LOCAL_COMPUTE_AUTO_AUTHORIZE", raising=False)

    status = runtime_supervisor.prepare_desktop_runtime()

    assert status["ready"] is True
    assert status["available_capabilities"] == ["llm.ollama"]
    assert status["capability_node_enabled"] is True
    assert status["local_compute_authorized"] is False

