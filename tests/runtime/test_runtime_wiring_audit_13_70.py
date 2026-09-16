from pathlib import Path

from mary.core.mary import Mary
from mary.core.service import MaryCoreService
from mary.runtime.application import create_application
from mary.runtime.wiring_audit import build_runtime_wiring_audit


def test_full_runtime_wiring_audit_boots_real_composition(tmp_path, monkeypatch):
    monkeypatch.setenv("MARY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MARY_WORKSPACE_ROOT", str(tmp_path / "workspace"))

    mary = Mary()
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
        developed_self_path=tmp_path / "personality" / "developed_self.json",
        preference_promotion_path=tmp_path / "personality" / "preferences.json",
        knowledge_path=tmp_path / "knowledge" / "knowledge.json",
        auto_save=False,
        load_memory=False,
        load_developed_self=False,
        load_preference_promotion=False,
        load_knowledge=False,
    )
    service = MaryCoreService(app, instance_id="wiring-test-core")

    report = build_runtime_wiring_audit(application=app, service=service)

    assert report["healthy"] is True
    assert report["required_failures"] == []
    sections = report["sections"]
    assert sections["composition"]["healthy"] is True
    assert sections["persistence"]["healthy"] is True
    assert sections["memory"]["healthy"] is True
    assert sections["providers"]["healthy"] is True
    assert sections["nodes"]["healthy"] is True
    assert sections["protocol"]["healthy"] is True
    assert sections["actions"]["healthy"] is True

    # Runtime readiness stays truthful without turning optional hardware,
    # credentials, voice or VRM files into architecture failures.
    assert isinstance(report["degraded"], list)
    assert isinstance(sections["providers"]["conversation_ready"], bool)
    assert isinstance(sections["voice"]["tts_ready"], bool)
    assert isinstance(sections["avatar"]["vrm_configured"], bool)


def test_core_integration_status_includes_executable_runtime_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("MARY_DATA_DIR", str(tmp_path / "data"))
    mary = Mary()
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory.json",
        auto_save=False,
        load_memory=False,
        load_developed_self=False,
        load_preference_promotion=False,
        load_knowledge=False,
    )
    service = MaryCoreService(app, instance_id="wiring-test-core")

    report = service.integration_status()

    assert report["healthy"] is True
    assert report["runtime"]["healthy"] is True
    assert report["runtime"]["sections"]["protocol"]["missing_routes"] == []
