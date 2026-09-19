"""Locally owned knowledge-pack fabric for MaryV2.

Knowledge packs are evidence sources, not memory and not identity.  This module
provides:
- an inspectable registry of installed/candidate local knowledge collections,
- a rebuildable SQLite FTS index for explicit local document folders,
- a bounded read-only Kiwix search adapter for locally served ZIM libraries,
- query planning across packs without silently promoting retrieved text.

Vector backends such as Qdrant/Qdrant Edge are represented in the same pack
contract and may be attached by a capability node without changing Core.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from fnmatch import fnmatchcase
import html
import ipaddress
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4
import xml.etree.ElementTree as ET
import zipfile

from mary.runtime.persistence import atomic_write_json, load_json_recovering


_ALLOWED_FILE_SUFFIXES = {
    ".txt", ".md", ".rst", ".html", ".htm", ".json", ".jsonl",
    ".csv", ".yaml", ".yml", ".toml", ".docx", ".epub", ".pdf",
}
_DENIED_NAMES = {".env", ".env.local", ".env.production", "credentials.json", "secrets.json"}
_DENIED_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".maryv2", "secrets"}
_MAX_FILE_BYTES = 64 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _tuple(values: Iterable[str], *, limit: int = 32, item_limit: int = 120) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            _text(item, item_limit)
            for item in list(values)[:limit]
            if _text(item, item_limit)
        )
    )


@dataclass(frozen=True)
class KnowledgePack:
    id: str
    title: str
    collection: str
    kind: str
    query_mode: str
    ingest_policy: str
    location: str
    enabled: bool
    local_only: bool
    topics: tuple[str, ...]
    license: str
    trust: str
    source: str
    content_fingerprint: str
    created_at: str
    updated_at: str
    disabled_documents: tuple[str, ...]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["topics"] = list(self.topics)
        payload["disabled_documents"] = list(self.disabled_documents)
        payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True)
class KnowledgeHit:
    pack_id: str
    title: str
    snippet: str
    source: str
    score: float
    locator: str = ""
    content_hash: str = ""
    collection: str = "default"
    source_date: str = ""
    indexed_at: str = ""
    citation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class KnowledgeFabric:
    """Registry and read-only retrieval substrate for locally owned knowledge."""

    VERSION = 4
    LOCAL_INDEX_PIPELINE_VERSION = "mary-local-index-v1"
    DEFAULT_CHUNK_TARGET = 6000
    DEFAULT_CHUNK_OVERLAP = 500
    KINDS = {"local_files", "kiwix", "qdrant", "qdrant_edge", "kolibri", "notes", "custom"}
    QUERY_MODES = {"fts", "direct", "vector", "hybrid", "catalog_only"}
    INGEST_POLICIES = {"manual", "on_change"}
    RETRIEVAL_MODES = {"auto", "off", "lexical", "direct", "vector", "hybrid"}

    def __init__(
        self,
        registry_path: Path,
        *,
        index_path: Path | None = None,
        capacity: int = 256,
    ) -> None:
        self.registry_path = Path(registry_path)
        self.index_path = Path(index_path) if index_path is not None else self.registry_path.with_suffix(".sqlite3")
        self.capacity = max(32, int(capacity))
        # Construction is observational. Registry/index files are created only
        # when the creator registers/indexes a real pack.

    def _ensure_registry(self) -> None:
        if self.registry_path.exists():
            return
        atomic_write_json(
            self.registry_path,
            {"version": self.VERSION, "packs": []},
            backup_generations=2,
            indent=2,
        )

    def _load(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {"version": self.VERSION, "packs": []}
        payload, _source = load_json_recovering(self.registry_path, backup_generations=2)
        if not isinstance(payload, dict):
            return {"version": self.VERSION, "packs": []}
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        payload["version"] = self.VERSION
        atomic_write_json(
            self.registry_path,
            payload,
            backup_generations=2,
            indent=2,
        )

    def register(
        self,
        *,
        title: str,
        kind: str,
        location: str,
        query_mode: str,
        ingest_policy: str = "manual",
        topics: Iterable[str] = (),
        collection: str = "default",
        license: str = "unknown",
        trust: str = "creator_configured",
        source: str = "creator",
        enabled: bool = True,
        local_only: bool = True,
        pack_id: str = "",
        content_fingerprint: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgePack:
        clean_title = _text(title, 240)
        clean_kind = _text(kind, 80).casefold()
        clean_mode = _text(query_mode, 80).casefold()
        clean_ingest = _text(ingest_policy, 40).casefold() or "manual"
        clean_location = str(location or "").strip()[:1000]
        if not clean_title or clean_kind not in self.KINDS or clean_mode not in self.QUERY_MODES:
            raise ValueError("knowledge pack requires valid title, kind and query_mode")
        if clean_ingest not in self.INGEST_POLICIES:
            raise ValueError(
                f"ingest_policy must be one of {sorted(self.INGEST_POLICIES)}"
            )
        if not clean_location:
            raise ValueError("knowledge pack location is required")
        if clean_kind == "local_files":
            resolved = Path(clean_location).expanduser().resolve()
            if not resolved.exists() or not resolved.is_dir():
                raise ValueError("local_files knowledge pack must point to an existing directory")
            clean_location = str(resolved)
        if clean_kind == "kiwix":
            self._validate_local_endpoint(clean_location)
        qdrant_active = (
            clean_kind in {"qdrant", "qdrant_edge"}
            and clean_mode in {"vector", "hybrid"}
        )
        if qdrant_active:
            self._validate_qdrant_endpoint(clean_location)

        identifier = _text(pack_id, 160) or f"pack_{uuid4().hex}"
        now = _now()
        safe_metadata = self._safe_metadata(metadata)
        if qdrant_active:
            self._validate_qdrant_metadata(safe_metadata)
        payload = self._load()
        rows = list(payload.get("packs") or [])
        existing = next((row for row in rows if row.get("id") == identifier), None)
        row = {
            "id": identifier,
            "title": clean_title,
            "collection": _text(collection, 160) or "default",
            "kind": clean_kind,
            "query_mode": clean_mode,
            "ingest_policy": clean_ingest,
            "location": clean_location,
            "enabled": bool(enabled),
            "local_only": bool(local_only),
            "topics": list(_tuple(topics)),
            "license": _text(license, 160) or "unknown",
            "trust": _text(trust, 80) or "creator_configured",
            "source": _text(source, 160) or "creator",
            "content_fingerprint": _text(content_fingerprint, 128),
            "created_at": str(existing.get("created_at")) if existing else now,
            "updated_at": now,
            # Source activation is creator intent, so it lives in the durable
            # registry and survives disposable FTS rebuilds.
            "disabled_documents": list(existing.get("disabled_documents") or []) if existing else [],
            "metadata": safe_metadata,
        }
        if existing is None:
            rows.append(row)
        else:
            existing.clear()
            existing.update(row)
        payload["packs"] = rows[-self.capacity :]
        self._save(payload)
        return self.get(identifier)

    def disable(self, pack_id: str) -> KnowledgePack:
        return self._set_enabled(pack_id, False)

    def enable(self, pack_id: str) -> KnowledgePack:
        return self._set_enabled(pack_id, True)

    def _set_enabled(self, pack_id: str, enabled: bool) -> KnowledgePack:
        payload = self._load()
        found = False
        for row in list(payload.get("packs") or []):
            if row.get("id") == pack_id:
                row["enabled"] = bool(enabled)
                row["updated_at"] = _now()
                found = True
                break
        if not found:
            raise KeyError(pack_id)
        self._save(payload)
        return self.get(pack_id)

    def get(self, pack_id: str) -> KnowledgePack:
        for row in list(self._load().get("packs") or []):
            if row.get("id") == pack_id:
                return self._decode_pack(row)
        raise KeyError(pack_id)

    def packs(
        self,
        *,
        enabled_only: bool = False,
        collection: str = "",
    ) -> list[KnowledgePack]:
        result = [self._decode_pack(row) for row in list(self._load().get("packs") or [])]
        if enabled_only:
            result = [item for item in result if item.enabled]
        wanted_collection = _text(collection, 160).casefold()
        if wanted_collection:
            result = [
                item for item in result
                if item.collection.casefold() == wanted_collection
            ]
        return result

    def enable_collection(self, collection: str) -> list[KnowledgePack]:
        return self._set_collection_enabled(collection, True)

    def disable_collection(self, collection: str) -> list[KnowledgePack]:
        return self._set_collection_enabled(collection, False)

    def _set_collection_enabled(
        self,
        collection: str,
        enabled: bool,
    ) -> list[KnowledgePack]:
        wanted = _text(collection, 160).casefold()
        if not wanted:
            raise ValueError("collection is required")
        payload = self._load()
        changed: list[str] = []
        now = _now()
        for row in list(payload.get("packs") or []):
            if str(row.get("collection") or "default").casefold() != wanted:
                continue
            row["enabled"] = bool(enabled)
            row["updated_at"] = now
            changed.append(str(row.get("id") or ""))
        if not changed:
            raise KeyError(collection)
        self._save(payload)
        return [self.get(pack_id) for pack_id in changed if pack_id]

    @staticmethod
    def _document_source(locator: str) -> str:
        value = str(locator or "").replace("\\", "/").strip()
        return re.sub(r"#chunk-\d+$", "", value, flags=re.I)[:800]

    def documents(self, pack_id: str) -> list[dict[str, Any]]:
        pack = self.get(pack_id)
        if pack.kind != "local_files":
            return []
        if not self.index_path.exists():
            return []
        try:
            self._ensure_index()
        except sqlite3.Error:
            return []
        rows: list[tuple[Any, ...]] = []
        try:
            with self._connect() as db:
                rows = list(db.execute(
                    "SELECT locator, indexed_at, source_modified_at "
                    "FROM documents WHERE pack_id = ? ORDER BY locator",
                    (pack.id,),
                ))
        except sqlite3.Error:
            return []
        disabled = set(pack.disabled_documents)
        grouped: dict[str, dict[str, Any]] = {}
        for locator, indexed_at, source_modified_at in rows:
            source_path = self._document_source(str(locator or ""))
            if not source_path:
                continue
            item = grouped.setdefault(source_path, {
                "pack_id": pack.id,
                "locator": source_path,
                "enabled": source_path not in disabled,
                "chunks": 0,
                "source_date": _text(source_modified_at, 80),
                "indexed_at": _text(indexed_at, 80),
            })
            item["chunks"] += 1
            if str(indexed_at or "") > str(item.get("indexed_at") or ""):
                item["indexed_at"] = _text(indexed_at, 80)
        return list(grouped.values())

    def indexed_chunks(
        self,
        pack_id: str,
        *,
        enabled_only: bool = True,
        limit: int = 20_000,
    ) -> list[dict[str, Any]]:
        """Return bounded rebuildable local chunks for a derived indexer.

        Chunk text never becomes canonical Mary state.  This method is intended
        for node-local derivative builders such as Qdrant and respects durable
        per-document activation policy by default.
        """

        pack = self.get(pack_id)
        if pack.kind != "local_files":
            raise ValueError("indexed_chunks requires a local_files source pack")
        if not self.index_path.exists():
            return []
        self._ensure_index()
        rows: list[tuple[Any, ...]] = []
        with self._connect() as db:
            rows = list(db.execute(
                """
                SELECT locator, title, body, content_hash, indexed_at, source_modified_at
                FROM documents
                WHERE pack_id = ?
                ORDER BY locator, id
                LIMIT ?
                """,
                (pack.id, max(1, min(20_000, int(limit)))),
            ))
        disabled = set(pack.disabled_documents)
        output: list[dict[str, Any]] = []
        for locator, title, body, content_hash, indexed_at, source_date in rows:
            locator_text = _text(locator, 500)
            if enabled_only and self._document_source(locator_text) in disabled:
                continue
            output.append({
                "pack_id": pack.id,
                "locator": locator_text,
                "title": _text(title, 240),
                "text": str(body or "")[:20_000],
                "content_hash": _text(content_hash, 128),
                "indexed_at": _text(indexed_at, 80),
                "source_date": _text(source_date, 80),
            })
        return output

    def enable_document(self, pack_id: str, locator: str) -> dict[str, Any]:
        return self._set_document_enabled(pack_id, locator, True)

    def disable_document(self, pack_id: str, locator: str) -> dict[str, Any]:
        return self._set_document_enabled(pack_id, locator, False)

    def _set_document_enabled(
        self,
        pack_id: str,
        locator: str,
        enabled: bool,
    ) -> dict[str, Any]:
        pack = self.get(pack_id)
        if pack.kind != "local_files":
            raise ValueError("document activation is available only for local_files packs")
        source_path = self._document_source(locator)
        if not source_path or source_path.startswith("/") or ".." in Path(source_path).parts:
            raise ValueError("document locator must be a safe pack-relative source path")
        known = {item["locator"] for item in self.documents(pack_id)}
        if not known:
            raise RuntimeError("index the local_files pack before changing document activation")
        if source_path not in known:
            raise KeyError(source_path)

        payload = self._load()
        found = False
        for row in list(payload.get("packs") or []):
            if str(row.get("id") or "") != pack_id:
                continue
            disabled = {
                self._document_source(item)
                for item in list(row.get("disabled_documents") or [])
                if self._document_source(item)
            }
            if enabled:
                disabled.discard(source_path)
            else:
                disabled.add(source_path)
            row["disabled_documents"] = sorted(disabled)[:4096]
            row["updated_at"] = _now()
            found = True
            break
        if not found:
            raise KeyError(pack_id)
        self._save(payload)
        return next(
            item for item in self.documents(pack_id)
            if item["locator"] == source_path
        )

    @staticmethod
    def _manifest_locator(pack_id: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(pack_id or ""))[:180] or "pack"

    def _source_manifest_path(self, pack_id: str) -> Path:
        return (
            self.registry_path.parent
            / "manifests"
            / f"{self._manifest_locator(pack_id)}.json"
        )

    @classmethod
    def local_index_pipeline_fingerprint(cls) -> str:
        payload = {
            "version": cls.LOCAL_INDEX_PIPELINE_VERSION,
            "allowed_suffixes": sorted(_ALLOWED_FILE_SUFFIXES),
            "max_file_bytes": _MAX_FILE_BYTES,
            "chunk_target": cls.DEFAULT_CHUNK_TARGET,
            "chunk_overlap": cls.DEFAULT_CHUNK_OVERLAP,
        }
        return sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def local_index_lineage(self, pack_id: str) -> dict[str, Any]:
        """Return cheap content-free lineage for the current local derivative."""

        pack = self.get(pack_id)
        if pack.kind != "local_files":
            raise ValueError("local index lineage requires a local_files pack")
        manifest = self._load_source_manifest(pack.id)
        current_pipeline = self.local_index_pipeline_fingerprint()
        stored_pipeline = _text(manifest.get("pipeline_fingerprint"), 128)
        manifest_content = _text(manifest.get("content_fingerprint"), 128)
        current = bool(
            self._source_manifest_path(pack.id).exists()
            and pack.content_fingerprint
            and manifest_content == pack.content_fingerprint
            and stored_pipeline == current_pipeline
        )
        derivative_fingerprint = (
            sha256(
                (
                    pack.content_fingerprint
                    + "|"
                    + current_pipeline
                ).encode("utf-8")
            ).hexdigest()
            if current
            else ""
        )
        return {
            "pack_id": pack.id,
            "content_fingerprint": pack.content_fingerprint,
            "manifest_content_fingerprint": manifest_content,
            "pipeline_version": self.LOCAL_INDEX_PIPELINE_VERSION,
            "pipeline_fingerprint": current_pipeline,
            "stored_pipeline_fingerprint": stored_pipeline,
            "current": current,
            "derivative_fingerprint": derivative_fingerprint,
            "authority": "rebuildable local index lineage only",
        }

    def derivative_source_fingerprint(self, pack_id: str) -> str:
        pack = self.get(pack_id)
        if pack.kind == "local_files":
            return str(self.local_index_lineage(pack.id)["derivative_fingerprint"])
        return _text(pack.content_fingerprint, 128)

    def _load_source_manifest(self, pack_id: str) -> dict[str, Any]:
        path = self._source_manifest_path(pack_id)
        if not path.exists():
            return {"version": 2, "pack_id": pack_id, "documents": []}
        try:
            payload, _source = load_json_recovering(path, backup_generations=2)
        except Exception:
            return {"version": 2, "pack_id": pack_id, "documents": []}
        return dict(payload) if isinstance(payload, dict) else {
            "version": 2, "pack_id": pack_id, "documents": []
        }

    def _save_source_manifest(
        self,
        pack: KnowledgePack,
        documents: list[dict[str, Any]],
        *,
        content_fingerprint: str,
    ) -> None:
        path = self._source_manifest_path(pack.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            path,
            {
                "version": 2,
                "pack_id": pack.id,
                "generated_at": _now(),
                "content_fingerprint": _text(content_fingerprint, 128),
                "pipeline_version": self.LOCAL_INDEX_PIPELINE_VERSION,
                "pipeline_fingerprint": self.local_index_pipeline_fingerprint(),
                "documents": list(documents)[:100_000],
                "authority": "rebuildable_source_inventory_only",
            },
            backup_generations=2,
            indent=2,
        )

    @staticmethod
    def _source_allowed(pack: KnowledgePack, relative: Path) -> bool:
        if any(part.casefold() in _DENIED_PARTS for part in relative.parts):
            return False
        if relative.name.casefold() in _DENIED_NAMES:
            return False
        if relative.suffix.casefold() not in _ALLOWED_FILE_SUFFIXES:
            return False
        locator = relative.as_posix()
        metadata = dict(pack.metadata or {})
        includes = [
            str(item).strip()
            for item in list(metadata.get("include_patterns") or [])
            if str(item).strip()
        ][:64]
        excludes = [
            str(item).strip()
            for item in list(metadata.get("exclude_patterns") or [])
            if str(item).strip()
        ][:64]
        if includes and not any(fnmatchcase(locator, pattern) for pattern in includes):
            return False
        if excludes and any(fnmatchcase(locator, pattern) for pattern in excludes):
            return False
        return True

    def local_refresh_plan(self, pack_id: str) -> dict[str, Any]:
        """Inspect local source changes without mutating registry or indexes."""

        pack = self.get(pack_id)
        if pack.kind != "local_files":
            raise ValueError("refresh planning is available only for local_files packs")
        root = Path(pack.location).resolve()
        previous = self._load_source_manifest(pack.id)
        current_pipeline = self.local_index_pipeline_fingerprint()
        previous_pipeline = _text(
            previous.get("pipeline_fingerprint"), 128
        )
        pipeline_changed = previous_pipeline != current_pipeline
        old = {
            str(item.get("locator") or ""): dict(item)
            for item in list(previous.get("documents") or [])
            if isinstance(item, dict) and str(item.get("locator") or "")
        }
        current: dict[str, dict[str, Any]] = {}
        skipped = 0
        for path in root.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(root)
            if not self._source_allowed(pack, rel):
                skipped += 1
                continue
            try:
                stat = path.stat()
                if stat.st_size > _MAX_FILE_BYTES:
                    skipped += 1
                    continue
                body = self._read_document(path)
            except (OSError, ValueError, zipfile.BadZipFile):
                skipped += 1
                continue
            if not body:
                skipped += 1
                continue
            locator = rel.as_posix()
            current[locator] = {
                "locator": locator,
                "content_hash": sha256(body.encode("utf-8")).hexdigest(),
                "size_bytes": int(stat.st_size),
                "source_modified_at": datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=timezone.utc,
                ).isoformat(),
            }

        added = sorted(set(current) - set(old))
        removed = sorted(set(old) - set(current))
        changed = sorted(
            locator
            for locator in set(current).intersection(old)
            if str(current[locator].get("content_hash") or "")
            != str(old[locator].get("content_hash") or "")
        )
        unchanged = sorted(
            locator
            for locator in set(current).intersection(old)
            if locator not in set(changed)
        )
        fingerprint = sha256(
            "\n".join(
                sorted(
                    f"{locator}:{row.get('content_hash', '')}"
                    for locator, row in current.items()
                )
            ).encode("utf-8")
        ).hexdigest() if current else ""
        has_changes = (
            bool(added or removed or changed)
            or fingerprint != str(previous.get("content_fingerprint") or "")
            or pipeline_changed
        )
        return {
            "pack_id": pack.id,
            "collection": pack.collection,
            "ingest_policy": pack.ingest_policy,
            "manifest_present": self._source_manifest_path(pack.id).exists(),
            "documents_seen": len(current),
            "added": added[:5000],
            "changed": changed[:5000],
            "removed": removed[:5000],
            "unchanged": len(unchanged),
            "skipped": skipped,
            "content_fingerprint": fingerprint,
            "pipeline_version": self.LOCAL_INDEX_PIPELINE_VERSION,
            "pipeline_fingerprint": current_pipeline,
            "previous_pipeline_fingerprint": previous_pipeline,
            "pipeline_changed": pipeline_changed,
            "has_changes": has_changes,
            "recommended_action": "explicit_index" if has_changes else "none",
            "automatic_mutation_performed": False,
            "authority": "source inventory only; retrieval index remains derivative",
        }

    def plan(self, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        terms = {
            token.casefold()
            for token in re.findall(r"[\w'-]{3,}", str(query or ""))
        }
        scored: list[tuple[float, KnowledgePack]] = []
        for pack in self.packs(enabled_only=True):
            haystack = (
                f"{pack.title} {pack.collection} {' '.join(pack.topics)} {pack.kind}"
            ).casefold()
            lexical = sum(1.0 for term in terms if term in haystack)
            broad = 0.15 if not pack.topics else 0.0
            local_bonus = 0.15 if pack.local_only else 0.0
            scored.append((lexical + broad + local_bonus, pack))
        scored.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
        return [
            {
                "pack_id": pack.id,
                "title": pack.title,
                "collection": pack.collection,
                "kind": pack.kind,
                "query_mode": pack.query_mode,
                "local_only": pack.local_only,
                "score": round(score, 3),
                "authority": "knowledge evidence source only",
            }
            for score, pack in scored[: max(1, min(32, int(limit)))]
            if score > 0
        ]

    def index_local_pack(self, pack_id: str) -> dict[str, Any]:
        pack = self.get(pack_id)
        if pack.kind != "local_files":
            raise ValueError("only local_files packs are indexed by the built-in FTS index")
        root = Path(pack.location).resolve()
        self._ensure_index()
        files = 0
        indexed = 0
        skipped = 0
        fingerprints: list[str] = []
        source_manifest: list[dict[str, Any]] = []
        with self._connect() as db:
            db.execute("DELETE FROM documents WHERE pack_id = ?", (pack.id,))
            for path in root.rglob("*"):
                if not path.is_file() or path.is_symlink():
                    continue
                rel = path.relative_to(root)
                if not self._source_allowed(pack, rel):
                    skipped += 1
                    continue
                files += 1
                try:
                    if path.stat().st_size > _MAX_FILE_BYTES:
                        skipped += 1
                        continue
                    stat = path.stat()
                    body = self._read_document(path)
                    source_modified_at = datetime.fromtimestamp(
                        stat.st_mtime,
                        tz=timezone.utc,
                    ).isoformat()
                except (OSError, ValueError, zipfile.BadZipFile):
                    skipped += 1
                    continue
                if not body:
                    skipped += 1
                    continue
                digest = sha256(body.encode("utf-8")).hexdigest()
                locator_source = rel.as_posix()
                fingerprints.append(f"{locator_source}:{digest}")
                source_manifest.append({
                    "locator": locator_source,
                    "content_hash": digest,
                    "size_bytes": int(stat.st_size),
                    "source_modified_at": source_modified_at,
                })
                chunks = self._document_chunks(
                    body,
                    target_characters=self.DEFAULT_CHUNK_TARGET,
                    overlap_characters=self.DEFAULT_CHUNK_OVERLAP,
                )
                if not chunks:
                    skipped += 1
                    continue
                for chunk_index, chunk in enumerate(chunks):
                    chunk_digest = sha256(chunk.encode("utf-8")).hexdigest()
                    locator = (
                        rel.as_posix()
                        if len(chunks) == 1
                        else f"{rel.as_posix()}#chunk-{chunk_index + 1}"
                    )
                    db.execute(
                        "INSERT INTO documents("
                        "pack_id, locator, title, body, content_hash, indexed_at, source_modified_at"
                        ") VALUES(?,?,?,?,?,?,?)",
                        (
                            pack.id,
                            locator,
                            path.stem[:240],
                            chunk,
                            chunk_digest,
                            _now(),
                            source_modified_at,
                        ),
                    )
                    indexed += 1
            db.commit()
        combined = sha256("\n".join(sorted(fingerprints)).encode("utf-8")).hexdigest() if fingerprints else ""
        self._save_source_manifest(
            pack,
            source_manifest,
            content_fingerprint=combined,
        )
        self._update_fingerprint(pack.id, combined, indexed=indexed)
        return {
            "pack_id": pack.id,
            "files_seen": files,
            "indexed": indexed,
            "chunks_indexed": indexed,
            "skipped": skipped,
            "content_fingerprint": combined,
            "pipeline_fingerprint": self.local_index_pipeline_fingerprint(),
            "derivative_fingerprint": self.derivative_source_fingerprint(pack.id),
            "index": "sqlite_fts5_rebuildable",
        }

    def search(
        self,
        query: str,
        *,
        pack_ids: Iterable[str] = (),
        limit: int = 12,
        retrieval_mode: str = "auto",
    ) -> list[KnowledgeHit]:
        query = _text(query, 500)
        mode = _text(retrieval_mode, 40).casefold() or "auto"
        if mode not in self.RETRIEVAL_MODES:
            raise ValueError(
                f"retrieval_mode must be one of {sorted(self.RETRIEVAL_MODES)}"
            )
        if not query or mode == "off":
            return []
        selected = set(_tuple(pack_ids, limit=64, item_limit=160))
        results: list[KnowledgeHit] = []
        packs = [
            pack for pack in self.packs(enabled_only=True)
            if not selected or pack.id in selected
        ]
        for pack in packs:
            use_lexical = (
                pack.kind == "local_files"
                and (
                    mode in {"lexical", "hybrid"}
                    or (mode == "auto" and pack.query_mode in {"fts", "hybrid"})
                )
            )
            use_direct = (
                pack.kind == "kiwix"
                and (
                    mode in {"direct", "hybrid"}
                    or (mode == "auto" and pack.query_mode in {"direct", "hybrid"})
                )
            )
            if use_lexical:
                results.extend(self._search_fts(pack, query, limit=limit))
            elif use_direct:
                results.extend(self._search_kiwix(pack, query, limit=limit))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[: max(1, min(100, int(limit)))]

    def curation_report(self, pack_id: str = "") -> dict[str, Any]:
        """Inspect corpus hygiene without mutating source, registry, or indexes."""

        selected = [
            pack for pack in self.packs()
            if pack.kind == "local_files" and (not pack_id or pack.id == pack_id)
        ]
        if pack_id and not selected:
            raise KeyError(pack_id)

        packs: list[dict[str, Any]] = []
        hash_owners: dict[str, list[dict[str, str]]] = {}
        for pack in selected:
            documents = self.documents(pack.id)
            manifest = self._load_source_manifest(pack.id)
            manifest_rows = {
                str(item.get("locator") or ""): dict(item)
                for item in list(manifest.get("documents") or [])
                if isinstance(item, dict) and str(item.get("locator") or "")
            }
            indexed_sources = {str(item.get("locator") or "") for item in documents}
            manifest_sources = set(manifest_rows)
            disabled = set(pack.disabled_documents)

            for locator, row in manifest_rows.items():
                digest = str(row.get("content_hash") or "").strip()
                if digest:
                    hash_owners.setdefault(digest, []).append({
                        "pack_id": pack.id,
                        "locator": locator,
                    })

            refresh = self.local_refresh_plan(pack.id)
            drift = {
                "manifest_only": sorted(manifest_sources - indexed_sources)[:5000],
                "index_only": sorted(indexed_sources - manifest_sources)[:5000],
                "disabled_missing": sorted(disabled - manifest_sources)[:5000],
            }
            recommendations: list[str] = []
            if refresh["has_changes"]:
                recommendations.append("explicit_refresh")
            if drift["manifest_only"] or drift["index_only"]:
                recommendations.append("rebuild_derivative_index")
            if drift["disabled_missing"]:
                recommendations.append("review_stale_disabled_locators")

            packs.append({
                "pack_id": pack.id,
                "title": pack.title,
                "collection": pack.collection,
                "enabled": pack.enabled,
                "documents": len(manifest_sources),
                "indexed_sources": len(indexed_sources),
                "disabled_documents": len(disabled),
                "refresh": {
                    "added": len(refresh["added"]),
                    "changed": len(refresh["changed"]),
                    "removed": len(refresh["removed"]),
                    "skipped": refresh["skipped"],
                    "pipeline_changed": refresh["pipeline_changed"],
                    "has_changes": refresh["has_changes"],
                },
                "drift": drift,
                "recommendations": recommendations or ["none"],
            })

        duplicates = [
            {"content_hash": digest, "copies": owners}
            for digest, owners in sorted(hash_owners.items())
            if len(owners) > 1
        ][:2000]
        return {
            "version": 1,
            "pack_id": pack_id or None,
            "packs": packs,
            "duplicate_content_groups": duplicates,
            "duplicate_content_group_count": len(duplicates),
            "automatic_mutation_performed": False,
            "recommended_policy": (
                "review duplicate and stale sources explicitly; refresh/rebuild only "
                "after creator or operator approval"
            ),
            "authority": "curation evidence only; never implicit corpus mutation",
        }

    def status(self) -> dict[str, Any]:
        packs = self.packs()
        indexed_counts: dict[str, int] = {}
        if self.index_path.exists():
            try:
                with self._connect() as db:
                    for pack_id, count in db.execute(
                        "SELECT pack_id, COUNT(*) FROM documents GROUP BY pack_id"
                    ):
                        indexed_counts[str(pack_id)] = int(count)
            except sqlite3.Error:
                indexed_counts = {}
        return {
            "version": self.VERSION,
            "packs": len(packs),
            "enabled": sum(1 for pack in packs if pack.enabled),
            "local_only": sum(1 for pack in packs if pack.local_only),
            "indexed_documents": sum(indexed_counts.values()),
            "by_kind": {
                kind: sum(1 for pack in packs if pack.kind == kind)
                for kind in sorted({pack.kind for pack in packs})
            },
            "pack_documents": indexed_counts,
            "collections": {
                name: {
                    "packs": sum(1 for pack in packs if pack.collection == name),
                    "enabled": sum(
                        1 for pack in packs
                        if pack.collection == name and pack.enabled
                    ),
                }
                for name in sorted({pack.collection for pack in packs})
            },
            "disabled_documents": sum(len(pack.disabled_documents) for pack in packs),
            "ingest_policies": {
                policy: sum(1 for pack in packs if pack.ingest_policy == policy)
                for policy in sorted(self.INGEST_POLICIES)
            },
            "retrieval_modes": sorted(self.RETRIEVAL_MODES),
            "vector_backend": (
                "optional node-owned qdrant/qdrant-edge derivative; "
                "Core lexical/direct retrieval remains sufficient"
            ),
            "authority": "retrieved evidence only; never implicit memory/identity truth",
        }

    def substrate_profile(self) -> dict[str, Any]:
        """Return a cheap read-only map of Mary's local knowledge substrate.

        This inspects registry/index metadata only. It never scans source files,
        contacts Kiwix/Qdrant, rebuilds an index, or promotes retrieved evidence.
        """

        packs = self.packs()
        status = self.status()
        by_id = {pack.id: pack for pack in packs}
        tiers = {
            "active_local": [],
            "offline_reference": [],
            "semantic_derivative": [],
            "catalog_candidates": [],
        }
        stale_derivatives: list[dict[str, str]] = []
        enabled_retrieval_modes: set[str] = set()

        for pack in packs:
            if pack.query_mode == "catalog_only":
                tier = "catalog_candidates"
            elif pack.kind in {"qdrant", "qdrant_edge"}:
                tier = "semantic_derivative"
            elif pack.kind in {"kiwix", "kolibri"}:
                tier = "offline_reference"
            else:
                tier = "active_local"

            if pack.enabled and pack.query_mode != "catalog_only":
                enabled_retrieval_modes.add(pack.query_mode)

            vector_build = (
                dict(pack.metadata.get("vector_build") or {})
                if isinstance(pack.metadata, dict)
                else {}
            )
            derivative_state = ""
            if tier == "semantic_derivative":
                source_id = _text(vector_build.get("source_pack_id"), 160)
                source = by_id.get(source_id)
                built_from = _text(vector_build.get("source_fingerprint"), 128)
                current_source = (
                    self.derivative_source_fingerprint(source.id)
                    if source is not None
                    else ""
                )
                if not vector_build:
                    derivative_state = "unbuilt"
                elif source is None:
                    derivative_state = "source_missing"
                elif not built_from or not current_source:
                    derivative_state = "lineage_incomplete"
                elif built_from != current_source:
                    derivative_state = "stale"
                else:
                    derivative_state = "current"
                if derivative_state != "current":
                    stale_derivatives.append({
                        "pack_id": pack.id,
                        "source_pack_id": source_id,
                        "state": derivative_state,
                    })

            tiers[tier].append({
                "pack_id": pack.id,
                "title": pack.title,
                "kind": pack.kind,
                "collection": pack.collection,
                "enabled": pack.enabled,
                "query_mode": pack.query_mode,
                "ingest_policy": pack.ingest_policy,
                "local_only": pack.local_only,
                "indexed_chunks": int(
                    dict(status.get("pack_documents") or {}).get(pack.id, 0) or 0
                ),
                "content_fingerprint_present": bool(pack.content_fingerprint),
                "derivative_state": derivative_state or None,
            })

        return {
            "version": 1,
            "packs": len(packs),
            "enabled": int(status.get("enabled") or 0),
            "indexed_chunks": int(status.get("indexed_documents") or 0),
            "tiers": tiers,
            "counts": {name: len(rows) for name, rows in tiers.items()},
            "enabled_retrieval_modes": sorted(enabled_retrieval_modes),
            "stale_derivatives": stale_derivatives,
            "attention_required": bool(stale_derivatives),
            "automatic_scan_performed": False,
            "automatic_rebuild_performed": False,
            "authority": (
                "registry/index metadata projection only; source text remains "
                "evidence and derivative indexes remain rebuildable"
            ),
        }

    def seed_recommended_candidates(self) -> list[KnowledgePack]:
        """Create disabled catalog-only entries for useful local knowledge substrates."""

        candidates = (
            {
                "pack_id": "candidate_kiwix",
                "title": "Kiwix / OpenZIM offline library",
                "kind": "custom",
                "query_mode": "catalog_only",
                "location": "configure-local-kiwix-endpoint",
                "topics": ("wikipedia", "books", "medical", "devdocs", "stackexchange", "offline reference"),
                "license": "content-specific",
                "source": "Project NOMAD / Kiwix pattern",
                "metadata": {"recommended_runtime": "kiwix-serve", "status": "configure_then_register_as_kiwix"},
            },
            {
                "pack_id": "candidate_qdrant_edge",
                "title": "Qdrant Edge local semantic index",
                "kind": "qdrant_edge",
                "query_mode": "catalog_only",
                "location": "configure-local-edge-shard",
                "topics": ("semantic search", "embeddings", "offline vector retrieval"),
                "license": "Apache-2.0 / upstream terms",
                "source": "Qdrant Edge",
                "metadata": {"status": "optional_backend", "embedded": True},
            },
            {
                "pack_id": "candidate_local_docs",
                "title": "Mary local documents",
                "kind": "custom",
                "query_mode": "catalog_only",
                "location": "configure-local-document-root",
                "topics": ("personal documents", "manuals", "project references"),
                "license": "creator-owned",
                "source": "MaryV2",
                "metadata": {"status": "configure_then_register_as_local_files"},
            },
        )
        output = []
        for item in candidates:
            try:
                output.append(self.get(str(item["pack_id"])))
                continue
            except KeyError:
                pass
            output.append(self.register(
                **item,
                enabled=False,
                local_only=True,
                trust="candidate",
            ))
        return output

    def _search_fts(self, pack: KnowledgePack, query: str, *, limit: int) -> list[KnowledgeHit]:
        self._ensure_index()
        safe_terms = [
            token for token in re.findall(r"[A-Za-z0-9_'-]{2,}", query)[:12]
            if token
        ]
        if not safe_terms:
            return []
        fts_query = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in safe_terms)
        rows: list[tuple[Any, ...]] = []
        try:
            with self._connect() as db:
                rows = list(db.execute(
                    """
                    SELECT d.title,
                           snippet(documents_fts, 2, '[', ']', ' … ', 20),
                           d.locator,
                           d.content_hash,
                           bm25(documents_fts),
                           d.indexed_at,
                           d.source_modified_at
                    FROM documents_fts
                    JOIN documents AS d ON d.id = documents_fts.rowid
                    WHERE documents_fts MATCH ? AND documents_fts.pack_id = ?
                    ORDER BY bm25(documents_fts)
                    LIMIT ?
                    """,
                    (
                        fts_query,
                        pack.id,
                        max(1, min(200, int(limit) * 4)),
                    ),
                ))
        except sqlite3.Error:
            with self._connect() as db:
                rows = list(db.execute(
                    """
                    SELECT title, substr(body, 1, 500), locator, content_hash,
                           0.0, indexed_at, source_modified_at
                    FROM documents
                    WHERE pack_id = ? AND lower(body) LIKE ?
                    LIMIT ?
                    """,
                    (
                        pack.id,
                        f"%{query.casefold()}%",
                        max(1, min(200, int(limit) * 4)),
                    ),
                ))
        output: list[KnowledgeHit] = []
        disabled = set(pack.disabled_documents)
        for row in rows:
            source_path = self._document_source(str(row[2] or ""))
            if source_path in disabled:
                continue
            rank = float(row[4] or 0.0)
            content_hash = _text(row[3], 128)
            locator = _text(row[2], 500)
            output.append(KnowledgeHit(
                pack_id=pack.id,
                title=_text(row[0], 240),
                snippet=_text(row[1], 1200),
                source=f"{pack.title} / local_files",
                score=max(0.1, 1.0 / (1.0 + abs(rank))) - len(output) * 0.002,
                locator=locator,
                content_hash=content_hash,
                collection=pack.collection,
                source_date=_text(row[6], 80),
                indexed_at=_text(row[5], 80),
                citation_id=self._citation_id(
                    pack,
                    locator=locator,
                    content_hash=content_hash,
                ),
            ))
            if len(output) >= max(1, min(50, int(limit))):
                break
        return output

    def _search_kiwix(self, pack: KnowledgePack, query: str, *, limit: int) -> list[KnowledgeHit]:
        self._validate_local_endpoint(pack.location)
        base = pack.location.rstrip("/")
        params = {
            "pattern": query,
            "format": "xml",
            "pageLength": str(max(1, min(25, int(limit)))),
        }
        book = _text(pack.metadata.get("book") if pack.metadata else "", 160)
        if book:
            params["books.name"] = book
        url = f"{base}/search?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": "MaryV2-KnowledgeFabric/1"})
        with urlopen(request, timeout=5.0) as response:  # nosec B310 - endpoint is validated local/private
            payload = response.read(2 * 1024 * 1024)
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return []
        output: list[KnowledgeHit] = []
        entries = list(root.iter())
        for element in entries:
            tag = element.tag.rsplit("}", 1)[-1].casefold()
            if tag not in {"entry", "item"}:
                continue
            title = ""
            snippet = ""
            locator = ""
            for child in list(element):
                name = child.tag.rsplit("}", 1)[-1].casefold()
                if name == "title":
                    title = "".join(child.itertext())
                elif name in {"summary", "description", "content"}:
                    snippet = "".join(child.itertext())
                elif name == "link":
                    locator = str(child.attrib.get("href") or "")
            if not title:
                continue
            clean_title = _text(html.unescape(title), 240)
            clean_locator = _text(locator, 800)
            output.append(KnowledgeHit(
                pack_id=pack.id,
                title=clean_title,
                snippet=_text(html.unescape(re.sub(r"<[^>]+>", " ", snippet)), 1200),
                source=f"{pack.title} / Kiwix",
                score=max(0.1, 1.0 - len(output) * 0.03),
                locator=clean_locator,
                collection=pack.collection,
                source_date=_text(
                    (pack.metadata or {}).get("source_date"),
                    80,
                ),
                indexed_at="",
                citation_id=self._citation_id(
                    pack,
                    locator=clean_locator,
                    title=clean_title,
                ),
            ))
            if len(output) >= max(1, min(50, int(limit))):
                break
        return output

    def _update_fingerprint(self, pack_id: str, fingerprint: str, *, indexed: int) -> None:
        payload = self._load()
        for row in list(payload.get("packs") or []):
            if row.get("id") == pack_id:
                row["content_fingerprint"] = fingerprint
                row["updated_at"] = _now()
                metadata = dict(row.get("metadata") or {})
                metadata["indexed_documents"] = int(indexed)
                metadata["index_backend"] = "sqlite_fts5"
                metadata["index_pipeline_version"] = self.LOCAL_INDEX_PIPELINE_VERSION
                metadata["index_pipeline_fingerprint"] = (
                    self.local_index_pipeline_fingerprint()
                )
                row["metadata"] = metadata
                break
        self._save(payload)

    def record_vector_build(
        self,
        pack_id: str,
        *,
        source_pack_id: str,
        source_fingerprint: str,
        embedding_space_identity: str,
        vectors: int,
        rebuild_id: str,
    ) -> KnowledgePack:
        """Record content-free evidence for one successful derived vector build."""

        payload = self._load()
        found = False
        for row in list(payload.get("packs") or []):
            if str(row.get("id") or "") != pack_id:
                continue
            metadata = dict(row.get("metadata") or {})
            metadata["vector_build"] = {
                "source_pack_id": _text(source_pack_id, 160),
                "source_fingerprint": _text(source_fingerprint, 128),
                "embedding_space_identity": _text(
                    embedding_space_identity,
                    128,
                ),
                "vectors": max(0, int(vectors)),
                "rebuild_id": _text(rebuild_id, 128),
                "built_at": _now(),
            }
            row["metadata"] = metadata
            row["content_fingerprint"] = sha256(
                (
                    _text(source_fingerprint, 128)
                    + "|"
                    + _text(embedding_space_identity, 128)
                    + "|"
                    + _text(rebuild_id, 128)
                ).encode("utf-8")
            ).hexdigest()
            row["updated_at"] = _now()
            found = True
            break
        if not found:
            raise KeyError(pack_id)
        self._save(payload)
        return self.get(pack_id)

    def _ensure_index(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pack_id TEXT NOT NULL,
                    locator TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    indexed_at TEXT NOT NULL,
                    source_modified_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            columns = {
                str(row[1])
                for row in db.execute("PRAGMA table_info(documents)")
            }
            if "source_modified_at" not in columns:
                db.execute(
                    "ALTER TABLE documents ADD COLUMN "
                    "source_modified_at TEXT NOT NULL DEFAULT ''"
                )
            db.execute("CREATE INDEX IF NOT EXISTS idx_documents_pack ON documents(pack_id)")
            try:
                db.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                        pack_id UNINDEXED,
                        title,
                        body,
                        locator UNINDEXED,
                        content_hash UNINDEXED,
                        content='documents',
                        content_rowid='id'
                    )
                    """
                )
                db.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                      INSERT INTO documents_fts(rowid, pack_id, title, body, locator, content_hash)
                      VALUES (new.id, new.pack_id, new.title, new.body, new.locator, new.content_hash);
                    END
                    """
                )
                db.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                      INSERT INTO documents_fts(documents_fts, rowid, pack_id, title, body, locator, content_hash)
                      VALUES('delete', old.id, old.pack_id, old.title, old.body, old.locator, old.content_hash);
                    END
                    """
                )
            except sqlite3.OperationalError:
                pass
            db.commit()

    def _connect(self) -> sqlite3.Connection:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.index_path, timeout=5.0)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @classmethod
    def _read_document(cls, path: Path) -> str:
        suffix = path.suffix.casefold()
        if suffix == ".docx":
            with zipfile.ZipFile(path) as archive:
                root = ET.fromstring(archive.read("word/document.xml"))
            namespace = {
                "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            }
            paragraphs = []
            for paragraph in root.findall(".//w:p", namespace):
                text = "".join(
                    node.text or ""
                    for node in paragraph.findall(".//w:t", namespace)
                )
                clean = " ".join(text.split())
                if clean:
                    paragraphs.append(clean)
            return "\n\n".join(paragraphs)[:4_000_000]

        if suffix == ".epub":
            parts: list[str] = []
            with zipfile.ZipFile(path) as archive:
                names = [
                    name for name in archive.namelist()
                    if name.casefold().endswith((".html", ".htm", ".xhtml"))
                    and not name.startswith("__MACOSX/")
                ][:2000]
                for name in names:
                    try:
                        raw = archive.read(name).decode("utf-8", errors="ignore")
                    except (KeyError, OSError):
                        continue
                    normalized = cls._normalize_document(raw, ".html")
                    if normalized:
                        parts.append(normalized)
                    if sum(len(item) for item in parts) >= 4_000_000:
                        break
            return "\n\n".join(parts)[:4_000_000]

        if suffix == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore
            except Exception:
                return ""
            try:
                reader = PdfReader(str(path))
                parts = []
                for page in list(reader.pages)[:2000]:
                    text = " ".join(str(page.extract_text() or "").split())
                    if text:
                        parts.append(text)
                    if sum(len(item) for item in parts) >= 4_000_000:
                        break
                return "\n\n".join(parts)[:4_000_000]
            except Exception:
                return ""

        raw = path.read_text(encoding="utf-8", errors="ignore")
        return cls._normalize_document(raw, suffix)

    @staticmethod
    def _document_chunks(
        body: str,
        *,
        target_characters: int = 6000,
        overlap_characters: int = 500,
    ) -> list[str]:
        """Create paragraph-aware rebuildable retrieval chunks.

        Chunks are search artifacts only. They never become MemoryManager
        records and can always be regenerated from the creator-owned source.
        """

        text = str(body or "").strip()
        if not text:
            return []
        target = max(1200, min(20_000, int(target_characters)))
        overlap = max(0, min(target // 3, int(overlap_characters)))
        if len(text) <= target:
            return [text]

        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n|(?<=\.)\s+(?=[A-Z])", text)
            if paragraph.strip()
        ]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if len(paragraph) > target:
                if current:
                    chunks.append(current.strip())
                    current = ""
                start = 0
                while start < len(paragraph):
                    end = min(len(paragraph), start + target)
                    piece = paragraph[start:end].strip()
                    if piece:
                        chunks.append(piece)
                    if end >= len(paragraph):
                        break
                    start = max(start + 1, end - overlap)
                continue

            candidate = paragraph if not current else f"{current}\n\n{paragraph}"
            if len(candidate) <= target:
                current = candidate
                continue
            if current:
                chunks.append(current.strip())
                tail = current[-overlap:].strip() if overlap else ""
                if tail:
                    remaining = max(0, target - len(paragraph) - 2)
                    tail = tail[-remaining:].strip() if remaining else ""
                current = f"{tail}\n\n{paragraph}".strip() if tail else paragraph
            else:
                current = paragraph

        if current:
            chunks.append(current.strip())
        return [chunk for chunk in chunks if chunk][:20_000]

    @staticmethod
    def _normalize_document(raw: str, suffix: str) -> str:
        value = raw
        if suffix in {".html", ".htm"}:
            value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
            value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
            value = re.sub(r"<[^>]+>", " ", value)
            value = html.unescape(value)
        return "\n".join(line.strip() for line in value.splitlines() if line.strip())[:500_000]

    @staticmethod
    def _validate_local_endpoint(value: str) -> None:
        parsed = urlparse(str(value or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Kiwix endpoint must be an explicit HTTP(S) endpoint")
        hostname = parsed.hostname.casefold()
        if hostname in {"localhost", "127.0.0.1", "::1"}:
            return
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError as exc:
            raise ValueError(
                "Kiwix endpoint must be local/private: use localhost or a literal "
                "private/LAN IP; Mary will not resolve arbitrary hostnames from this adapter."
            ) from exc
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise ValueError("Kiwix endpoint must be local/private")

    @staticmethod
    def _validate_qdrant_endpoint(value: str) -> None:
        parsed = urlparse(str(value or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Qdrant endpoint must be an explicit HTTP(S) endpoint")
        hostname = parsed.hostname.casefold()
        if hostname in {"localhost", "127.0.0.1", "::1"}:
            return
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError as exc:
            raise ValueError(
                "Qdrant endpoint must be local/private: use localhost or a literal "
                "private/LAN IP; Mary will not resolve arbitrary hostnames from this adapter."
            ) from exc
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise ValueError("Qdrant endpoint must be local/private")

    @staticmethod
    def _validate_qdrant_metadata(metadata: dict[str, Any]) -> None:
        collection = str(metadata.get("qdrant_collection") or "").strip()
        model = str(metadata.get("embedding_model") or "").strip()
        identity = str(metadata.get("embedding_space_identity") or "").strip()
        try:
            dimensions = int(metadata.get("embedding_dimensions") or 0)
        except (TypeError, ValueError):
            dimensions = 0
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", collection):
            raise ValueError("Qdrant pack requires a safe qdrant_collection")
        if not model:
            raise ValueError("Qdrant pack requires embedding_model")
        if len(identity) < 16:
            raise ValueError("Qdrant pack requires embedding_space_identity")
        if dimensions < 1 or dimensions > 65536:
            raise ValueError("Qdrant pack requires valid embedding_dimensions")
        vector_name = str(metadata.get("vector_name") or "").strip()
        if vector_name and not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", vector_name):
            raise ValueError("Qdrant vector_name is invalid")

    @staticmethod
    def _citation_id(
        pack: KnowledgePack,
        *,
        locator: str,
        content_hash: str = "",
        title: str = "",
    ) -> str:
        digest = _text(content_hash, 128)
        if not digest:
            digest = sha256(
                f"{pack.id}|{locator}|{title}".encode("utf-8")
            ).hexdigest()
        return f"knowledge:{pack.id}:{digest[:16]}"

    @staticmethod
    def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
        denied = {"token", "authorization", "api_key", "secret", "password", "cookie"}
        output: dict[str, Any] = {}
        for key, value in list(dict(metadata or {}).items())[:24]:
            name = _text(key, 80)
            if not name or name.casefold() in denied:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                output[name] = value if not isinstance(value, str) else _text(value, 500)
            elif isinstance(value, (list, tuple)):
                output[name] = [
                    _text(item, 300)
                    for item in list(value)[:64]
                    if _text(item, 300)
                ]
            else:
                output[name] = _text(value, 500)
        return output

    @staticmethod
    def _decode_pack(row: dict[str, Any]) -> KnowledgePack:
        values = dict(row)
        values["topics"] = tuple(values.get("topics") or [])
        values.setdefault("collection", "default")
        values.setdefault("ingest_policy", "manual")
        values["disabled_documents"] = tuple(
            values.get("disabled_documents") or []
        )
        values["metadata"] = dict(values.get("metadata") or {})
        return KnowledgePack(**values)
