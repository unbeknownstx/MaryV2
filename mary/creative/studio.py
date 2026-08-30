"""Canonical non-identity production workspace for MaryV2.

The ProductionStudio stores creator-directed production projects beneath the
existing Ecosystem data root. It owns production artifacts only: plans, stages,
asset/take metadata, and capability-readiness projections. It never owns Mary
identity, relationship, memory, character, agency, or provider credentials.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from mary.runtime.persistence import atomic_write_json, load_json_recovering

from .production import CharacterAnchor, CreativeReference, ProductionPlan, ProductionStage, Shot, build_production_plan, capability_jobs


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text[:limit]


class ProductionStudio:
    """Persistent creative-production workspace attached to one MaryEcosystem."""

    VERSION = "2"
    _STAGES = {item.value for item in ProductionStage}

    def __init__(self, root: str | Path) -> None:
        self.path = Path(root) / "production.json"
        self.projects: list[dict[str, Any]] = []
        payload, _ = load_json_recovering(self.path)
        if isinstance(payload, dict):
            self.projects = [
                dict(item)
                for item in list(payload.get("projects", []) or [])
                if isinstance(item, dict)
            ][-100:]

    def save(self) -> bool:
        return bool(atomic_write_json(
            self.path,
            {
                "version": self.VERSION,
                "authority": "canonical_workspace_artifact",
                "identity_owner": False,
                "projects": self.projects[-100:],
            },
        ))

    def create(
        self,
        *,
        title: str,
        objective: str,
        shots: Iterable[dict[str, Any] | Shot],
        characters: Iterable[dict[str, Any] | CharacterAnchor] = (),
        format: str = "short_video",
        aspect_ratio: str = "9:16",
        target_seconds: int = 30,
        deliverables: Iterable[str] = ("master_video", "thumbnail", "caption"),
        provider_preferences: dict[str, str] | None = None,
        references: Iterable[dict[str, Any] | CreativeReference] = (),
        creative_intent: Iterable[str] = (),
        style_constraints: Iterable[str] = (),
        budget_ceiling_usd: float | None = None,
        source: str = "creator_directed",
    ) -> dict[str, Any]:
        shot_items = tuple(self._shot(item, index) for index, item in enumerate(shots, start=1))
        character_items = tuple(self._character(item) for item in characters)
        reference_items = tuple(self._reference(item) for item in references)
        plan = build_production_plan(
            title=title,
            objective=objective,
            shots=shot_items,
            characters=character_items,
            format=format,
            aspect_ratio=aspect_ratio,
            target_seconds=target_seconds,
            deliverables=deliverables,
            provider_preferences=provider_preferences,
            references=reference_items,
            creative_intent=creative_intent,
            style_constraints=style_constraints,
            budget_ceiling_usd=budget_ceiling_usd,
        )
        item = plan.to_dict()
        item.update({
            "created_at": _now(),
            "updated_at": _now(),
            "source": _clip(source, 80) or "creator_directed",
            "assets": [],
            "reviews": [],
            "fingerprint": plan.fingerprint,
        })
        self.projects.append(item)
        self.projects = self.projects[-100:]
        self.save()
        return dict(item)

    def get(self, production_id: str) -> dict[str, Any]:
        item = next((x for x in self.projects if x.get("production_id") == production_id), None)
        if item is None:
            raise KeyError(production_id)
        return dict(item)

    def list(self, limit: int = 30) -> list[dict[str, Any]]:
        ordered = sorted(self.projects, key=lambda x: str(x.get("updated_at", "")), reverse=True)
        return [dict(item) for item in ordered[: max(1, min(100, int(limit)))]]

    def set_stage(self, production_id: str, stage: str) -> dict[str, Any]:
        normalized = str(stage or "").strip().lower()
        if normalized not in self._STAGES:
            raise ValueError("Unsupported production stage: " + normalized)
        item = self._mutable(production_id)
        item["stage"] = normalized
        item["updated_at"] = _now()
        self.save()
        return dict(item)

    def add_asset(
        self,
        production_id: str,
        *,
        kind: str,
        uri: str = "",
        shot_id: str = "",
        provider: str = "",
        model: str = "",
        status: str = "candidate",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        item = self._mutable(production_id)
        assets = list(item.get("assets", []) or [])[-249:]
        asset = {
            "id": f"asset_{len(assets) + 1:04d}",
            "kind": _clip(kind, 80),
            "uri": str(uri or "")[:2000],
            "shot_id": _clip(shot_id, 120),
            "provider": _clip(provider, 120),
            "model": _clip(model, 160),
            "status": _clip(status, 40) or "candidate",
            "metadata": self._safe_metadata(metadata),
            "created_at": _now(),
        }
        if not asset["kind"]:
            raise ValueError("production asset kind is required")
        assets.append(asset)
        item["assets"] = assets
        item["updated_at"] = _now()
        self.save()
        return dict(asset)

    def review(
        self,
        production_id: str,
        *,
        rating: str,
        note: str = "",
        asset_id: str = "",
    ) -> dict[str, Any]:
        normalized = str(rating or "").strip().lower()
        if normalized not in {"positive", "negative", "neutral"}:
            raise ValueError("production review rating must be positive, negative, or neutral")
        item = self._mutable(production_id)
        reviews = list(item.get("reviews", []) or [])[-249:]
        review = {
            "id": f"review_{len(reviews) + 1:04d}",
            "rating": normalized,
            "note": str(note or "")[:1200],
            "asset_id": _clip(asset_id, 120),
            "created_at": _now(),
        }
        reviews.append(review)
        item["reviews"] = reviews
        item["updated_at"] = _now()
        self.save()
        return dict(review)

    def jobs(
        self,
        production_id: str,
        *,
        node_registry: Any = None,
        service_registry: Any = None,
    ) -> dict[str, Any]:
        plan = self._plan_from_dict(self.get(production_id))
        jobs = capability_jobs(plan)
        enriched: list[dict[str, Any]] = []
        for job in jobs:
            row = dict(job)
            route: dict[str, Any] = {}
            if node_registry is not None:
                preview = getattr(node_registry, "route_preview", None)
                if callable(preview):
                    try:
                        route = dict(preview(str(job.get("kind") or "")) or {})
                    except Exception:
                        route = {}
            service_quote: dict[str, Any] = {}
            if service_registry is not None:
                quote = getattr(service_registry, "quote_job", None)
                if callable(quote):
                    try:
                        service_quote = dict(quote(row) or {})
                    except Exception:
                        service_quote = {}
            row["route"] = {
                "node": route,
                "service": service_quote,
                "selected_surface": (
                    "node" if bool(route.get("available"))
                    else "service" if bool(service_quote.get("available"))
                    else None
                ),
            }
            row["available"] = bool(route.get("available") or service_quote.get("available"))
            row["estimated_cost_usd"] = service_quote.get("estimated_cost_usd")
            enriched.append(row)
        return {
            "production_id": production_id,
            "jobs": enriched,
            "ready": bool(enriched) and all(bool(row.get("available")) for row in enriched),
            "policy": "planning/readiness only; execution still requires capability permission and approval",
        }

    def snapshot(self) -> dict[str, Any]:
        recent = self.list(8)
        return {
            "version": self.VERSION,
            "projects": len(self.projects),
            "active": sum(str(item.get("stage")) != ProductionStage.PUBLISH.value for item in self.projects),
            "recent": [
                {
                    "production_id": item.get("production_id"),
                    "title": item.get("title"),
                    "stage": item.get("stage"),
                    "format": item.get("format"),
                    "shots": len(item.get("shots", []) or []),
                    "assets": len(item.get("assets", []) or []),
                    "updated_at": item.get("updated_at"),
                }
                for item in recent
            ],
            "semantics": {
                "authority": "canonical_workspace_artifact",
                "identity_owner": False,
                "execution_authority": False,
                "silent_publish": False,
            },
        }

    def _mutable(self, production_id: str) -> dict[str, Any]:
        item = next((x for x in self.projects if x.get("production_id") == production_id), None)
        if item is None:
            raise KeyError(production_id)
        return item

    @staticmethod
    def _shot(item: dict[str, Any] | Shot, index: int) -> Shot:
        if isinstance(item, Shot):
            return item
        if not isinstance(item, dict):
            raise ValueError("shots must contain objects")
        return Shot(
            shot_id=_clip(item.get("shot_id") or f"shot_{index:03d}", 120),
            duration_s=max(0.1, min(float(item.get("duration_s", 3.0) or 3.0), 120.0)),
            framing=_clip(item.get("framing") or "medium", 120),
            action=str(item.get("action") or "")[:2000],
            dialogue=str(item.get("dialogue") or "")[:4000],
            environment=str(item.get("environment") or "")[:1200],
            camera=str(item.get("camera") or "")[:800],
            expression=_clip(item.get("expression") or "neutral", 120),
            gesture=_clip(item.get("gesture") or "natural", 120),
            audio_notes=str(item.get("audio_notes") or "")[:800],
            continuity=tuple(str(x)[:240] for x in list(item.get("continuity", []) or [])[:32]),
            source_refs=tuple(str(x)[:1000] for x in list(item.get("source_refs", []) or [])[:32]),
        )

    @staticmethod
    def _character(item: dict[str, Any] | CharacterAnchor) -> CharacterAnchor:
        if isinstance(item, CharacterAnchor):
            return item
        if not isinstance(item, dict):
            raise ValueError("characters must contain objects")
        return CharacterAnchor(
            character_id=_clip(item.get("character_id") or item.get("display_name") or "character", 120),
            display_name=_clip(item.get("display_name") or item.get("character_id") or "Character", 160),
            visual_traits=tuple(str(x)[:240] for x in list(item.get("visual_traits", []) or [])[:32]),
            wardrobe=tuple(str(x)[:240] for x in list(item.get("wardrobe", []) or [])[:24]),
            voice_profile=_clip(item.get("voice_profile"), 240),
            behavior_notes=tuple(str(x)[:300] for x in list(item.get("behavior_notes", []) or [])[:32]),
            reference_assets=tuple(str(x)[:1000] for x in list(item.get("reference_assets", []) or [])[:32]),
            provenance=_clip(item.get("provenance") or "creator_authored", 80),
        )

    @staticmethod
    def _reference(item: dict[str, Any] | CreativeReference) -> CreativeReference:
        if isinstance(item, CreativeReference):
            return item
        if not isinstance(item, dict):
            raise ValueError("references must contain objects")
        uri = str(item.get("uri") or item.get("path") or "")[:2000]
        kind = _clip(item.get("kind") or "reference", 80)
        if not uri:
            raise ValueError("creative reference uri is required")
        return CreativeReference(
            uri=uri,
            kind=kind or "reference",
            role=_clip(item.get("role") or "reference", 80),
            provenance=_clip(item.get("provenance") or "creator_authored", 80),
            notes=str(item.get("notes") or "")[:1000],
        )

    @staticmethod
    def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(metadata, dict):
            return {}
        safe: dict[str, Any] = {}
        for key, value in list(metadata.items())[:24]:
            name = _clip(key, 80)
            if not name:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe[name] = value if not isinstance(value, str) else value[:1000]
        return safe

    @classmethod
    def _plan_from_dict(cls, item: dict[str, Any]) -> ProductionPlan:
        return ProductionPlan(
            production_id=str(item.get("production_id") or ""),
            title=str(item.get("title") or ""),
            objective=str(item.get("objective") or ""),
            format=str(item.get("format") or "short_video"),
            aspect_ratio=str(item.get("aspect_ratio") or "9:16"),
            target_seconds=int(item.get("target_seconds", 30) or 30),
            stage=str(item.get("stage") or ProductionStage.STORYBOARD.value),
            characters=tuple(cls._character(x) for x in list(item.get("characters", []) or [])),
            shots=tuple(cls._shot(x, index) for index, x in enumerate(list(item.get("shots", []) or []), start=1)),
            deliverables=tuple(str(x)[:80] for x in list(item.get("deliverables", []) or [])),
            provider_preferences={str(k)[:80]: str(v)[:160] for k, v in dict(item.get("provider_preferences", {}) or {}).items()},
            approval_gates=tuple(str(x)[:80] for x in list(item.get("approval_gates", []) or [])),
            provenance=str(item.get("provenance") or "creator_directed"),
            version=str(item.get("version") or "1"),
            references=tuple(cls._reference(x) for x in list(item.get("references", []) or [])),
            creative_intent=tuple(str(x)[:500] for x in list(item.get("creative_intent", []) or [])[:32]),
            style_constraints=tuple(str(x)[:500] for x in list(item.get("style_constraints", []) or [])[:32]),
            budget_ceiling_usd=(
                None if item.get("budget_ceiling_usd") is None
                else max(0.0, float(item.get("budget_ceiling_usd")))
            ),
        )
