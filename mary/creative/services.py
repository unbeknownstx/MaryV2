"""Configuration-only registry for external creative services.

This registry describes *available paid/free creative capabilities* and their
price hints without storing API secrets or executing anything.  Actual adapters
remain explicit integrations.  It gives Mary/Studio enough information to say
"I can route this to X and the configured estimate is about $Y" before seeking
approval.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class CreativeServiceCapability:
    provider: str
    capability: str
    model: str = ""
    available: bool = True
    cost_per_unit_usd: float | None = None
    unit: str = "job"
    latency: str = "batch"
    quality: str = "standard"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CreativeServiceRegistry:
    VERSION = "1.0"
    MAX_ENTRIES = 128

    def __init__(self, entries: Iterable[CreativeServiceCapability] = (), *, errors: Iterable[str] = ()) -> None:
        self.entries = tuple(list(entries)[: self.MAX_ENTRIES])
        self.errors = tuple(str(item)[:500] for item in errors)

    @classmethod
    def empty(cls) -> "CreativeServiceRegistry":
        return cls(())

    @classmethod
    def from_environment(cls) -> "CreativeServiceRegistry":
        """Load a secret-free service catalog.

        ``MARY_CREATIVE_SERVICE_CATALOG`` may be either a JSON file path or an
        inline JSON array.  API keys are intentionally configured elsewhere.
        """
        raw = str(os.getenv("MARY_CREATIVE_SERVICE_CATALOG", "") or "").strip()
        if not raw:
            return cls.empty()
        try:
            path = Path(raw).expanduser()
            if path.exists() and path.is_file():
                payload = json.loads(path.read_text(encoding="utf-8"))
            else:
                payload = json.loads(raw)
            rows = payload.get("capabilities", []) if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                raise ValueError("creative service catalog must contain a list")
            entries = [cls._entry(row) for row in rows[: cls.MAX_ENTRIES] if isinstance(row, dict)]
            return cls(entries)
        except Exception as exc:
            return cls((), errors=[f"{type(exc).__name__}: {exc}"])

    @staticmethod
    def _entry(row: dict[str, Any]) -> CreativeServiceCapability:
        provider = str(row.get("provider") or "").strip().lower()[:80]
        capability = str(row.get("capability") or row.get("kind") or "").strip().lower()[:80]
        if not provider or not capability:
            raise ValueError("creative service entries require provider and capability")
        raw_cost = row.get("cost_per_unit_usd")
        cost = None if raw_cost in (None, "") else max(0.0, float(raw_cost))
        metadata = {}
        for key, value in list(dict(row.get("metadata", {}) or {}).items())[:16]:
            name = str(key)[:80]
            if any(marker in name.lower() for marker in ("key", "token", "secret", "password", "auth")):
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                metadata[name] = value if not isinstance(value, str) else value[:240]
        return CreativeServiceCapability(
            provider=provider,
            capability=capability,
            model=str(row.get("model") or "")[:160],
            available=bool(row.get("available", True)),
            cost_per_unit_usd=cost,
            unit=str(row.get("unit") or "job")[:40],
            latency=str(row.get("latency") or "batch")[:40],
            quality=str(row.get("quality") or "standard")[:40],
            metadata=metadata,
        )

    def candidates(self, capability: str) -> list[CreativeServiceCapability]:
        name = str(capability or "").strip().lower()
        return [item for item in self.entries if item.available and item.capability == name]

    def preview(self, capability: str, *, provider_preference: str = "") -> dict[str, Any]:
        candidates = self.candidates(capability)
        preference = str(provider_preference or "").strip().lower()
        if preference:
            candidates.sort(key=lambda x: (x.provider != preference, x.cost_per_unit_usd is None, x.cost_per_unit_usd or 0.0, x.provider))
        else:
            candidates.sort(key=lambda x: (x.cost_per_unit_usd is None, x.cost_per_unit_usd or 0.0, x.provider))
        selected = candidates[0] if candidates else None
        return {
            "capability": str(capability or "").strip().lower(),
            "available": selected is not None,
            "selected": selected.to_dict() if selected else None,
            "candidates": [item.to_dict() for item in candidates[:12]],
            "execution": "not_authorized",
            "policy": "service discovery/price hint only; adapter execution and spending require explicit authorization",
        }

    def quote_job(self, job: dict[str, Any]) -> dict[str, Any]:
        preview = self.preview(
            str(job.get("kind") or ""),
            provider_preference=str(job.get("provider_preference") or ""),
        )
        selected = preview.get("selected") or {}
        cost = selected.get("cost_per_unit_usd") if isinstance(selected, dict) else None
        quantity = 1.0
        if str(selected.get("unit") or "") in {"second", "seconds"}:
            quantity = max(1.0, float(job.get("duration_s") or 1.0))
        estimate = None if cost is None else round(float(cost) * quantity, 4)
        return {
            **preview,
            "estimated_cost_usd": estimate,
            "estimate_only": True,
            "budget_ceiling_usd": job.get("budget_ceiling_usd"),
            "within_budget_hint": (
                None if estimate is None or job.get("budget_ceiling_usd") is None
                else estimate <= float(job.get("budget_ceiling_usd"))
            ),
        }

    def snapshot(self) -> dict[str, Any]:
        providers = sorted({item.provider for item in self.entries})
        capabilities = sorted({item.capability for item in self.entries if item.available})
        return {
            "version": self.VERSION,
            "configured": bool(self.entries),
            "entries": len(self.entries),
            "providers": providers,
            "capabilities": capabilities,
            "errors": list(self.errors)[:16],
            "stores_credentials": False,
            "execution_authority": False,
        }
