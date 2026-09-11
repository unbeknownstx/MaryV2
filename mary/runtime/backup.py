"""Bounded backup policy for Mary's canonical durable state.

Backups are allowlist-based and contain only state that a fresh Mary process
actually reconstructs. Rebuildable caches and process-local/session state are
never copied. Restore is intentionally implemented by the offline
``scripts.restore_state`` command, not by an HTTP mutation endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable
import zipfile


BACKUP_FORMAT = "maryv2-state-backup-v2"
MANIFEST_NAME = "MARYV2_STATE_BACKUP_MANIFEST.json"
STATE_PROJECTION_VERSION = 2


@dataclass(frozen=True)
class DurableStateFile:
    relative_path: str
    category: str
    owner: str
    schema: str


DURABLE_STATE_FILES: tuple[DurableStateFile, ...] = (
    DurableStateFile("memory/memory.json", "memory", "MemoryManager", "memory"),
    DurableStateFile(
        "personality/developed_self.json",
        "developed_self",
        "DevelopedSelfStateStore",
        "developed_self",
    ),
    DurableStateFile(
        "personality/preference_promotion.json",
        "preference_candidates",
        "PreferencePromotionManager",
        "preference_promotion",
    ),
    DurableStateFile(
        "relationship/relationship.json",
        "relationship",
        "RelationshipManager",
        "relationship",
    ),
    DurableStateFile(
        "relationship/creator_directives.json",
        "relationship",
        "CreatorDirectiveStore",
        "creator_directives",
    ),
    DurableStateFile(
        "knowledge/knowledge.json",
        "knowledge",
        "KnowledgeStateStore",
        "knowledge",
    ),
    DurableStateFile("goals/goals.json", "autonomy", "GoalManager", "goals"),
    DurableStateFile(
        "goals/intentions.json",
        "autonomy",
        "IntentionManager",
        "intentions",
    ),
    DurableStateFile(
        "goals/curiosities.json",
        "autonomy",
        "CuriosityManager",
        "curiosities",
    ),
    DurableStateFile(
        "development/experience_journal.json",
        "growth",
        "ExperienceJournal",
        "experience_journal",
    ),
    DurableStateFile(
        "runtime/conversation_engagement.json",
        "engagement",
        "ConversationEngagement",
        "conversation_engagement",
    ),
    DurableStateFile(
        "runtime/node_enrollment.json",
        "node_trust",
        "MaryCoreService",
        "node_enrollment",
    ),
    DurableStateFile(
        "training/response_feedback.json",
        "training",
        "ResponseFeedbackStore",
        "response_feedback",
    ),
    DurableStateFile(
        "voice/voice_lab.json",
        "voice",
        "VoiceLabStore",
        "voice_lab",
    ),
    DurableStateFile(
        "ecosystem/command_center.json",
        "shared_work",
        "CommandCenter",
        "command_center",
    ),
    DurableStateFile(
        "ecosystem/focus.json",
        "shared_work",
        "FocusManager",
        "focus",
    ),
    DurableStateFile(
        "ecosystem/inbox.json",
        "shared_work",
        "MaryInbox",
        "inbox",
    ),
    DurableStateFile(
        "ecosystem/study.json",
        "shared_work",
        "StudyManager",
        "study",
    ),
    DurableStateFile(
        "ecosystem/research.json",
        "shared_work",
        "ResearchNotebook",
        "research",
    ),
    DurableStateFile(
        "ecosystem/production.json",
        "shared_work",
        "ProductionStudio",
        "production",
    ),
    DurableStateFile(
        "ecosystem/presence/pending_thoughts.json",
        "durable_autonomy",
        "PendingThoughtStore",
        "pending_thoughts",
    ),
    DurableStateFile(
        "continuity/experience.json",
        "experiential_continuity",
        "ExperienceLedger",
        "experience_ledger",
    ),
    DurableStateFile(
        "continuity/temporal_knowledge.json",
        "experiential_continuity",
        "TemporalKnowledgeGraph",
        "temporal_knowledge",
    ),
    DurableStateFile(
        "continuity/skills.json",
        "experiential_continuity",
        "SkillLibrary",
        "procedural_skills",
    ),
    DurableStateFile(
        "continuity/workflows.json",
        "experiential_continuity",
        "DurableWorkflowStore",
        "workflow_checkpoints",
    ),
    DurableStateFile(
        "continuity/verification.json",
        "experiential_continuity",
        "ActionVerificationManager",
        "action_verification",
    ),
)

EXCLUDED_STATE = (
    "surface_leases",
    "attention_queue",
    "provider_cooldowns",
    "node_sessions",
    "node_enrollment_grants",
    "in_flight_node_work",
    "request_and_turn_traces",
    "dialogue_session_context",
    "reservoir_and_rebuildable_indexes",
    "workspace_files_not_owned_by_canonical_state",
    "environment_and_provider_credentials",
)

_SENSITIVE_KEY = re.compile(
    r"^(?:api[_-]?key|access[_-]?token|refresh[_-]?token|bearer|password|"
    r"private[_-]?key|client[_-]?secret|provider[_-]?credential)$",
    re.IGNORECASE,
)
_STRICT_DURABLE_ROOTS = {
    "identity",
    "personality",
    "memory",
    "relationship",
    "knowledge",
    "goals",
    "development",
    "training",
    "voice",
    "ecosystem",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_metadata(payload: bytes) -> tuple[int, str | int | None]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Durable state file is not valid UTF-8 JSON.") from exc
    _reject_sensitive_keys(value)
    version: str | int | None = None
    if isinstance(value, dict):
        version = value.get("schema_version", value.get("version"))
        list_counts = [len(item) for item in value.values() if isinstance(item, list)]
        record_count = sum(list_counts) if list_counts else len(value)
    elif isinstance(value, list):
        record_count = len(value)
    else:
        record_count = 1
    return record_count, version


def validate_json_state_payload(payload: bytes) -> tuple[int, str | int | None]:
    """Validate one registered JSON state payload without returning its values."""
    return _json_metadata(payload)


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _export_payload(
    spec: DurableStateFile,
    source: bytes,
    *,
    projection_version: int = STATE_PROJECTION_VERSION,
) -> bytes:
    """Project mixed stores down to only their durable reconstruction state."""
    if (
        projection_version >= 2
        and spec.relative_path == "runtime/conversation_engagement.json"
    ):
        try:
            value = json.loads(source.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                "Conversation engagement state is not valid UTF-8 JSON."
            ) from exc
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError("Unsupported conversation engagement state schema.")
        active_session = value.get("active_session", {})
        stats = value.get("stats", {})
        if not isinstance(active_session, dict) or not isinstance(stats, dict):
            raise ValueError("Invalid conversation engagement state.")
        # The planner's last plan and question decision are process-local
        # observations. ConversationEngagement.load() intentionally does not
        # reconstruct them, so they cannot participate in a restart-stable
        # durable fingerprint. Keep the stable policy/session/statistics fields.
        return _canonical_json_bytes(
            {
                "schema_version": 1,
                "mode": value.get("mode", "adaptive"),
                "active_session": active_session,
                "last_plan": {},
                "last_question_asked": False,
                "stats": stats,
            }
        )
    if spec.relative_path != "runtime/node_enrollment.json":
        return source
    try:
        value = json.loads(source.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Node trust state is not valid UTF-8 JSON.") from exc
    if not isinstance(value, dict) or value.get("version") != 2:
        raise ValueError("Unsupported node trust state schema.")
    trusted = value.get("trusted_devices")
    if not isinstance(trusted, list):
        trusted = []
    # Grants, their audit trail, and session generations authorize only the
    # current process lifetime. A recovery artifact may preserve trust digests,
    # never an enrollment opportunity or prior session ownership.
    sanitized = {
        "version": 2,
        "grants": [],
        "audit": [],
        "session_generations": {},
        "trusted_devices": trusted,
    }
    return _canonical_json_bytes(sanitized)


def _reject_sensitive_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _SENSITIVE_KEY.match(str(key).strip()):
                raise ValueError(
                    "Durable state contains a credential-like field; backup refused."
                )
            _reject_sensitive_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_sensitive_keys(item)


def _canonical_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(encoded)


def _sourcebook_summary(sourcebook: Any | None) -> dict[str, Any]:
    if sourcebook is None:
        return {"version": None, "record_count": None, "sha256": None}
    records = getattr(sourcebook, "records", ())
    return {
        "version": str(getattr(sourcebook, "VERSION", "")) or None,
        "record_count": len(records),
        "sha256": str(getattr(sourcebook, "sourcebook_hash", "")) or None,
    }


def durable_fingerprint(
    data_root: Path,
    *,
    sourcebook: Any | None = None,
    specifications: Iterable[DurableStateFile] = DURABLE_STATE_FILES,
    projection_version: int = STATE_PROJECTION_VERSION,
) -> dict[str, Any]:
    if projection_version not in {1, STATE_PROJECTION_VERSION}:
        raise ValueError("Unsupported durable-state projection version.")
    root = Path(data_root).expanduser().resolve()
    registered = {item.relative_path for item in specifications}
    for strict_root in sorted(_STRICT_DURABLE_ROOTS):
        directory = root / strict_root
        if not directory.exists():
            continue
        for path in directory.rglob("*.json"):
            relative = path.relative_to(root).as_posix()
            if (
                path.is_file()
                and ".bak" not in path.name
                and ".tmp" not in path.name
                and relative not in registered
            ):
                raise ValueError(
                    f"Unclassified durable-state JSON file: {relative}"
                )
    records: list[dict[str, Any]] = []
    categories: dict[str, dict[str, int]] = {}
    for spec in specifications:
        path = root / spec.relative_path
        if not path.is_file():
            continue
        if path.is_symlink() or root not in path.resolve().parents:
            raise ValueError(f"Unsafe durable-state path: {spec.relative_path}")
        payload = _export_payload(
            spec,
            path.read_bytes(),
            projection_version=projection_version,
        )
        record_count, schema_version = _json_metadata(payload)
        record = {
            "path": f"data/{spec.relative_path}",
            "category": spec.category,
            "owner": spec.owner,
            "schema": spec.schema,
            "schema_version": schema_version,
            "size": len(payload),
            "sha256": sha256_bytes(payload),
            "record_count": record_count,
            "sanitized_for_recovery": (
                spec.relative_path == "runtime/node_enrollment.json"
                or (
                    projection_version >= 2
                    and spec.relative_path
                    == "runtime/conversation_engagement.json"
                )
            ),
        }
        records.append(record)
        summary = categories.setdefault(
            spec.category,
            {"file_count": 0, "record_count": 0, "total_bytes": 0},
        )
        summary["file_count"] += 1
        summary["record_count"] += record_count
        summary["total_bytes"] += len(payload)

    stable = {
        "format": BACKUP_FORMAT,
        "files": records,
        "categories": categories,
        "sourcebook": _sourcebook_summary(sourcebook),
        "excluded_state": list(EXCLUDED_STATE),
    }
    # Projection v1 predates this manifest field. Omitting it when validating
    # older v2 archives preserves their original fingerprint exactly.
    if projection_version >= 2:
        stable["projection_version"] = projection_version
    return {
        **stable,
        "file_count": len(records),
        "total_bytes": sum(item["size"] for item in records),
        "durable_state_fingerprint": _canonical_fingerprint(stable),
    }


def create_backup(
    data_root: Path,
    output_dir: Path,
    *,
    timestamp: datetime | None = None,
    sourcebook: Any | None = None,
) -> Path | None:
    root = Path(data_root).expanduser().resolve()
    destination = Path(output_dir).expanduser().resolve()
    if not root.exists():
        return None
    if root == destination or root in destination.parents:
        raise ValueError("Backup output directory must be outside Mary's data directory.")

    fingerprint = durable_fingerprint(root, sourcebook=sourcebook)
    if not fingerprint["files"]:
        return None

    destination.mkdir(parents=True, exist_ok=True)
    moment = timestamp or datetime.now(timezone.utc)
    stamp = moment.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    archive = destination / (
        f"MaryV2-state-{stamp}-{fingerprint['durable_state_fingerprint'][:12]}.zip"
    )
    temporary = archive.with_suffix(".zip.tmp")
    manifest = {
        **fingerprint,
        "created_at_utc": moment.astimezone(timezone.utc).isoformat(),
        "contains_environment_secrets": False,
        "restore_mode": "offline_empty_target_only",
    }

    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as bundle:
            for record in manifest["files"]:
                relative = Path(str(record["path"])).relative_to("data")
                spec = next(
                    item
                    for item in DURABLE_STATE_FILES
                    if item.relative_path == relative.as_posix()
                )
                payload = _export_payload(
                    spec,
                    (root / relative).read_bytes(),
                    projection_version=int(
                        manifest.get("projection_version", 1)
                    ),
                )
                if (
                    len(payload) != int(record["size"])
                    or sha256_bytes(payload) != str(record["sha256"])
                ):
                    raise RuntimeError(
                        f"Durable state changed during backup: {relative.as_posix()}"
                    )
                bundle.writestr(str(record["path"]), payload)
            bundle.writestr(
                MANIFEST_NAME,
                json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n",
            )
        temporary.replace(archive)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return archive


def inspect_backup(archive: Path) -> dict[str, Any]:
    """Verify a v2 archive and return its manifest without exposing state."""
    path = Path(archive).expanduser().resolve()
    with zipfile.ZipFile(path) as bundle:
        names = set(bundle.namelist())
        if MANIFEST_NAME not in names:
            raise ValueError("MaryV2 backup manifest is missing.")
        try:
            manifest = json.loads(bundle.read(MANIFEST_NAME).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError, KeyError) as exc:
            raise ValueError("MaryV2 backup manifest is invalid.") from exc
        if not isinstance(manifest, dict) or manifest.get("format") != BACKUP_FORMAT:
            raise ValueError("Unsupported MaryV2 state backup format.")
        records = manifest.get("files")
        if not isinstance(records, list):
            raise ValueError("MaryV2 backup file manifest is invalid.")
        allowed = {f"data/{item.relative_path}" for item in DURABLE_STATE_FILES}
        expected_names = {MANIFEST_NAME}
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("MaryV2 backup contains an invalid file record.")
            name = str(record.get("path", ""))
            if name not in allowed or name not in names:
                raise ValueError(f"Unsafe or missing backup member: {name!r}")
            payload = bundle.read(name)
            if len(payload) != int(record.get("size", -1)):
                raise ValueError(f"Backup size mismatch: {name}")
            if sha256_bytes(payload) != str(record.get("sha256", "")):
                raise ValueError(f"Backup hash mismatch: {name}")
            expected_names.add(name)
        if names != expected_names:
            raise ValueError("Backup contains unmanifested members.")
        stable = {
            "format": manifest["format"],
            "files": manifest["files"],
            "categories": manifest.get("categories", {}),
            "sourcebook": manifest.get("sourcebook", {}),
            "excluded_state": manifest.get("excluded_state", []),
        }
        if "projection_version" in manifest:
            stable["projection_version"] = manifest["projection_version"]
        if _canonical_fingerprint(stable) != str(
            manifest.get("durable_state_fingerprint", "")
        ):
            raise ValueError("Backup durable-state fingerprint mismatch.")
        if manifest.get("contains_environment_secrets") is not False:
            raise ValueError("Backup secret-exclusion declaration is invalid.")
    return manifest


def backup_public_report(archive: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Return non-content metadata safe for an authenticated operations response."""
    return {
        "backup_id": Path(archive).stem,
        "format": manifest["format"],
        "projection_version": manifest.get("projection_version", 1),
        "created_at_utc": manifest.get("created_at_utc"),
        "file_count": manifest["file_count"],
        "total_bytes": manifest["total_bytes"],
        "categories": manifest["categories"],
        "durable_state_fingerprint": manifest["durable_state_fingerprint"],
        "sourcebook": manifest["sourcebook"],
        "excluded_state": manifest["excluded_state"],
        "contains_environment_secrets": False,
        "verified": True,
    }


