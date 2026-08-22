"""Persistent study projects with simple spaced repetition."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid
from typing import Any
from mary.runtime.persistence import atomic_write_json, load_json_recovering


def _now(): return datetime.now(timezone.utc)

def _parse(value: Any):
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception: return _now()


class StudyManager:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root); self.path = self.root / "study.json"; self.projects: list[dict[str, Any]] = []
        payload, _ = load_json_recovering(self.path)
        if isinstance(payload, dict): self.projects = [dict(item) for item in payload.get("projects", []) if isinstance(item, dict)][-50:]

    def save(self) -> bool: return atomic_write_json(self.path, {"version": 1, "projects": self.projects[-50:]})

    def create_project(self, title: str, *, objective: str = "") -> dict[str, Any]:
        title = " ".join(str(title).split())[:160]
        if not title: raise ValueError("Study project title cannot be empty.")
        project = {"id": f"study_{uuid.uuid4().hex[:10]}", "title": title, "objective": str(objective or "")[:800],
                   "created_at": _now().isoformat(), "cards": [], "sessions": []}
        self.projects.append(project); self.save(); return dict(project)

    def _project(self, project_id: str) -> dict[str, Any]:
        project = next((item for item in self.projects if item.get("id") == project_id), None)
        if project is None: raise KeyError(project_id)
        return project

    def add_card(self, project_id: str, prompt: str, answer: str, *, tags: list[str] | None = None) -> dict[str, Any]:
        project = self._project(project_id); now = _now()
        card = {"id": f"card_{uuid.uuid4().hex[:10]}", "prompt": str(prompt).strip()[:1200], "answer": str(answer).strip()[:2400],
                "tags": [str(tag)[:40] for tag in (tags or [])[:10]], "interval_days": 0, "ease": 2.3, "repetitions": 0,
                "due_at": now.isoformat(), "last_score": None}
        if not card["prompt"] or not card["answer"]: raise ValueError("Study card prompt and answer are required.")
        project.setdefault("cards", []).append(card); self.save(); return dict(card)

    def review(self, project_id: str, card_id: str, score: int) -> dict[str, Any]:
        project = self._project(project_id); card = next((item for item in project.get("cards", []) if item.get("id") == card_id), None)
        if card is None: raise KeyError(card_id)
        score = max(0, min(5, int(score))); reps = int(card.get("repetitions", 0)); interval = int(card.get("interval_days", 0)); ease = float(card.get("ease", 2.3))
        if score < 3: reps = 0; interval = 1
        else:
            reps += 1
            interval = 1 if reps == 1 else 3 if reps == 2 else max(4, round(max(1, interval) * ease))
        ease = max(1.3, min(3.0, ease + (0.1 - (5-score)*(0.08 + (5-score)*0.02))))
        card.update({"repetitions": reps, "interval_days": interval, "ease": round(ease, 3), "last_score": score,
                     "due_at": (_now() + timedelta(days=interval)).isoformat(), "reviewed_at": _now().isoformat()})
        self.save(); return dict(card)

    def due_cards(self, project_id: str | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
        now = _now(); values = []
        projects = [self._project(project_id)] if project_id else self.projects
        for project in projects:
            for card in project.get("cards", []):
                if _parse(card.get("due_at")) <= now:
                    values.append({**card, "project_id": project.get("id"), "project_title": project.get("title")})
        return sorted(values, key=lambda item: str(item.get("due_at", "")))[:limit]

    def summary(self) -> dict[str, Any]:
        return {"projects": len(self.projects), "due": len(self.due_cards(limit=500)),
                "project_list": [{"id": p.get("id"), "title": p.get("title"), "cards": len(p.get("cards", [])),
                                  "due": len(self.due_cards(p.get("id"), limit=500))} for p in self.projects[:20]]}
