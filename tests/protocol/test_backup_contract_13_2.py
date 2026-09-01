from __future__ import annotations

import json

from fastapi.testclient import TestClient

from mary.core.service import MaryCoreService
from mary.protocol.server import create_app
from mary.runtime.application import create_application


def _service(tmp_path) -> MaryCoreService:
    data = tmp_path / "data"
    application = create_application(
        memory_path=data / "memory" / "memory.json",
        developed_self_path=data / "personality" / "developed_self.json",
        preference_promotion_path=data / "personality" / "preference_promotion.json",
        knowledge_path=data / "knowledge" / "knowledge.json",
        auto_save=True,
        name="backup-contract",
    )
    relationship = data / "relationship" / "relationship.json"
    relationship.parent.mkdir(parents=True, exist_ok=True)
    relationship.write_text(
        json.dumps({"relationship": {"stage": "established"}}),
        encoding="utf-8",
    )
    return MaryCoreService(
        application,
        instance_id="backup-contract-core",
        enrollment_state_path=data / "runtime" / "node_enrollment.json",
    )


def test_backup_endpoint_is_creator_authenticated_and_returns_metadata_only(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("MARY_CORE_TOKEN", "creator-backup-secret")
    monkeypatch.setenv("MARY_BACKUP_DIR", str(tmp_path / "protected-backups"))
    service = _service(tmp_path)

    with TestClient(create_app(service)) as client:
        assert client.post("/v1/admin/backups").status_code == 401
        assert client.get("/v1/admin/durable-state").status_code == 401
        live = client.get(
            "/v1/admin/durable-state",
            headers={"Authorization": "Bearer creator-backup-secret"},
        )
        response = client.post(
            "/v1/admin/backups",
            headers={"Authorization": "Bearer creator-backup-secret"},
        )

    assert response.status_code == 200
    assert live.status_code == 200
    payload = response.json()
    assert payload["verified"] is True
    assert payload["contains_environment_secrets"] is False
    assert payload["file_count"] >= 1
    assert len(payload["durable_state_fingerprint"]) == 64
    serialized = json.dumps(payload).lower()
    assert "relationship.json" not in serialized
    assert "established" not in serialized
    assert str(tmp_path).lower() not in serialized
    assert "archive" not in payload
    live_payload = live.json()
    assert live_payload["durable_state_fingerprint"] == (
        payload["durable_state_fingerprint"]
    )
    assert live_payload["core_instance_id"] == "backup-contract-core"


def test_backup_endpoint_fails_safely_without_protected_destination(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("MARY_CORE_TOKEN", "creator-backup-secret")
    monkeypatch.delenv("MARY_BACKUP_DIR", raising=False)
    service = _service(tmp_path)
    state = tmp_path / "data" / "relationship" / "relationship.json"
    before = state.read_bytes()

    with TestClient(create_app(service)) as client:
        response = client.post(
            "/v1/admin/backups",
            headers={"Authorization": "Bearer creator-backup-secret"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Durable-state backup failed safely."
    assert state.read_bytes() == before