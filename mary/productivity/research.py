"""Persistent bounded research notebooks for MaryV2."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import uuid
from typing import Any
from mary.runtime.persistence import atomic_write_json, load_json_recovering


def _now() -> str: return datetime.now(timezone.utc).isoformat()


class ResearchNotebook:
    def __init__(self, root: str | Path) -> None:
        self.path = Path(root) / "research.json"; self.threads: list[dict[str, Any]] = []
        payload, _ = load_json_recovering(self.path)
        if isinstance(payload, dict): self.threads = [dict(x) for x in payload.get("threads", []) if isinstance(x, dict)][-100:]
    def save(self): return atomic_write_json(self.path, {"version":1,"threads":self.threads[-100:]})
    def create(self, title: str, *, question: str = ""):
        title=" ".join(str(title).split())[:180]
        if not title: raise ValueError("Research title cannot be empty.")
        item={"id":f"research_{uuid.uuid4().hex[:10]}","title":title,"question":str(question)[:1000],"created_at":_now(),"updated_at":_now(),"notes":[],"status":"open"}
        self.threads.append(item); self.save(); return dict(item)
    def add_note(self, thread_id: str, text: str, *, source: str = "", url: str = ""):
        thread=next((x for x in self.threads if x.get("id")==thread_id),None)
        if thread is None: raise KeyError(thread_id)
        note={"id":f"note_{uuid.uuid4().hex[:10]}","text":str(text).strip()[:4000],"source":str(source)[:240],"url":str(url)[:1000],"created_at":_now()}
        if not note["text"]: raise ValueError("Research note cannot be empty.")
        thread.setdefault("notes",[]).append(note); thread["notes"]=thread["notes"][-250:]; thread["updated_at"]=_now(); self.save(); return dict(note)
    def list(self, limit: int = 50): return [dict(x) for x in sorted(self.threads,key=lambda x:str(x.get("updated_at","")),reverse=True)[:limit]]
    def summary(self): return {"open":sum(x.get("status")=="open" for x in self.threads),"recent":[{"id":x.get("id"),"title":x.get("title"),"notes":len(x.get("notes",[]))} for x in self.list(5)]}
