"""Mine creator-owned Unbeknownst prose into *review candidates* for Mary.

The miner is intentionally conservative:
- it never turns fictional events into AI Mary memory;
- it never labels raw excerpts as training-ready;
- it works locally on DOCX/TXT/MD without uploading the manuscript;
- it produces bounded scene candidates with chapter/provenance/fingerprint so
  the creator can derive behavioral invariants for the CharacterSourcebook or
  Mary Dataset after review.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any
from xml.etree import ElementTree as ET
import zipfile


_CHAPTER_RE = re.compile(r"^CHAPTER\s+(?P<number>\d+|[IVXLCDM]+)\b", re.I)
_QUOTE_RE = re.compile(r"[“”\"]")
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class NovelSceneCandidate:
    candidate_id: str
    chapter: str
    chapter_title: str
    paragraph_start: int
    paragraph_end: int
    mary_mentions: int
    dialogue_density: float
    text: str
    source_file: str
    source_sha256: str
    boundary: str = "fictional_canon_reference"
    training_eligible: bool = False
    requires_creator_review: bool = True
    suggested_use: str = "derive behavior invariant, reaction pattern, dialogue cadence, or negative example"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_paragraphs(path: str | Path) -> list[str]:
    source = Path(path).expanduser().resolve()
    suffix = source.suffix.casefold()
    if suffix == ".docx":
        with zipfile.ZipFile(source) as archive:
            xml = archive.read("word/document.xml")
        root = ET.fromstring(xml)
        namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs: list[str] = []
        for paragraph in root.findall(".//w:p", namespaces):
            text = "".join(
                node.text or ""
                for node in paragraph.findall(".//w:t", namespaces)
            )
            clean = _SPACE_RE.sub(" ", text).strip()
            if clean:
                paragraphs.append(clean)
        return paragraphs
    if suffix in {".txt", ".md"}:
        return [
            _SPACE_RE.sub(" ", line).strip()
            for line in source.read_text(encoding="utf-8", errors="ignore").splitlines()
            if _SPACE_RE.sub(" ", line).strip()
        ]
    raise ValueError("novel miner supports .docx, .txt and .md")


def mine_mary_scenes(
    path: str | Path,
    *,
    character_name: str = "Mary",
    context_paragraphs: int = 3,
    max_characters: int = 5000,
    priority_chapters: tuple[int, ...] = (3, 9, 12, 15, 19, 20, 22, 23, 26, 28, 29, 30),
) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    paragraphs = read_paragraphs(source)
    digest = sha256_path(source)
    name_re = re.compile(rf"\b{re.escape(character_name)}\b", re.I)
    chapter = "unknown"
    chapter_title = ""
    chapter_number: int | None = None
    chapter_map: list[tuple[str, str, int | None]] = []
    current = (chapter, chapter_title, chapter_number)

    # Resolve chapter identity at every paragraph so scene provenance survives
    # later manuscript edits better than page numbers alone.
    for index, paragraph in enumerate(paragraphs):
        match = _CHAPTER_RE.match(paragraph)
        if match:
            raw = match.group("number")
            chapter = f"CHAPTER {raw}"
            chapter_number = int(raw) if raw.isdigit() else None
            chapter_title = ""
            current = (chapter, chapter_title, chapter_number)
        elif chapter != "unknown" and not chapter_title and index > 0:
            # The canonical manuscript commonly places a short chapter title
            # directly after the chapter heading. Keep it only if it is short
            # and not prose/dialogue.
            if len(paragraph) <= 80 and not _QUOTE_RE.search(paragraph):
                chapter_title = paragraph
                current = (chapter, chapter_title, chapter_number)
        chapter_map.append(current)

    mention_indexes = [
        index for index, paragraph in enumerate(paragraphs)
        if name_re.search(paragraph)
    ]
    windows: list[tuple[int, int]] = []
    radius = max(1, min(12, int(context_paragraphs)))
    for index in mention_indexes:
        start = max(0, index - radius)
        end = min(len(paragraphs), index + radius + 1)
        if windows and start <= windows[-1][1] + 1:
            windows[-1] = (windows[-1][0], max(windows[-1][1], end))
        else:
            windows.append((start, end))

    candidates: list[NovelSceneCandidate] = []
    for ordinal, (start, end) in enumerate(windows):
        selected = paragraphs[start:end]
        text = "\n".join(selected)
        if len(text) > max_characters:
            text = text[: max(500, int(max_characters))].rstrip() + "\n…[bounded excerpt]"
        mary_mentions = len(name_re.findall(text))
        quoted = sum(1 for paragraph in selected if _QUOTE_RE.search(paragraph))
        dialogue_density = quoted / max(1, len(selected))
        chapter_value, title_value, number_value = chapter_map[min(start, len(chapter_map) - 1)]
        priority = number_value in set(priority_chapters) if number_value is not None else False
        candidate_id = sha256(
            f"{digest}:{start}:{end}:{character_name}".encode("utf-8")
        ).hexdigest()[:20]
        candidates.append(NovelSceneCandidate(
            candidate_id=f"novel_{candidate_id}",
            chapter=chapter_value,
            chapter_title=title_value,
            paragraph_start=start,
            paragraph_end=end - 1,
            mary_mentions=mary_mentions,
            dialogue_density=round(dialogue_density, 4),
            text=text,
            source_file=source.name,
            source_sha256=digest,
            suggested_use=(
                "priority calibration scene: derive behavior invariant, reaction pattern, "
                "dialogue cadence, or negative example"
                if priority
                else "derive behavior invariant only if it generalizes beyond fictional plot"
            ),
        ))

    candidates.sort(
        key=lambda item: (
            "priority calibration" in item.suggested_use,
            item.mary_mentions,
            item.dialogue_density,
        ),
        reverse=True,
    )
    return {
        "version": "mary-novel-miner-v1",
        "source": {
            "file": source.name,
            "sha256": digest,
            "paragraphs": len(paragraphs),
            "character": character_name,
        },
        "boundaries": {
            "fiction_is_ai_memory": False,
            "raw_excerpt_training_eligible": False,
            "creator_review_required": True,
            "character_bible_remains_authority": True,
            "recommended_derivation": (
                "convert reviewed recurring behavior into abstract Situation/Mary behavior "
                "records with DNA provenance; keep plot-specific facts FC-only"
            ),
        },
        "priority_chapters": list(priority_chapters),
        "candidates": [item.to_dict() for item in candidates],
    }


def write_mining_bundle(payload: dict[str, Any], output: str | Path) -> Path:
    target = Path(output).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return target
