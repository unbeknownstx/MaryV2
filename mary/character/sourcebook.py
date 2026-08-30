"""Authored character sourcebook for MaryV2.

The sourcebook is a *read-only character authority bridge*.  It lets the live
Mary runtime use creator-authored material (Character Bible, corpus, canon,
performance notes, voice direction, etc.) without turning those documents into
Mary's lived AI memory or another mutable personality database.

Important boundaries:
- ``Character`` / Character Core remains the compact bootstrap/fallback.
- Relationship, memory, developed-self, and agency retain their existing owners.
- Fictional canon may inform behavior but is never automatically an AI-Mary
  lived experience.
- Provider output never writes into this sourcebook.
- Retrieval is bounded; the whole corpus is never dumped into a model prompt.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile


class CharacterEvidenceLabel(str, Enum):
    """Creator-facing evidence labels used by the definitive Mary Bible."""

    FICTIONAL_CANON = "FC"
    SHARED_DNA = "DNA"
    AI_MARY = "AI"
    PUBLIC_PERFORMER = "PUB"
    ALTERNATE = "ALT"
    NEGATIVE = "NEG"
    UNSPECIFIED = "UNSPECIFIED"


_LABEL_RE = re.compile(r"\[(FC|DNA|AI|PUB|ALT|NEG)\]", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")

# These are tiny ranking weights, not identity rules.  Shared DNA and explicit
# AI-Mary material are normally most useful to a conversational turn; negative
# examples are valuable when the current input resembles a failure mode.
_LABEL_WEIGHT = {
    CharacterEvidenceLabel.SHARED_DNA: 1.45,
    CharacterEvidenceLabel.AI_MARY: 1.35,
    CharacterEvidenceLabel.PUBLIC_PERFORMER: 1.10,
    CharacterEvidenceLabel.NEGATIVE: 1.05,
    CharacterEvidenceLabel.FICTIONAL_CANON: 0.95,
    CharacterEvidenceLabel.ALTERNATE: 0.55,
    CharacterEvidenceLabel.UNSPECIFIED: 0.75,
}

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can",
    "do", "does", "for", "from", "had", "has", "have", "he", "her", "hers",
    "him", "his", "i", "if", "in", "is", "it", "its", "mary", "me", "my",
    "of", "on", "or", "our", "she", "so", "that", "the", "their", "them",
    "they", "this", "to", "unbe", "we", "what", "when", "where", "which",
    "who", "why", "with", "would", "you", "your",
}


@dataclass(frozen=True)
class CharacterSourceRecord:
    """One bounded authored evidence record."""

    record_id: str
    text: str
    source_path: str
    source_name: str
    source_kind: str
    labels: tuple[str, ...] = ()
    heading: str = ""
    ordinal: int = 0
    content_hash: str = ""
    provenance: str = "creator_authored"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_text: bool = True) -> dict[str, Any]:
        data = asdict(self)
        if not include_text:
            data.pop("text", None)
        return data

    @property
    def evidence_labels(self) -> tuple[CharacterEvidenceLabel, ...]:
        resolved: list[CharacterEvidenceLabel] = []
        for item in self.labels:
            try:
                resolved.append(CharacterEvidenceLabel(str(item).upper()))
            except ValueError:
                continue
        return tuple(resolved) or (CharacterEvidenceLabel.UNSPECIFIED,)

    @property
    def is_negative_example(self) -> bool:
        return CharacterEvidenceLabel.NEGATIVE in self.evidence_labels

    @property
    def is_fictional_canon(self) -> bool:
        return CharacterEvidenceLabel.FICTIONAL_CANON in self.evidence_labels

    @property
    def is_ai_mary(self) -> bool:
        return CharacterEvidenceLabel.AI_MARY in self.evidence_labels


@dataclass(frozen=True)
class CharacterSourceSelection:
    """LLM-safe, bounded projection of authored character evidence."""

    query: str
    records: tuple[CharacterSourceRecord, ...]
    total_records: int
    sourcebook_hash: str

    def prompt_view(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for record in self.records:
            items.append({
                "id": record.record_id,
                "labels": list(record.labels) or [CharacterEvidenceLabel.UNSPECIFIED.value],
                "kind": record.source_kind,
                "source": record.source_name,
                "heading": record.heading,
                "text": record.text,
                "boundary": (
                    "fictional_reference_not_ai_memory"
                    if record.is_fictional_canon
                    else "negative_example_not_character_instruction"
                    if record.is_negative_example
                    else "authored_character_evidence"
                ),
            })
        return {
            "policy": (
                "Creator-authored Mary evidence. Use it to realize Mary's character; "
                "never convert fictional canon into AI lived memory and never imitate NEG examples."
            ),
            "sourcebook_hash": self.sourcebook_hash,
            "records": items,
        }


class CharacterSourcebook:
    """Read-only collection of creator-authored Mary material.

    ``from_environment`` intentionally loads only explicitly configured sources
    plus conventional ``character_sources/`` directories.  It does not crawl the
    entire repository or user's filesystem.
    """

    VERSION = "1.0"
    SUPPORTED_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".docx"}
    MAX_FILES = 64
    MAX_RECORDS = 6000
    MAX_RECORD_CHARS = 1800

    def __init__(
        self,
        records: Iterable[CharacterSourceRecord] = (),
        *,
        configured_paths: Iterable[str] = (),
        load_errors: Iterable[str] = (),
    ) -> None:
        self.records = tuple(list(records)[: self.MAX_RECORDS])
        self.configured_paths = tuple(str(item) for item in configured_paths)
        self.load_errors = tuple(str(item)[:500] for item in load_errors)
        digest = sha256()
        for record in self.records:
            digest.update(record.record_id.encode("utf-8", errors="ignore"))
            digest.update(record.content_hash.encode("ascii", errors="ignore"))
        self.sourcebook_hash = digest.hexdigest()[:20]

    @classmethod
    def empty(cls) -> "CharacterSourcebook":
        return cls(())

    @classmethod
    def from_environment(cls, *, root: str | Path | None = None) -> "CharacterSourcebook":
        base = Path(root) if root is not None else Path.cwd()
        raw = str(os.getenv("MARY_CHARACTER_SOURCES", "") or "").strip()
        paths: list[Path] = []
        if raw:
            # Semicolon is canonical because Mary's primary host is Windows.
            # Accept os.pathsep too when it differs and no semicolon was used.
            parts = raw.split(";") if ";" in raw else raw.split(os.pathsep)
            paths.extend(Path(part.strip()).expanduser() for part in parts if part.strip())
        else:
            for candidate in (
                base / "character_sources",
                base / "docs" / "character" / "sources",
            ):
                if candidate.exists():
                    paths.append(candidate)
        return cls.from_paths(paths)

    @classmethod
    def from_paths(cls, paths: Iterable[str | Path]) -> "CharacterSourcebook":
        files: list[Path] = []
        configured: list[str] = []
        errors: list[str] = []
        for raw in list(paths)[: cls.MAX_FILES]:
            path = Path(raw).expanduser()
            configured.append(str(path))
            if not path.exists():
                errors.append(f"missing character source: {path}")
                continue
            if path.is_dir():
                for child in sorted(path.rglob("*")):
                    if child.is_file() and child.suffix.lower() in cls.SUPPORTED_SUFFIXES:
                        files.append(child)
                        if len(files) >= cls.MAX_FILES:
                            break
            elif path.suffix.lower() in cls.SUPPORTED_SUFFIXES:
                files.append(path)
            else:
                errors.append(f"unsupported character source: {path}")
            if len(files) >= cls.MAX_FILES:
                break

        records: list[CharacterSourceRecord] = []
        for path in files[: cls.MAX_FILES]:
            try:
                records.extend(cls._records_from_file(path, remaining=cls.MAX_RECORDS - len(records)))
            except Exception as exc:  # fail soft: authored source is optional at boot
                errors.append(f"{path}: {type(exc).__name__}: {exc}")
            if len(records) >= cls.MAX_RECORDS:
                break
        return cls(records, configured_paths=configured, load_errors=errors)

    @classmethod
    def _records_from_file(cls, path: Path, *, remaining: int) -> list[CharacterSourceRecord]:
        suffix = path.suffix.lower()
        if suffix == ".docx":
            blocks = cls._docx_blocks(path)
        elif suffix == ".json":
            blocks = cls._json_blocks(path)
        elif suffix == ".jsonl":
            blocks = cls._jsonl_blocks(path)
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            blocks = cls._text_blocks(text)

        source_hash = sha256(path.read_bytes()).hexdigest()
        source_kind = cls._infer_source_kind(path.name)
        result: list[CharacterSourceRecord] = []
        heading = ""
        for ordinal, block in enumerate(blocks, start=1):
            if len(result) >= max(0, remaining):
                break
            text = cls._clean(block.get("text", ""))
            if not text:
                continue
            candidate_heading = cls._clean(block.get("heading", ""))
            if candidate_heading:
                heading = candidate_heading
            labels = tuple(cls._labels(text, block.get("labels")))
            text = _LABEL_RE.sub("", text).strip()
            if not text:
                continue
            # Split very large prose blocks so retrieval stays bounded.
            for piece in cls._split_text(text):
                if len(result) >= max(0, remaining):
                    break
                content_hash = sha256(piece.encode("utf-8")).hexdigest()
                record_id = sha256(
                    f"{source_hash}:{ordinal}:{len(result)}:{content_hash}".encode("utf-8")
                ).hexdigest()[:18]
                result.append(CharacterSourceRecord(
                    record_id=record_id,
                    text=piece,
                    source_path=str(path),
                    source_name=path.name,
                    source_kind=source_kind,
                    labels=labels,
                    heading=heading[:240],
                    ordinal=ordinal,
                    content_hash=content_hash[:20],
                    metadata={"source_hash": source_hash[:20]},
                ))
        return result

    @staticmethod
    def _infer_source_kind(name: str) -> str:
        value = name.lower()
        for marker, kind in (
            ("bible", "character_bible"),
            ("corpus", "character_corpus"),
            ("dialog", "dialogue_corpus"),
            ("voice", "voice_direction"),
            ("perform", "performance_direction"),
            ("manga", "manga_reference"),
            ("anim", "animation_reference"),
            ("book", "book_reference"),
            ("unbeknownst", "fictional_canon"),
            ("canon", "canon"),
        ):
            if marker in value:
                return kind
        return "character_source"

    @staticmethod
    def _clean(value: Any) -> str:
        return " ".join(str(value or "").replace("\u00a0", " ").split())

    @classmethod
    def _split_text(cls, text: str) -> list[str]:
        if len(text) <= cls.MAX_RECORD_CHARS:
            return [text]
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) + 1 > cls.MAX_RECORD_CHARS and current:
                chunks.append(current.strip())
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            chunks.append(current.strip())
        return chunks or [text[: cls.MAX_RECORD_CHARS]]

    @staticmethod
    def _labels(text: str, explicit: Any = None) -> list[str]:
        values: list[str] = []
        if isinstance(explicit, str):
            explicit = [explicit]
        if isinstance(explicit, (list, tuple, set)):
            for item in explicit:
                name = str(item).strip().upper().strip("[]")
                if name in {item.value for item in CharacterEvidenceLabel if item is not CharacterEvidenceLabel.UNSPECIFIED}:
                    values.append(name)
        for match in _LABEL_RE.findall(str(text or "")):
            values.append(match.upper())
        return list(dict.fromkeys(values))

    @classmethod
    def _text_blocks(cls, text: str) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        heading = ""
        buffer: list[str] = []

        def flush() -> None:
            nonlocal buffer
            body = " ".join(part.strip() for part in buffer if part.strip()).strip()
            if body:
                blocks.append({"heading": heading, "text": body})
            buffer = []

        for line in str(text).splitlines():
            matched = _HEADING_RE.match(line)
            if matched:
                flush()
                heading = matched.group(1).strip()
                continue
            if not line.strip():
                flush()
            else:
                buffer.append(line)
        flush()
        return blocks

    @classmethod
    def _docx_blocks(cls, path: Path) -> list[dict[str, Any]]:
        """Read DOCX paragraphs/tables using only the standard library."""
        try:
            with ZipFile(path) as archive:
                xml = archive.read("word/document.xml")
        except (BadZipFile, KeyError) as exc:
            raise ValueError("invalid DOCX character source") from exc

        root = ET.fromstring(xml)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        blocks: list[dict[str, Any]] = []
        heading = ""
        for paragraph in root.findall(".//w:p", ns):
            pieces = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
            text = cls._clean("".join(pieces))
            if not text:
                continue
            style_node = paragraph.find("./w:pPr/w:pStyle", ns)
            style = ""
            if style_node is not None:
                style = str(style_node.attrib.get(f"{{{ns['w']}}}val", ""))
            if style.lower().startswith("heading") or style.lower().startswith("title"):
                heading = text
                continue
            blocks.append({"heading": heading, "text": text})
        return blocks

    @classmethod
    def _json_blocks(cls, path: Path) -> list[dict[str, Any]]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("records", data.get("items", [data]))
        if not isinstance(data, list):
            data = [data]
        blocks: list[dict[str, Any]] = []
        for item in data:
            if isinstance(item, str):
                blocks.append({"text": item})
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("response") or ""
                if text:
                    blocks.append({
                        "text": text,
                        "heading": item.get("heading") or item.get("title") or item.get("prompt") or "",
                        "labels": item.get("labels") or item.get("evidence_labels") or [],
                    })
        return blocks

    @classmethod
    def _jsonl_blocks(cls, path: Path) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if isinstance(item, str):
                blocks.append({"text": item})
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("response") or ""
                if text:
                    blocks.append({
                        "text": text,
                        "heading": item.get("heading") or item.get("title") or item.get("prompt") or "",
                        "labels": item.get("labels") or item.get("evidence_labels") or [],
                    })
        return blocks

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return {
            token.lower()
            for token in _WORD_RE.findall(str(value or ""))
            if len(token) > 2 and token.lower() not in _STOPWORDS
        }

    def select(
        self,
        query: str,
        *,
        limit: int = 6,
        max_characters: int = 4200,
    ) -> CharacterSourceSelection:
        """Retrieve the smallest relevant authored character evidence set."""
        if not self.records:
            return CharacterSourceSelection(str(query), (), 0, self.sourcebook_hash)
        query_tokens = self._tokens(query)
        lowered = str(query or "").lower()
        negative_context = any(word in lowered for word in ("wrong", "not mary", "generic", "bad response", "avoid", "never"))
        public_context = any(word in lowered for word in ("stream", "audience", "public", "chat", "perform"))

        scored: list[tuple[float, CharacterSourceRecord]] = []
        for record in self.records:
            body_tokens = self._tokens(f"{record.heading} {record.text}")
            exact_overlap = len(query_tokens.intersection(body_tokens))
            related_overlap = 0
            for query_token in query_tokens:
                if query_token in body_tokens or len(query_token) < 5:
                    continue
                if any(
                    len(body_token) >= 5
                    and (body_token.startswith(query_token) or query_token.startswith(body_token))
                    for body_token in body_tokens
                ):
                    related_overlap += 1
            overlap = exact_overlap + (0.65 * related_overlap)
            if query_tokens:
                lexical = overlap / max(1.0, len(query_tokens) ** 0.5)
            else:
                lexical = 0.0
            labels = record.evidence_labels
            label_weight = max(_LABEL_WEIGHT.get(label, 0.75) for label in labels)
            phrase_bonus = 0.0
            for token in query_tokens:
                if token in record.heading.lower():
                    phrase_bonus += 0.18
            context_bonus = 0.0
            if negative_context and record.is_negative_example:
                context_bonus += 0.8
            if public_context and CharacterEvidenceLabel.PUBLIC_PERFORMER in labels:
                context_bonus += 0.5
            # With no lexical overlap, only allow high-authority baseline records
            # when the query is tiny; otherwise irrelevant material stays out.
            score = lexical * label_weight + phrase_bonus + context_bonus
            if score > 0.0:
                scored.append((score, record))

        scored.sort(key=lambda row: (row[0], -row[1].ordinal), reverse=True)
        chosen: list[CharacterSourceRecord] = []
        used = 0
        for _score, record in scored:
            if len(chosen) >= max(1, min(int(limit), 12)):
                break
            cost = len(record.text) + len(record.heading) + 80
            if chosen and used + cost > max(500, int(max_characters)):
                continue
            chosen.append(record)
            used += cost
        return CharacterSourceSelection(str(query), tuple(chosen), len(self.records), self.sourcebook_hash)

    def snapshot(self) -> dict[str, Any]:
        labels: dict[str, int] = {}
        kinds: dict[str, int] = {}
        sources: dict[str, int] = {}
        for record in self.records:
            kinds[record.source_kind] = kinds.get(record.source_kind, 0) + 1
            sources[record.source_name] = sources.get(record.source_name, 0) + 1
            for label in record.evidence_labels:
                labels[label.value] = labels.get(label.value, 0) + 1
        return {
            "enabled": bool(self.records),
            "version": self.VERSION,
            "records": len(self.records),
            "sources": len(sources),
            "source_names": sorted(sources)[:32],
            "kinds": kinds,
            "labels": labels,
            "sourcebook_hash": self.sourcebook_hash,
            "configured_paths": list(self.configured_paths)[:32],
            "errors": list(self.load_errors)[:16],
            "semantics": {
                "authored_character_authority": True,
                "ai_lived_memory_owner": False,
                "mutable_by_model_output": False,
                "whole_corpus_prompt_dump": False,
            },
        }
