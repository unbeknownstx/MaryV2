"""Persistent pending thoughts: grounded observations Mary may bring up later."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid
from typing import Any
from mary.runtime.persistence import atomic_write_json, load_json_recovering

def _now(): return datetime.now(timezone.utc)

def _parse(value):
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception: return _now()

class PendingThoughtStore:
    def __init__(self, root: str | Path, limit: int = 100) -> None:
        self.path = Path(root) / "pending_thoughts.json"; self.limit=max(20,int(limit)); self.items=[]
        payload,_=load_json_recovering(self.path)
        if isinstance(payload,dict): self.items=[dict(x) for x in payload.get("thoughts",[]) if isinstance(x,dict)][-self.limit:]
    def _prune(self):
        now=_now(); self.items=[x for x in self.items if not x.get("expires_at") or _parse(x["expires_at"])>now][-self.limit:]
    def save(self): self._prune(); return atomic_write_json(self.path,{"version":1,"thoughts":self.items})
    def add(self,text:str,*,context:str="",importance:float=.5,ttl_hours:int=72,source:str="presence"):
        text=" ".join(str(text).split())[:800]
        if not text: raise ValueError("Pending thought cannot be empty.")
        now=_now(); item={"id":f"thought_{uuid.uuid4().hex[:10]}","text":text,"context":str(context)[:500],"importance":max(0,min(1,float(importance))),"source":str(source)[:40],"created_at":now.isoformat(),"expires_at":(now+timedelta(hours=max(1,min(720,int(ttl_hours))))).isoformat(),"used":False}
        self.items.append(item); self.save(); return dict(item)
    def active(self,limit:int=20): self._prune(); return [dict(x) for x in sorted([x for x in self.items if not x.get("used")],key=lambda x:(float(x.get("importance",0)),str(x.get("created_at",""))),reverse=True)[:limit]]
    def consume(self,item_id:str):
        for x in self.items:
            if x.get("id")==item_id: x["used"]=True; x["used_at"]=_now().isoformat(); self.save(); return True
        return False
