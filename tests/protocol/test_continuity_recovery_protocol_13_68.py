from fastapi.testclient import TestClient

from mary.core.service import MaryCoreService
from mary.protocol.server import create_app
from mary.runtime.application import create_application


def _continuity():
    return {
        "memory": {
            "episodic": [
                {
                    "id": "episode_recovery_test",
                    "content": "Recovered creator continuity test.",
                    "timestamp": "2026-08-20T10:00:00+00:00",
                    "importance": 0.8,
                    "source": "interaction",
                    "event_type": "shared_work",
                    "participants": ["creator", "mary"],
                    "emotional_context": {},
                    "metadata": {},
                }
            ],
            "semantic": [],
        },
        "relationship": {
            "user_model": {
                "creator_id": "creator",
                "name": "unbe",
                "facts": {},
                "preferences": {},
                "interests": [],
                "values": [],
                "goals": [],
                "communication_style": {},
                "profile_records": [],
            },
            "history": {
                "creator_id": "creator",
                "events": [
                    {
                        "id": "relationship_recovery_test",
                        "creator_id": "creator",
                        "type": "shared_experience",
                        "description": "Recovered a bounded continuity record.",
                        "importance": 0.8,
                        "source": "relationship",
                        "metadata": {},
                        "created_at": "2026-08-20T10:00:00+00:00",
                    }
                ],
            },
            "understanding": {
                "observations": [],
                "inferences": [],
                "patterns": [],
            },
            "milestones": [],
        },
    }


def _service(tmp_path):
    data = tmp_path / "data"
    app = create_application(
        memory_path=data / "memory" / "memory.json",
        developed_self_path=data / "personality" / "developed_self.json",
        preference_promotion_path=data / "personality" / "preference_promotion.json",
        knowledge_path=data / "knowledge" / "knowledge.json",
        auto_save=True,
        name="continuity-recovery-test",
    )
    return MaryCoreService(
        app,
        instance_id="continuity-recovery-core",
        enrollment_state_path=data / "runtime" / "node_enrollment.json",
    )


def test_recovery_preview_is_authenticated_and_non_mutating(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("MARY_CORE_TOKEN", "recovery-secret")
    monkeypatch.setenv("MARY_BACKUP_DIR", str(tmp_path / "protected-backups"))
    service = _service(tmp_path)
    before_memory = service.mary.memory.episodic.count()
    before_history = service.mary.relationship.history.count()

    with TestClient(create_app(service)) as client:
        assert client.post(
            "/v1/admin/continuity-recovery/preview",
            json={"continuity": _continuity()},
        ).status_code == 401

        response = client.post(
            "/v1/admin/continuity-recovery/preview",
            headers={"Authorization": "Bearer recovery-secret"},
            json={"continuity": _continuity()},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mutated"] is False
    assert payload["backup_ready"] is True
    assert payload["plan"]["additions"]["episodic"] == 1
    assert payload["plan"]["additions"]["relationship_history"] == 1
    assert len(payload["expected_durable_state_fingerprint"]) == 64
    assert service.mary.memory.episodic.count() == before_memory
    assert service.mary.relationship.history.count() == before_history


def test_recovery_apply_requires_exact_confirmation(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("MARY_CORE_TOKEN", "recovery-secret")
    monkeypatch.setenv("MARY_BACKUP_DIR", str(tmp_path / "protected-backups"))
    service = _service(tmp_path)
    headers = {"Authorization": "Bearer recovery-secret"}

    with TestClient(create_app(service)) as client:
        preview = client.post(
            "/v1/admin/continuity-recovery/preview",
            headers=headers,
            json={"continuity": _continuity()},
        ).json()
        response = client.post(
            "/v1/admin/continuity-recovery/apply",
            headers=headers,
            json={
                "continuity": _continuity(),
                "expected_fingerprint": preview[
                    "expected_durable_state_fingerprint"
                ],
                "confirmation": "yes",
            },
        )

    assert response.status_code == 403
    assert service.mary.memory.episodic.count() == 0


def test_recovery_apply_backs_up_merges_and_rejects_stale_replay(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("MARY_CORE_TOKEN", "recovery-secret")
    monkeypatch.setenv("MARY_BACKUP_DIR", str(tmp_path / "protected-backups"))
    service = _service(tmp_path)
    headers = {"Authorization": "Bearer recovery-secret"}

    with TestClient(create_app(service)) as client:
        preview_response = client.post(
            "/v1/admin/continuity-recovery/preview",
            headers=headers,
            json={"continuity": _continuity()},
        )
        assert preview_response.status_code == 200
        preview = preview_response.json()
        expected = preview["expected_durable_state_fingerprint"]

        applied = client.post(
            "/v1/admin/continuity-recovery/apply",
            headers=headers,
            json={
                "continuity": _continuity(),
                "expected_fingerprint": expected,
                "confirmation": "MERGE_LOCAL_CONTINUITY",
            },
        )
        stale = client.post(
            "/v1/admin/continuity-recovery/apply",
            headers=headers,
            json={
                "continuity": _continuity(),
                "expected_fingerprint": expected,
                "confirmation": "MERGE_LOCAL_CONTINUITY",
            },
        )

    assert applied.status_code == 200
    payload = applied.json()
    assert payload["mutated"] is True
    assert payload["backup"]["verified"] is True
    assert payload["merge"]["added"]["episodic"] == 1
    assert payload["merge"]["added"]["relationship_history"] == 1
    assert payload["before_durable_state_fingerprint"] != (
        payload["after_durable_state_fingerprint"]
    )
    assert service.mary.memory.episodic.count() == 1
    assert service.mary.relationship.history.count() >= 1
    assert stale.status_code == 409


def test_recovery_apply_refuses_without_protected_backup(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("MARY_CORE_TOKEN", "recovery-secret")
    monkeypatch.delenv("MARY_BACKUP_DIR", raising=False)
    service = _service(tmp_path)
    headers = {"Authorization": "Bearer recovery-secret"}

    with TestClient(create_app(service)) as client:
        preview = client.post(
            "/v1/admin/continuity-recovery/preview",
            headers=headers,
            json={"continuity": _continuity()},
        ).json()
        assert preview["backup_ready"] is False
        response = client.post(
            "/v1/admin/continuity-recovery/apply",
            headers=headers,
            json={
                "continuity": _continuity(),
                "expected_fingerprint": preview[
                    "expected_durable_state_fingerprint"
                ],
                "confirmation": "MERGE_LOCAL_CONTINUITY",
            },
        )

    assert response.status_code == 409
    assert service.mary.memory.episodic.count() == 0
