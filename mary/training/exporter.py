"""Consent-driven Mary dataset exporter.

Exports only explicitly rated/corrected records from ResponseFeedbackStore.
It performs no training and never reads ordinary dialogue history by itself.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Any

from .feedback import ResponseFeedback, ResponseFeedbackStore


@dataclass(frozen=True)
class DatasetExportSummary:
    source_records: int
    sft: int
    preferences: int
    rejected: int
    eval: int
    output_dir: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MaryTrainingDatasetExporter:
    VERSION = "1"

    def preview(self, store: ResponseFeedbackStore) -> dict[str, Any]:
        """Return export eligibility counts without writing files or training."""
        records = store.records()
        positive = sum(item.rating == "positive" for item in records)
        corrections = sum(bool(item.chosen_text) for item in records)
        negative = sum(item.rating == "negative" for item in records)
        return {
            "source_records": len(records),
            "sft_candidates": positive + corrections,
            "preference_candidates": corrections,
            "rejected_candidates": negative,
            "eval_candidates": len(records),
            "writes_files": False,
            "trains_model": False,
            "policy": "explicit creator feedback only; preview is read-only",
        }

    def export(self, store: ResponseFeedbackStore, output_dir: str | Path) -> DatasetExportSummary:
        target = Path(output_dir).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        sft: list[dict[str, Any]] = []
        preferences: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        evaluation: list[dict[str, Any]] = []

        records = store.records()
        for record in records:
            prompt = self._prompt(record)
            common = {
                "feedback_id": record.id,
                "source_kind": record.source_kind,
                "input_authority": record.input_authority,
                "conversation_mode": record.conversation_mode,
                "performance_context": record.performance_context,
                "character_patterns": list(record.character_patterns),
                "tags": list(record.tags),
            }
            if record.rating == "positive":
                sft.append({
                    **common,
                    "messages": self._messages(record, answer=record.assistant_text),
                })
            if record.chosen_text:
                # A creator correction is stronger training evidence than the
                # original rating. It can seed both SFT and preference data.
                sft.append({
                    **common,
                    "messages": self._messages(record, answer=record.chosen_text),
                    "source": "creator_correction",
                })
                preferences.append({
                    **common,
                    "prompt": prompt,
                    "chosen": record.chosen_text,
                    "rejected": record.assistant_text,
                })
            if record.rating == "negative":
                rejected.append({
                    **common,
                    "prompt": prompt,
                    "response": record.assistant_text,
                    "note": record.note,
                })
            evaluation.append({
                **common,
                "prompt": prompt,
                "response": record.assistant_text,
                "rating": record.rating,
                "chosen": record.chosen_text or None,
                "note": record.note,
            })

        self._jsonl(target / "mary_sft.jsonl", sft)
        self._jsonl(target / "mary_preferences.jsonl", preferences)
        self._jsonl(target / "mary_rejected.jsonl", rejected)
        self._jsonl(target / "mary_eval.jsonl", evaluation)
        summary = DatasetExportSummary(
            source_records=len(records),
            sft=len(sft),
            preferences=len(preferences),
            rejected=len(rejected),
            eval=len(evaluation),
            output_dir=str(target),
        )
        manifest = {
            "version": self.VERSION,
            "summary": summary.to_dict(),
            "policy": {
                "explicit_feedback_only": True,
                "ordinary_conversation_harvested": False,
                "fictional_novel_events_are_lived_memory": False,
                "feedback_is_character_authority": False,
                "training_performed": False,
            },
        }
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return summary

    @staticmethod
    def _prompt(record: ResponseFeedback) -> str:
        if record.source_kind == "mary_initiative":
            return f"[MARY INITIATIVE CONTEXT — {record.input_authority}]\n{record.context_text}".strip()
        return record.user_text

    def _messages(self, record: ResponseFeedback, *, answer: str) -> list[dict[str, str]]:
        if record.source_kind == "mary_initiative":
            return [
                {"role": "system", "content": "Mary initiative context; not creator-authored speech."},
                {"role": "user", "content": self._prompt(record)},
                {"role": "assistant", "content": answer},
            ]
        return [
            {"role": "user", "content": record.user_text},
            {"role": "assistant", "content": answer},
        ]

    @staticmethod
    def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        path.write_text(text, encoding="utf-8")
