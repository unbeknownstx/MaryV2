"""Mary Inbox: a bounded queue for non-interrupting notices."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import uuid
from typing import Any
from mary.runtime.persistence import atomic_write_json, load_json_recovering


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MaryInbox:
    def __init__(self, root: str | Path, *, limit: int = 200) -> None:
        self.root = Path(root); self.path = self.root / "inbox.json"; self.limit = max(20, int(limit)); self.notices: list[dict[str, Any]] = []
        payload, _ = load_json_recovering(self.path)
        if isinstance(payload, dict):
            self.notices = [dict(item) for item in payload.get("notices", []) if isinstance(item, dict)][-self.limit:]

    def save(self) -> bool:
        self.notices = self.notices[-self.limit:]
        return atomic_write_json(self.path, {"version": 1, "notices": self.notices})

    def add(self, title: str, body: str = "", *, category: str = "general", importance: float = 0.5, source: str = "mary") -> dict[str, Any]:
        notice = {
            "id": f"notice_{uuid.uuid4().hex[:10]}", "title": " ".join(str(title).split())[:180],
            "body": str(body or "").strip()[:1200], "category": str(category or "general")[:40],
            "importance": max(0.0, min(1.0, float(importance))), "source": str(source or "mary")[:40],
            "created_at": _now(), "read": False,
        }
        if not notice["title"]: raise ValueError("Notice title cannot be empty.")
        self.notices.append(notice); self.save(); return dict(notice)

    def mark_read(self, notice_id: str, read: bool = True) -> bool:
        for item in self.notices:
            if item.get("id") == notice_id:
                item["read"] = bool(read); self.save(); return True
        return False

    def list(self, *, unread_only: bool = False, limit: int = 50) -> list[dict[str, Any]]:
        values = [item for item in self.notices if not item.get("read")] if unread_only else list(self.notices)
        values = sorted(values, key=lambda item: (float(item.get("importance", 0)), str(item.get("created_at", ""))), reverse=True)
        return [dict(item) for item in values[: max(1, min(200, int(limit)))]]

    def summary(self) -> dict[str, Any]:
        return {"unread": sum(not item.get("read") for item in self.notices), "recent": self.list(limit=5)}
