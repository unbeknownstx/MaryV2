"""Grounded experience journal for MaryV2 13.0.

This is not chain-of-thought storage.  It records observable turn outcomes and
provenance-safe learning signals so Mary's development can be based on things
that actually happened rather than on whatever a language model happened to
say about itself.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import uuid

from mary.governance.bounds import clip_text
from mary.runtime.persistence import atomic_write_json, load_json_recovering


class ExperienceJournal:
    SCHEMA_VERSION = 1

    def __init__(self, *, capacity: int = 2048, text_limit: int = 1200) -> None:
        self.capacity = max(128, min(8192, int(capacity)))
        self.text_limit = max(200, min(4000, int(text_limit)))
        self.records: list[dict[str, Any]] = []
        self.path: Path | None = None
        self.auto_save = False
        self.total_recorded = 0
        self.evicted = 0

    def configure(self, path: str | Path, *, auto_save: bool = True, load: bool = True) -> bool:
        self.path = Path(path)
        self.auto_save = bool(auto_save)
        return self.load() if load else True

    def add(self, record: dict[str, Any]) -> dict[str, Any]:
        item = dict(record or {})
        item.setdefault("id", f"experience_{uuid.uuid4().hex}")
        item.setdefault("timestamp", datetime.now().isoformat())
        for key in ("user_text", "mary_text", "summary", "reason"):
            if key in item:
                item[key] = clip_text(str(item.get(key) or ""), self.text_limit)
        self.records.append(item)
        self.total_recorded += 1
        if len(self.records) > self.capacity:
            overflow = len(self.records) - self.capacity
            self.records = self.records[overflow:]
            self.evicted += overflow
        if self.auto_save:
            self.save()
        return dict(item)

    def recent(self, limit: int = 12, *, meaningful_only: bool = False) -> list[dict[str, Any]]:
        items = self.records
        if meaningful_only:
            items = [item for item in items if float(item.get("importance", 0.0) or 0.0) >= 0.6]
        return [dict(item) for item in items[-max(0, min(100, int(limit))):]]

    def save(self) -> bool:
        if self.path is None:
            return True
        return atomic_write_json(self.path, self.to_dict(), backup_generations=3, indent=2)

    def load(self) -> bool:
        if self.path is None:
            return True
        payload, _ = load_json_recovering(self.path, backup_generations=3, restore_primary=False)
        if payload is None:
            return True
        if not isinstance(payload, dict):
            return False
        records = payload.get("records", [])
        self.records = [dict(x) for x in records if isinstance(x, dict)][-self.capacity:] if isinstance(records, list) else []
        stats = payload.get("stats", {})
        if isinstance(stats, dict):
            self.total_recorded = int(stats.get("total_recorded", len(self.records)) or len(self.records))
            self.evicted = int(stats.get("evicted", 0) or 0)
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "policy": {
                "stores_chain_of_thought": False,
                "model_dialogue_is_self_evidence": False,
                "observable_turn_outcomes_only": True,
            },
            "records": list(self.records[-self.capacity:]),
            "stats": {"total_recorded": self.total_recorded, "evicted": self.evicted},
        }

    def status(self) -> dict[str, Any]:
        meaningful = sum(1 for x in self.records if float(x.get("importance", 0.0) or 0.0) >= 0.6)
        return {
            "records": len(self.records),
            "meaningful_records": meaningful,
            "total_recorded": self.total_recorded,
            "evicted": self.evicted,
            "capacity": self.capacity,
            "configured": self.path is not None,
        }
