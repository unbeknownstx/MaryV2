"""Mary Dataset v1 exporter.

Builds a portable, provenance-bearing dataset bundle from data Mary already
owns/accepts. It intentionally separates:
- creator-authored character corpus/reference evidence,
- structured behavior SFT seeds derived only from authored Situation/Behavior records,
- explicit creator-rated/corrected dialogue feedback,
- negative character examples,
- MaryBench acceptance/evaluation cases.

Ordinary conversation history, memories, relationship state, growth state,
provider traces and private durable profile data are never harvested implicitly.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from mary.character import CharacterSourcebook, MaryEvaluationSet
from mary.training.exporter import MaryTrainingDatasetExporter
from mary.training.feedback import ResponseFeedbackStore


_DATASET_VERSION = "mary-dataset-v1"
_SITUATION_RE = re.compile(
    r"Situation:\s*(?P<situation>.+?)\s+Mary behavior:\s*(?P<behavior>.+?)(?:\s+Performance tells:|\s+Avoid:|\s+Source/provenance:|$)",
    re.IGNORECASE,
)
_AVOID_RE = re.compile(r"\s+Avoid:\s*(?P<avoid>.+?)(?:\s+Source/provenance:|\s+Strength:|$)", re.IGNORECASE)


@dataclass(frozen=True)
class MaryDatasetV1Summary:
    version: str
    sourcebook_records: int
    character_training_candidates: int
    behavior_sft: int
    negative_examples: int
    marybench_eval: int
    feedback_records: int
    feedback_sft: int
    feedback_preferences: int
    feedback_rejected: int
    feedback_eval: int
    fingerprint: str
    output_dir: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _stable_split(identifier: str) -> str:
    bucket = int(sha256(identifier.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 85:
        return "train"
    if bucket < 93:
        return "validation"
    return "test"


def _record_boundary(record: Any) -> str:
    labels = set(str(item).upper() for item in getattr(record, "labels", ()) or ())
    if "NEG" in labels:
        return "negative_example_only"
    if "FC" in labels:
        return "fictional_reference_not_lived_memory"
    if "ALT" in labels:
        return "alternate_reference_not_default_character"
    if labels.intersection({"AI", "DNA", "PUB"}):
        return "character_training_candidate"
    return "reference_only"


def _character_row(record: Any, sourcebook_hash: str) -> dict[str, Any]:
    labels = [str(item).upper() for item in getattr(record, "labels", ()) or ()]
    boundary = _record_boundary(record)
    return {
        "dataset_version": _DATASET_VERSION,
        "record_id": str(record.record_id),
        "text": str(record.text),
        "heading": str(record.heading or ""),
        "labels": labels,
        "source_name": str(record.source_name),
        "source_kind": str(record.source_kind),
        "provenance": str(record.provenance or "creator_authored"),
        "content_hash": str(record.content_hash),
        "sourcebook_hash": sourcebook_hash,
        "boundary": boundary,
        "training_eligible": boundary == "character_training_candidate",
        "split": _stable_split(str(record.record_id)),
    }


def _behavior_sft_row(record: Any) -> dict[str, Any] | None:
    """Convert only explicitly structured authored Situation/Behavior evidence.

    This deliberately does not invent prompts from arbitrary prose.
    """

    text = str(record.text or "")
    matched = _SITUATION_RE.search(text)
    if not matched:
        return None
    situation = " ".join(matched.group("situation").split())
    behavior = " ".join(matched.group("behavior").split())
    if not situation or not behavior:
        return None
    avoid_match = _AVOID_RE.search(text)
    avoid = " ".join(avoid_match.group("avoid").split()) if avoid_match else ""
    labels = [str(item).upper() for item in getattr(record, "labels", ()) or ()]
    if "NEG" in labels or "FC" in labels or "ALT" in labels:
        return None
    return {
        "dataset_version": _DATASET_VERSION,
        "example_id": f"behavior_{record.record_id}",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Respond as Mary: natural, direct, character-consistent, and grounded. "
                    "Do not invent memories or creator facts."
                ),
            },
            {"role": "user", "content": situation},
            {"role": "assistant", "content": behavior},
        ],
        "avoid": avoid or None,
        "labels": labels,
        "source_name": str(record.source_name),
        "source_kind": str(record.source_kind),
        "provenance": "creator_authored_structured_behavior",
        "split": _stable_split(f"behavior_{record.record_id}"),
    }


def _marybench_row(case: Any) -> dict[str, Any]:
    return {
        "dataset_version": _DATASET_VERSION,
        "case_id": str(case.case_id),
        "prompt": str(case.prompt),
        "category": str(case.category),
        "description": str(case.description or ""),
        "required_phrases": list(case.required_phrases),
        "forbidden_phrases": list(case.forbidden_phrases),
        "forbidden_patterns": list(case.forbidden_patterns),
        "expected_labels": list(case.expected_labels),
        "notes": str(case.notes or ""),
        "source": str(case.source or "creator_authored"),
        "metadata": dict(case.metadata or {}),
        "training_eligible": False,
        "purpose": "held_out_character_evaluation",
    }


class MaryDatasetV1Exporter:
    """Create Mary Dataset v1 without harvesting implicit private state."""

    VERSION = _DATASET_VERSION

    def export(
        self,
        *,
        root: str | Path,
        output_dir: str | Path,
        feedback_path: str | Path | None = None,
    ) -> MaryDatasetV1Summary:
        base = Path(root).expanduser().resolve()
        target = Path(output_dir).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)

        sourcebook = CharacterSourcebook.from_environment(root=base)
        evaluation = MaryEvaluationSet.from_environment(root=base)

        character_rows = [
            _character_row(record, sourcebook.sourcebook_hash)
            for record in sourcebook.records
        ]
        training_candidates = [
            row for row in character_rows if bool(row["training_eligible"])
        ]
        negative_rows = [
            row for row in character_rows
            if row["boundary"] == "negative_example_only"
        ]
        behavior_rows = [
            row
            for record in sourcebook.records
            if (row := _behavior_sft_row(record)) is not None
        ]
        eval_rows = [_marybench_row(case) for case in evaluation.cases]

        _jsonl(target / "mary_character_corpus.jsonl", character_rows)
        _jsonl(target / "mary_character_training_candidates.jsonl", training_candidates)
        _jsonl(target / "mary_behavior_sft.jsonl", behavior_rows)
        _jsonl(target / "mary_negative_examples.jsonl", negative_rows)
        _jsonl(target / "mary_character_eval.jsonl", eval_rows)

        feedback_summary = {
            "source_records": 0,
            "sft": 0,
            "preferences": 0,
            "rejected": 0,
            "eval": 0,
        }
        feedback_source = Path(feedback_path).expanduser().resolve() if feedback_path else None
        feedback_dir = target / "explicit_feedback"
        if feedback_source is not None and feedback_source.exists():
            store = ResponseFeedbackStore(feedback_source)
            exported = MaryTrainingDatasetExporter().export(store, feedback_dir)
            feedback_summary = {
                "source_records": exported.source_records,
                "sft": exported.sft,
                "preferences": exported.preferences,
                "rejected": exported.rejected,
                "eval": exported.eval,
            }
        else:
            feedback_dir.mkdir(parents=True, exist_ok=True)
            for name in (
                "mary_sft.jsonl",
                "mary_preferences.jsonl",
                "mary_rejected.jsonl",
                "mary_eval.jsonl",
            ):
                (feedback_dir / name).write_text("", encoding="utf-8")

        fingerprint_payload = {
            "version": self.VERSION,
            "sourcebook_hash": sourcebook.sourcebook_hash,
            "sourcebook_records": len(character_rows),
            "character_training_candidates": len(training_candidates),
            "behavior_sft": len(behavior_rows),
            "negative_examples": len(negative_rows),
            "marybench_fingerprint": evaluation.fingerprint,
            "marybench_eval": len(eval_rows),
            "feedback": feedback_summary,
        }
        fingerprint = sha256(
            json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:24]

        summary = MaryDatasetV1Summary(
            version=self.VERSION,
            sourcebook_records=len(character_rows),
            character_training_candidates=len(training_candidates),
            behavior_sft=len(behavior_rows),
            negative_examples=len(negative_rows),
            marybench_eval=len(eval_rows),
            feedback_records=int(feedback_summary["source_records"]),
            feedback_sft=int(feedback_summary["sft"]),
            feedback_preferences=int(feedback_summary["preferences"]),
            feedback_rejected=int(feedback_summary["rejected"]),
            feedback_eval=int(feedback_summary["eval"]),
            fingerprint=fingerprint,
            output_dir=str(target),
        )

        manifest = {
            "version": self.VERSION,
            "fingerprint": fingerprint,
            "summary": summary.to_dict(),
            "sources": {
                "sourcebook": {
                    "version": sourcebook.VERSION,
                    "hash": sourcebook.sourcebook_hash,
                    "records": len(sourcebook.records),
                    "source_names": sorted({record.source_name for record in sourcebook.records}),
                    "load_errors": list(sourcebook.load_errors),
                },
                "marybench": {
                    "version": evaluation.VERSION,
                    "fingerprint": evaluation.fingerprint,
                    "cases": len(evaluation.cases),
                    "load_errors": list(evaluation.load_errors),
                },
                "explicit_feedback": {
                    "path_included": bool(feedback_source and feedback_source.exists()),
                    **feedback_summary,
                },
            },
            "files": {
                "character_corpus": "mary_character_corpus.jsonl",
                "character_training_candidates": "mary_character_training_candidates.jsonl",
                "behavior_sft": "mary_behavior_sft.jsonl",
                "negative_examples": "mary_negative_examples.jsonl",
                "character_eval": "mary_character_eval.jsonl",
                "feedback_sft": "explicit_feedback/mary_sft.jsonl",
                "feedback_preferences": "explicit_feedback/mary_preferences.jsonl",
                "feedback_rejected": "explicit_feedback/mary_rejected.jsonl",
                "feedback_eval": "explicit_feedback/mary_eval.jsonl",
            },
            "boundaries": {
                "ordinary_conversation_harvested": False,
                "memory_exported": False,
                "relationship_state_exported": False,
                "growth_state_exported": False,
                "creator_profile_exported": False,
                "provider_traces_exported": False,
                "fictional_canon_is_lived_memory": False,
                "negative_examples_are_sft_targets": False,
                "marybench_used_for_training_by_default": False,
                "third_party_dataset_included": False,
                "training_performed": False,
            },
            "recommended_uses": {
                "character_corpus": "RAG, curation, synthetic-example generation with review",
                "character_training_candidates": "manual curation before LoRA/SFT",
                "behavior_sft": "direct SFT/QLoRA seed examples",
                "negative_examples": "rejection/rubric/preference construction",
                "character_eval": "held-out MaryBench regression evaluation",
                "feedback_sft": "creator-approved supervised fine-tuning",
                "feedback_preferences": "DPO/ORPO-style preference tuning",
            },
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return summary
