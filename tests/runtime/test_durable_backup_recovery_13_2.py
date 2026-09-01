from __future__ import annotations

from pathlib import Path

import pytest

from mary.core.service import MaryCoreService
from mary.llm.interface import LLMInterface, LLMMessage, LLMResponse
from mary.runtime.application import create_application
from mary.runtime.backup import (
    create_backup,
    durable_fingerprint,
    inspect_backup,
    verify_reconstruction,
)
from scripts.restore_state import restore_backup


class _BackupLifecycleLLM(LLMInterface):
    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        return LLMResponse(
            content="A deterministic Mary response.",
            provider="backup-lifecycle",
            model="backup-test-model",
        )

    def is_available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "backup-lifecycle"

    def model_name(self) -> str:
        return "backup-test-model"


def _application(data_root: Path, monkeypatch, *, load: bool):
    monkeypatch.setenv("MARY_DATA_DIR", str(data_root))
    app = create_application(
        auto_save=True,
        load_memory=load,
        load_developed_self=load,
        load_preference_promotion=load,
        load_knowledge=load,
        name="durable-backup-recovery",
    )
    app.mary.llm.register_provider("backup-lifecycle", _BackupLifecycleLLM())
    app.mary.config.llm.provider = "backup-lifecycle"
    return app


def _relationship_snapshot(mary) -> dict:
    return {
        "user_model": mary.relationship.user_model.to_dict(),
        "history": mary.relationship.history.to_dict(),
        "understanding": mary.relationship.understanding.to_dict(),
        "milestones": mary.relationship.milestones.export(),
    }


def test_backup_restore_reconstructs_developed_self_and_omits_ephemeral_state(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source-data"
    first = _application(source, monkeypatch, load=False)
    prompts = (
        "Please keep your answers concise.",
        "I prefer your responses to be brief.",
        "From now on, keep your replies short.",
        "That response was too long.",
        "Do not be so verbose.",
    )
    for index, prompt in enumerate(prompts, start=1):
        result = first.run(prompt, turn_id=f"backup-evidence-{index}")
        assert result.success is True
    command = first.ecosystem.command.add(
        "Preserve the canonical release checklist",
        kind="task",
        priority=1,
        notes="Shared work must survive recovery.",
    )
    pending_thought = first.ecosystem.presence.thoughts.add(
        "Revisit the verified deployment checklist after the next safe restart.",
        context="Task 23 recovery drill",
        importance=0.8,
        ttl_hours=24,
        source="recovery_test",
    )
    assert first.save() is True
    before_growth = first.mary.growth.status()
    before_relationship = _relationship_snapshot(first.mary)
    before_memory = first.mary.memory.status()
    before_sourcebook = first.mary.character_sourcebook.snapshot()
    before = durable_fingerprint(
        source,
        sourcebook=first.mary.character_sourcebook,
    )

    ephemeral = {
        "runtime/node_sessions.json": "{}",
        "runtime/surface_leases.json": "{}",
        "runtime/attention_queue.json": "{}",
        "runtime/provider_cooldown.json": "{}",
        "runtime/request_traces.json": "{}",
        "reservoir/rebuildable.json": "{}",
    }
    for relative, payload in ephemeral.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")

    archive = create_backup(
        source,
        tmp_path / "protected-backups",
        sourcebook=first.mary.character_sourcebook,
    )
    assert archive is not None
    manifest = inspect_backup(archive)
    assert manifest["durable_state_fingerprint"] == before["durable_state_fingerprint"]
    assert manifest["sourcebook"]["sha256"] == before_sourcebook["sourcebook_hash"]
    first.close()

    restored = tmp_path / "restored-data"
    report = restore_backup(archive, restored, apply=True)
    assert report["applied"] is True
    for relative in ephemeral:
        assert not (restored / relative).exists()

    second = _application(restored, monkeypatch, load=True)
    after = durable_fingerprint(
        restored,
        sourcebook=second.mary.character_sourcebook,
    )
    assert after["durable_state_fingerprint"] == before["durable_state_fingerprint"]
    verification = verify_reconstruction(
        restored,
        manifest,
        sourcebook=second.mary.character_sourcebook,
    )
    assert verification["reconstruction_verified"] is True
    assert second.mary.growth.status()["journal"]["records"] == (
        before_growth["journal"]["records"]
    )
    assert second.mary.memory.status()["counts"] == before_memory["counts"]
    assert _relationship_snapshot(second.mary) == before_relationship
    developed = second.mary.growth.status()["developed_preferences"]
    assert len(developed) == 1
    assert developed[0]["state"] == "active"
    assert second.mary.character_sourcebook.snapshot() == before_sourcebook
    restored_commands = second.ecosystem.command.list(limit=20)
    assert any(item["id"] == command["id"] for item in restored_commands)
    restored_thoughts = second.ecosystem.presence.thoughts.active(limit=20)
    assert any(item["id"] == pending_thought["id"] for item in restored_thoughts)
    second.close()


def test_backup_preserves_node_trust_but_never_grants_or_sessions(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source-data"
    first_app = _application(source, monkeypatch, load=False)
    first = MaryCoreService(
        first_app,
        enrollment_state_path=source / "runtime" / "node_enrollment.json",
    )
    registration = {
        "node_id": "device-a",
        "display_name": "device-a",
        "host_type": "desktop",
        "platform": "windows",
        "surface": "desktop",
        "capabilities": [{"name": "personal_search", "private": True}],
    }
    enrolled = first.register_node(registration)
    old_token = enrolled["node_token"]
    durable_credential = enrolled["device_credential"]
    old_grant = first.issue_enrollment_grant("device-b")["enrollment_grant"]

    archive = create_backup(
        source,
        tmp_path / "protected-backups",
        sourcebook=first.mary.character_sourcebook,
    )
    assert archive is not None
    restored = tmp_path / "restored-data"
    restore_backup(archive, restored, apply=True)
    first.close()

    second_app = _application(restored, monkeypatch, load=True)
    second = MaryCoreService(
        second_app,
        enrollment_state_path=restored / "runtime" / "node_enrollment.json",
    )
    status = second.enrollment_grant_status()
    assert status["grants"] == []
    assert [item["node_id"] for item in status["trusted_devices"]] == ["device-a"]
    assert not second.validate_node_token("device-a", old_token)
    with pytest.raises(PermissionError):
        second.register_node(
            {**registration, "node_id": "device-b", "display_name": "device-b"},
            enrollment_grant=old_grant,
            creator_authorized=False,
        )
    reconnected = second.register_node(
        registration,
        device_credential=durable_credential,
        creator_authorized=False,
    )
    assert reconnected["node_token"] != old_token
    assert reconnected["session_generation"] == 1
    second.close()


def test_reconstruction_verification_rejects_sourcebook_mismatch(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source-data"
    app = _application(source, monkeypatch, load=False)
    assert app.save() is True
    archive = create_backup(
        source,
        tmp_path / "protected-backups",
        sourcebook=app.mary.character_sourcebook,
    )
    assert archive is not None
    manifest = inspect_backup(archive)
    manifest["sourcebook"] = {
        "version": "1.0",
        "record_count": 999,
        "sha256": "mismatch",
    }
    with pytest.raises(ValueError, match="CharacterSourcebook"):
        verify_reconstruction(
            source,
            manifest,
            sourcebook=app.mary.character_sourcebook,
        )
    app.close()