def durable_public_report(fingerprint: dict[str, Any]) -> dict[str, Any]:
    """Project a live durable fingerprint without paths or state contents."""
    return {
        "format": fingerprint["format"],
        "projection_version": fingerprint.get("projection_version", 1),
        "file_count": fingerprint["file_count"],
        "total_bytes": fingerprint["total_bytes"],
        "categories": fingerprint["categories"],
        "durable_state_fingerprint": fingerprint["durable_state_fingerprint"],
        "sourcebook": fingerprint["sourcebook"],
        "excluded_state": fingerprint["excluded_state"],
        "contains_environment_secrets": False,
    }


def verify_reconstruction(
    data_root: Path,
    expected_manifest: dict[str, Any],
    *,
    sourcebook: Any,
) -> dict[str, Any]:
    """Verify restored durable state and authored sourcebook against a snapshot."""
    actual = durable_fingerprint(
        data_root,
        sourcebook=sourcebook,
        projection_version=int(expected_manifest.get("projection_version", 1)),
    )
    expected_fingerprint = str(
        expected_manifest.get("durable_state_fingerprint", "")
    )
    if actual["durable_state_fingerprint"] != expected_fingerprint:
        raise ValueError("Reconstructed durable-state fingerprint mismatch.")
    expected_sourcebook = expected_manifest.get("sourcebook")
    if not isinstance(expected_sourcebook, dict):
        raise ValueError("Backup sourcebook fingerprint is missing.")
    if actual["sourcebook"] != expected_sourcebook:
        raise ValueError("Reconstructed CharacterSourcebook fingerprint mismatch.")
    return {
        **durable_public_report(actual),
        "reconstruction_verified": True,
    }