"""Rebuildable document-evidence synchronization for MaryV2.

This module mines useful local-document/RAG patterns without introducing a
second memory authority. Creator files remain authoritative. The cognitive
reservoir/vector index may receive derived records that can be deleted and
rebuilt at any time.

No directory is crawled automatically at import/startup. Hosts must explicitly
supply approved paths. This module performs no cloud calls and no background
watching by itself.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable


SUPPORTED_TEXT_SUFFIXES = frozenset({
    ".txt", ".md", ".markdown", ".json", ".jsonl", ".csv", ".py", ".js", ".ts",
    ".tsx", ".jsx", ".html", ".css", ".yaml", ".yml", ".toml", ".ini", ".cfg",
})


@dataclass(frozen=True)
class DocumentFingerprint:
    path: str
    content_hash: str
    size_bytes: int
    modified_ns: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DocumentSyncDecision:
    path: str
    action: str
    reason: str
    fingerprint: DocumentFingerprint | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.fingerprint is not None:
            data["fingerprint"] = self.fingerprint.to_dict()
        return data


class DocumentEvidencePlanner:
    """Plan explicit local evidence refreshes without owning documents."""

    VERSION = "13.28"

    def __init__(
        self,
        *,
        max_files: int = 256,
        max_file_bytes: int = 2_000_000,
        max_chunk_characters: int = 1800,
    ) -> None:
        self.max_files = max(1, min(5000, int(max_files)))
        self.max_file_bytes = max(1024, min(100_000_000, int(max_file_bytes)))
        self.max_chunk_characters = max(256, min(8000, int(max_chunk_characters)))

    def fingerprint(self, path: str | Path) -> DocumentFingerprint:
        target = Path(path).expanduser().resolve()
        stat = target.stat()
        if not target.is_file():
            raise ValueError("document evidence path must be a file")
        if stat.st_size > self.max_file_bytes:
            raise ValueError("document exceeds configured evidence file budget")
        digest = sha256(target.read_bytes()).hexdigest()
        return DocumentFingerprint(
            path=str(target),
            content_hash=digest,
            size_bytes=int(stat.st_size),
            modified_ns=int(stat.st_mtime_ns),
        )

    def plan(
        self,
        paths: Iterable[str | Path],
        previous_manifest: dict[str, Any] | None = None,
    ) -> tuple[DocumentSyncDecision, ...]:
        prior = dict((previous_manifest or {}).get("documents") or {})
        decisions: list[DocumentSyncDecision] = []
        seen: set[str] = set()

        for raw in list(paths)[: self.max_files]:
            target = Path(raw).expanduser().resolve()
            key = str(target)
            if key in seen:
                continue
            seen.add(key)
            if not target.exists():
                decisions.append(DocumentSyncDecision(key, "skip", "missing"))
                continue
            if not target.is_file():
                decisions.append(DocumentSyncDecision(key, "skip", "not_a_file"))
                continue
            if target.suffix.lower() not in SUPPORTED_TEXT_SUFFIXES:
                decisions.append(DocumentSyncDecision(key, "skip", "unsupported_type"))
                continue
            try:
                current = self.fingerprint(target)
            except ValueError as exc:
                decisions.append(DocumentSyncDecision(key, "skip", str(exc)))
                continue
            old = dict(prior.get(key) or {})
            if str(old.get("content_hash") or "") == current.content_hash:
                decisions.append(DocumentSyncDecision(key, "unchanged", "content_hash_match", current))
            else:
                decisions.append(DocumentSyncDecision(key, "refresh", "new_or_changed_document", current))

        # Manifest entries no longer present in the explicitly supplied set are
        # marked stale so a host can remove their derived reservoir records.
        for key in sorted(set(prior) - seen):
            decisions.append(DocumentSyncDecision(key, "remove", "no_longer_in_approved_set"))
        return tuple(decisions)

    def manifest(self, decisions: Iterable[DocumentSyncDecision]) -> dict[str, Any]:
        documents: dict[str, Any] = {}
        for decision in decisions:
            if decision.action in {"refresh", "unchanged"} and decision.fingerprint is not None:
                documents[decision.path] = decision.fingerprint.to_dict()
        return {
            "version": self.VERSION,
            "documents": documents,
            "authority": "derived_evidence_manifest_only",
        }

    def records_for_file(self, path: str | Path) -> list[Any]:
        """Create rebuildable CognitiveReservoir records for one approved text file."""
        target = Path(path).expanduser().resolve()
        fingerprint = self.fingerprint(target)
        if target.suffix.lower() not in SUPPORTED_TEXT_SUFFIXES:
            return []
        text = target.read_text(encoding="utf-8", errors="replace")
        chunks = self._chunks(text)
        from mary.mind.reservoir import ReservoirRecord

        records: list[ReservoirRecord] = []
        source_id = fingerprint.content_hash[:16]
        for index, chunk in enumerate(chunks):
            record_id = f"document:{source_id}:{index:04d}"
            records.append(ReservoirRecord(
                record_id=record_id,
                kind="document_evidence",
                subject=target.name,
                predicate="contains",
                content=chunk,
                source=str(target),
                authority="creator_file_derived",
                confidence=1.0,
                tags=("document", target.suffix.lower().lstrip(".")),
                metadata={
                    "content_hash": fingerprint.content_hash,
                    "chunk_index": index,
                    "derived": True,
                    "canonical_owner": "creator_file",
                },
            ))
        return records

    def _chunks(self, text: str) -> list[str]:
        cleaned = "\n".join(line.rstrip() for line in str(text).splitlines()).strip()
        if not cleaned:
            return []
        chunks: list[str] = []
        current = ""
        for paragraph in cleaned.split("\n\n"):
            paragraph = " ".join(paragraph.split())
            if not paragraph:
                continue
            if len(paragraph) > self.max_chunk_characters:
                parts = [
                    paragraph[i : i + self.max_chunk_characters]
                    for i in range(0, len(paragraph), self.max_chunk_characters)
                ]
            else:
                parts = [paragraph]
            for part in parts:
                if current and len(current) + len(part) + 2 > self.max_chunk_characters:
                    chunks.append(current)
                    current = ""
                current = f"{current}\n\n{part}".strip() if current else part
        if current:
            chunks.append(current)
        return chunks


def save_manifest(manifest: dict[str, Any], path: str | Path) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def load_manifest(path: str | Path) -> dict[str, Any]:
    target = Path(path).expanduser()
    if not target.exists():
        return {"version": DocumentEvidencePlanner.VERSION, "documents": {}}
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("document evidence manifest must be an object")
    return payload
