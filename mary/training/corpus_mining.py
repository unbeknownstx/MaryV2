"""Read-only corpus inventory for Mary Dataset v1 planning.

This module measures the creator-owned character corpus before training or
synthetic expansion. It never rewrites the sourcebook, invents examples, treats
fiction as lived memory, or promotes any record into training automatically.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

from mary.character import CharacterSourcebook, MaryEvaluationSet


_BEHAVIOR_RE = re.compile(
    r"Situation:\s*(?P<situation>.+?)\s+Mary behavior:\s*(?P<behavior>.+?)"
    r"(?:\s+Performance tells:|\s+Avoid:|\s+Source/provenance:|$)",
    re.IGNORECASE,
)


def _share(count: int, total: int) -> float:
    return round(count / max(1, total), 4)


@dataclass(frozen=True)
class MaryCorpusMiningReport:
    version: str
    sourcebook_hash: str
    evaluation_fingerprint: str
    records: int
    sources: int
    source_kinds: int
    labels: dict[str, int]
    by_source: dict[str, int]
    by_source_kind: dict[str, int]
    structured_behavior_records: int
    training_candidate_records: int
    negative_records: int
    fictional_reference_records: int
    alternate_reference_records: int
    duplicate_content_groups: int
    dominant_source_share: float
    marybench_cases: int
    marybench_categories: dict[str, int]
    recommendations: tuple[str, ...]
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["recommendations"] = list(self.recommendations)
        payload["automatic_mutation_performed"] = False
        payload["training_performed"] = False
        payload["authority"] = "read_only_corpus_inventory"
        return payload


class MaryCorpusMiner:
    VERSION = "mary-corpus-mining-v1"

    def inspect(self, root: str | Path) -> MaryCorpusMiningReport:
        base = Path(root).expanduser().resolve()
        sourcebook = CharacterSourcebook.from_environment(root=base)
        evaluation = MaryEvaluationSet.from_environment(root=base)

        labels: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_kind: dict[str, int] = {}
        hashes: dict[str, list[str]] = {}
        structured = 0
        training_candidates = 0
        negatives = 0
        fiction = 0
        alternate = 0

        for record in sourcebook.records:
            record_labels = {
                str(item).strip().upper()
                for item in (getattr(record, "labels", ()) or ())
                if str(item).strip()
            }
            for label in sorted(record_labels):
                labels[label] = labels.get(label, 0) + 1

            source_name = str(getattr(record, "source_name", "") or "unknown")[:240]
            source_kind = str(getattr(record, "source_kind", "") or "unknown")[:120]
            by_source[source_name] = by_source.get(source_name, 0) + 1
            by_kind[source_kind] = by_kind.get(source_kind, 0) + 1

            digest = str(getattr(record, "content_hash", "") or "").strip()
            if digest:
                hashes.setdefault(digest, []).append(str(record.record_id))

            text = str(getattr(record, "text", "") or "")
            training_blocked = bool(
                record_labels.intersection({"NEG", "FC", "ALT"})
            )
            if _BEHAVIOR_RE.search(text) and not training_blocked:
                structured += 1
            if (
                record_labels.intersection({"AI", "DNA", "PUB"})
                and not training_blocked
            ):
                training_candidates += 1
            if "NEG" in record_labels:
                negatives += 1
            if "FC" in record_labels:
                fiction += 1
            if "ALT" in record_labels:
                alternate += 1

        duplicate_groups = sum(1 for owners in hashes.values() if len(owners) > 1)
        total = len(sourcebook.records)
        dominant_source_share = (
            max((_share(count, total) for count in by_source.values()), default=0.0)
            if total
            else 0.0
        )
        categories: dict[str, int] = {}
        for case in evaluation.cases:
            key = str(case.category or "character")[:80]
            categories[key] = categories.get(key, 0) + 1

        recommendations: list[str] = []
        if structured < 32:
            recommendations.append(
                "expand creator-authored Situation/Mary behavior records before relying on LoRA character learning"
            )
        if negatives < 8:
            recommendations.append(
                "add more NEG anti-examples for generic-assistant drift, identity leakage, and overperformance"
            )
        if dominant_source_share > 0.75 and len(by_source) > 1:
            recommendations.append(
                "review source balance; one source contributes more than 75% of the active corpus"
            )
        if duplicate_groups:
            recommendations.append(
                f"review {duplicate_groups} exact duplicate content group(s) before synthetic expansion"
            )
        if len(evaluation.cases) < 50:
            recommendations.append(
                "expand held-out MaryBench coverage before comparing adapters"
            )
        if not fiction:
            recommendations.append(
                "keep explicit FC references for fictional canon boundaries where useful; never convert them to AI-Mary lived memory"
            )
        if not recommendations:
            recommendations.append(
                "corpus inventory has no obvious structural gap; continue creator review and held-out evaluation expansion"
            )

        payload = (
            f"{self.VERSION}|{sourcebook.sourcebook_hash}|{evaluation.fingerprint}|"
            f"{total}|{structured}|{negatives}|{fiction}|{duplicate_groups}"
        )
        fingerprint = sha256(payload.encode("utf-8")).hexdigest()[:24]

        return MaryCorpusMiningReport(
            version=self.VERSION,
            sourcebook_hash=sourcebook.sourcebook_hash,
            evaluation_fingerprint=evaluation.fingerprint,
            records=total,
            sources=len(by_source),
            source_kinds=len(by_kind),
            labels=dict(sorted(labels.items())),
            by_source=dict(sorted(by_source.items())),
            by_source_kind=dict(sorted(by_kind.items())),
            structured_behavior_records=structured,
            training_candidate_records=training_candidates,
            negative_records=negatives,
            fictional_reference_records=fiction,
            alternate_reference_records=alternate,
            duplicate_content_groups=duplicate_groups,
            dominant_source_share=dominant_source_share,
            marybench_cases=len(evaluation.cases),
            marybench_categories=dict(sorted(categories.items())),
            recommendations=tuple(recommendations),
            fingerprint=fingerprint,
        )
