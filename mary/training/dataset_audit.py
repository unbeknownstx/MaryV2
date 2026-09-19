"""Deterministic quality audit for Mary Dataset v1.

The auditor is intentionally read-only. It checks exported artifacts before any
MLX/LoRA preparation without using an LLM and without rewriting dataset rows.
It focuses on provenance, split leakage, duplicate examples, MaryBench
contamination and fiction/negative-example boundaries.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable


_REQUIRED_FILES = (
    "manifest.json",
    "mary_character_corpus.jsonl",
    "mary_character_training_candidates.jsonl",
    "mary_behavior_sft.jsonl",
    "mary_negative_examples.jsonl",
    "mary_character_eval.jsonl",
)

_SPACE_RE = re.compile(r"\s+")


def _normalize(value: Any) -> str:
    return _SPACE_RE.sub(" ", str(value or "")).strip().casefold()


def _signature(parts: Iterable[Any]) -> str:
    joined = "\n".join(_normalize(item) for item in parts if _normalize(item))
    return sha256(joined.encode("utf-8")).hexdigest()[:24] if joined else ""


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    if not path.exists():
        return rows, [f"missing:{path.name}"]
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            errors.append(f"invalid_json:{path.name}:{number}")
            continue
        if not isinstance(value, dict):
            errors.append(f"non_object:{path.name}:{number}")
            continue
        rows.append(value)
    return rows, errors


def _messages_signature(row: dict[str, Any]) -> str:
    messages = list(row.get("messages") or [])
    return _signature(
        f"{str(item.get('role') or '')}:{str(item.get('content') or '')}"
        for item in messages
        if isinstance(item, dict)
    )


def _user_prompt_signature(row: dict[str, Any]) -> str:
    for item in list(row.get("messages") or []):
        if isinstance(item, dict) and str(item.get("role") or "").casefold() == "user":
            return _signature((item.get("content"),))
    return ""


@dataclass(frozen=True)
class MaryDatasetAuditReport:
    version: str
    dataset_fingerprint: str
    training_rows: int
    train_rows: int
    validation_rows: int
    test_rows: int
    duplicate_groups: int
    split_leakage_groups: int
    marybench_prompt_leaks: int
    boundary_violations: int
    source_dominance: float
    blocking_issues: tuple[str, ...]
    warnings: tuple[str, ...]
    training_ready: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blocking_issues"] = list(self.blocking_issues)
        payload["warnings"] = list(self.warnings)
        payload["promotion_performed"] = False
        payload["authority"] = "read_only_dataset_quality_evidence"
        return payload


class MaryDatasetV1Auditor:
    VERSION = "mary-dataset-audit-v1"

    def audit(
        self,
        dataset_dir: str | Path,
        *,
        minimum_train_examples: int = 8,
        maximum_single_source_share: float = 0.80,
    ) -> MaryDatasetAuditReport:
        root = Path(dataset_dir).expanduser().resolve()
        blocking: list[str] = []
        warnings: list[str] = []

        for name in _REQUIRED_FILES:
            if not (root / name).exists():
                blocking.append(f"required dataset artifact missing: {name}")

        manifest: dict[str, Any] = {}
        manifest_path = root / "manifest.json"
        if manifest_path.exists():
            try:
                loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    manifest = loaded
                else:
                    blocking.append("manifest.json is not an object")
            except json.JSONDecodeError:
                blocking.append("manifest.json is invalid JSON")

        behavior, behavior_errors = _load_jsonl(root / "mary_behavior_sft.jsonl")
        feedback, feedback_errors = _load_jsonl(
            root / "explicit_feedback" / "mary_sft.jsonl"
        )
        eval_rows, eval_errors = _load_jsonl(root / "mary_character_eval.jsonl")
        corpus, corpus_errors = _load_jsonl(root / "mary_character_corpus.jsonl")
        negative, negative_errors = _load_jsonl(root / "mary_negative_examples.jsonl")
        blocking.extend(
            [*behavior_errors, *feedback_errors, *eval_errors, *corpus_errors, *negative_errors]
        )

        training = [*behavior, *feedback]
        split_counts = {"train": 0, "validation": 0, "test": 0}
        signature_splits: dict[str, set[str]] = {}
        signature_counts: dict[str, int] = {}
        sources: dict[str, int] = {}
        boundary_violations = 0

        for row in training:
            split = str(row.get("split") or "train").casefold()
            if split not in split_counts:
                split = "train"
                warnings.append("training row with unknown split treated as train for audit")
            split_counts[split] += 1

            signature = _messages_signature(row)
            if signature:
                signature_counts[signature] = signature_counts.get(signature, 0) + 1
                signature_splits.setdefault(signature, set()).add(split)

            source = _normalize(row.get("source_name") or row.get("provenance") or "unknown")
            if source:
                sources[source] = sources.get(source, 0) + 1

            boundary = _normalize(row.get("boundary"))
            labels = {_normalize(item).upper() for item in list(row.get("labels") or [])}
            if boundary == "fictional_reference_not_lived_memory" or "FC" in labels:
                boundary_violations += 1
            if "NEG" in labels or boundary == "negative_example_only":
                boundary_violations += 1
            if row.get("training_eligible") is False:
                boundary_violations += 1

        duplicate_groups = sum(1 for count in signature_counts.values() if count > 1)
        split_leakage_groups = sum(
            1 for splits in signature_splits.values() if len(splits) > 1
        )

        eval_prompt_signatures = {
            _signature((row.get("prompt"),))
            for row in eval_rows
            if _signature((row.get("prompt"),))
        }
        train_prompt_signatures = {
            signature
            for row in training
            if (signature := _user_prompt_signature(row))
        }
        marybench_prompt_leaks = len(eval_prompt_signatures & train_prompt_signatures)

        # Corpus boundary sanity: FC/NEG material may exist as evidence, but
        # must not be marked training eligible.
        for row in [*corpus, *negative]:
            labels = {_normalize(item).upper() for item in list(row.get("labels") or [])}
            boundary = _normalize(row.get("boundary"))
            if ("FC" in labels or "NEG" in labels or boundary in {
                "fictional_reference_not_lived_memory",
                "negative_example_only",
            }) and bool(row.get("training_eligible")):
                boundary_violations += 1

        maximum_source_share = 0.0
        if training:
            maximum_source_share = max(sources.values(), default=0) / len(training)

        if len(training) < max(1, int(minimum_train_examples)):
            blocking.append(
                f"insufficient training examples: {len(training)} < {max(1, int(minimum_train_examples))}"
            )
        if split_leakage_groups:
            blocking.append(
                f"{split_leakage_groups} normalized example signature(s) cross train/validation/test boundaries"
            )
        if marybench_prompt_leaks:
            blocking.append(
                f"{marybench_prompt_leaks} held-out MaryBench prompt(s) appear in training inputs"
            )
        if boundary_violations:
            blocking.append(
                f"{boundary_violations} fiction/negative/training-eligibility boundary violation(s)"
            )
        if duplicate_groups:
            warnings.append(
                f"{duplicate_groups} duplicate normalized training example group(s) require curation"
            )
        if training and maximum_source_share > max(0.1, min(1.0, float(maximum_single_source_share))):
            warnings.append(
                f"single source dominates {maximum_source_share:.1%} of training rows"
            )
        if split_counts["validation"] == 0:
            warnings.append("validation split is empty")
        if split_counts["test"] == 0:
            warnings.append("test split is empty")

        fingerprint = str(manifest.get("fingerprint") or "")
        if not fingerprint:
            blocking.append("dataset manifest fingerprint is missing")

        report = MaryDatasetAuditReport(
            version=self.VERSION,
            dataset_fingerprint=fingerprint,
            training_rows=len(training),
            train_rows=split_counts["train"],
            validation_rows=split_counts["validation"],
            test_rows=split_counts["test"],
            duplicate_groups=duplicate_groups,
            split_leakage_groups=split_leakage_groups,
            marybench_prompt_leaks=marybench_prompt_leaks,
            boundary_violations=boundary_violations,
            source_dominance=round(maximum_source_share, 4),
            blocking_issues=tuple(dict.fromkeys(blocking)),
            warnings=tuple(dict.fromkeys(warnings)),
            training_ready=not blocking,
        )
        return report
