"""Durable competence evidence for MaryV2.

The competence ledger answers a narrow operational question: what capabilities,
skills and replaceable workers have actually succeeded for Mary, how often, and
with what verified evidence?

It is not identity, personality, memory truth, world truth, permission, or a
router.  It persists structural performance evidence so Mary can reason about
her own practical limits across restarts without confusing "advertised" with
"demonstrated".
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import math
from typing import Any, Iterable
from uuid import uuid4

from .storage import AtomicJsonStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _tuple(values: Iterable[Any], *, limit: int = 32, item_limit: int = 180) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            item
            for raw in list(values)[:limit]
            if (item := _text(raw, item_limit))
        )
    )


@dataclass(frozen=True)
class CompetenceRecord:
    id: str
    capability: str
    operation: str
    node_id: str
    skill_id: str
    attempts: int
    successes: int
    failures: int
    verified_successes: int
    latency_samples: int
    mean_latency_ms: float | None
    reliability: float
    evidence_strength: float
    evidence_ids: tuple[str, ...]
    first_observed_at: str
    last_observed_at: str
    last_result: str
    last_success: bool | None
    implementation_fingerprint: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_ids"] = list(self.evidence_ids)
        return payload


class CompetenceLedger:
    """Persistent structural performance evidence, never execution authority."""

    VERSION = 2

    def __init__(self, path: Path, *, capacity: int = 2000) -> None:
        self.capacity = max(64, int(capacity))
        self._store = AtomicJsonStore(
            path,
            default={"version": self.VERSION, "records": []},
        )

    @staticmethod
    def _key(
        capability: str,
        operation: str,
        node_id: str,
        skill_id: str,
        implementation_fingerprint: str = "",
    ) -> tuple[str, str, str, str, str]:
        return (
            _text(capability, 160).casefold(),
            _text(operation, 80).casefold() or "general",
            _text(node_id, 180),
            _text(skill_id, 180),
            _text(implementation_fingerprint, 64).casefold(),
        )

    @staticmethod
    def _posterior(successes: int, failures: int) -> tuple[float, float]:
        """Beta(1,1) posterior mean plus bounded evidence strength.

        The reliability estimate intentionally remains conservative when only a
        few observations exist. Evidence strength approaches 1 gradually and is
        separate from reliability so callers can see the difference between
        "1/1 worked" and "40/42 worked".
        """

        successes = max(0, int(successes))
        failures = max(0, int(failures))
        attempts = successes + failures
        reliability = (successes + 1.0) / (attempts + 2.0)
        evidence_strength = 1.0 - math.exp(-attempts / 8.0)
        return round(reliability, 4), round(max(0.0, min(1.0, evidence_strength)), 4)

    def record(
        self,
        *,
        capability: str,
        operation: str = "general",
        node_id: str = "",
        skill_id: str = "",
        success: bool,
        verified: bool = False,
        latency_ms: float | None = None,
        evidence_ids: Iterable[str] = (),
        result: str = "",
        observed_at: str | None = None,
        implementation_fingerprint: str = "",
    ) -> CompetenceRecord:
        capability, operation, node_id, skill_id, implementation_fingerprint = self._key(
            capability,
            operation,
            node_id,
            skill_id,
            implementation_fingerprint,
        )
        if not capability:
            raise ValueError("competence evidence requires capability")
        when = observed_at or _now()
        new_evidence = _tuple(evidence_ids, limit=48)
        record_id = ""

        def mutate(data: dict[str, Any]) -> None:
            nonlocal record_id
            rows = list(data.get("records") or [])
            row = next(
                (
                    item for item in rows
                    if self._key(
                        str(item.get("capability") or ""),
                        str(item.get("operation") or "general"),
                        str(item.get("node_id") or ""),
                        str(item.get("skill_id") or ""),
                        str(item.get("implementation_fingerprint") or ""),
                    ) == (
                        capability,
                        operation,
                        node_id,
                        skill_id,
                        implementation_fingerprint,
                    )
                ),
                None,
            )
            if row is None:
                record_id = f"competence_{uuid4().hex}"
                row = {
                    "id": record_id,
                    "capability": capability,
                    "operation": operation,
                    "node_id": node_id,
                    "skill_id": skill_id,
                    "attempts": 0,
                    "successes": 0,
                    "failures": 0,
                    "verified_successes": 0,
                    "latency_samples": 0,
                    "mean_latency_ms": None,
                    "reliability": 0.5,
                    "evidence_strength": 0.0,
                    "evidence_ids": [],
                    "first_observed_at": when,
                    "last_observed_at": when,
                    "last_result": "",
                    "last_success": None,
                    "implementation_fingerprint": implementation_fingerprint,
                }
                rows.append(row)
            else:
                record_id = str(row.get("id") or "")

            attempts = int(row.get("attempts", 0) or 0) + 1
            successes = int(row.get("successes", 0) or 0) + (1 if success else 0)
            failures = int(row.get("failures", 0) or 0) + (0 if success else 1)
            verified_successes = int(row.get("verified_successes", 0) or 0) + (
                1 if success and verified else 0
            )

            previous_latency = row.get("mean_latency_ms")
            latency_samples = int(row.get("latency_samples", 0) or 0)
            clean_latency: float | None = None
            if latency_ms is not None:
                try:
                    clean_latency = max(0.0, min(3_600_000.0, float(latency_ms)))
                except (TypeError, ValueError):
                    clean_latency = None
            if clean_latency is not None:
                if previous_latency is None or latency_samples <= 0:
                    mean_latency = clean_latency
                else:
                    mean_latency = (
                        float(previous_latency) * latency_samples + clean_latency
                    ) / (latency_samples + 1)
                latency_samples += 1
                row["mean_latency_ms"] = round(mean_latency, 2)
            row["latency_samples"] = latency_samples

            reliability, strength = self._posterior(successes, failures)
            row.update({
                "attempts": attempts,
                "successes": successes,
                "failures": failures,
                "verified_successes": verified_successes,
                "reliability": reliability,
                "evidence_strength": strength,
                "evidence_ids": list(_tuple([
                    *(row.get("evidence_ids") or []),
                    *new_evidence,
                ], limit=48)),
                "last_observed_at": when,
                "last_result": _text(result, 1200),
                "last_success": bool(success),
            })
            data["records"] = rows[-self.capacity :]
            data["version"] = self.VERSION

        self._store.mutate(mutate)
        return self.get(record_id)

    def get(self, record_id: str) -> CompetenceRecord:
        for row in list(self._store.snapshot().get("records") or []):
            if str(row.get("id") or "") == str(record_id):
                return self._decode(row)
        raise KeyError(record_id)

    def find(
        self,
        *,
        capability: str = "",
        operation: str = "",
        node_id: str | None = None,
        skill_id: str | None = None,
        implementation_fingerprint: str | None = None,
        limit: int = 50,
    ) -> list[CompetenceRecord]:
        cap = _text(capability, 160).casefold()
        op = _text(operation, 80).casefold()
        implementation = (
            None
            if implementation_fingerprint is None
            else _text(implementation_fingerprint, 64).casefold()
        )
        output: list[CompetenceRecord] = []
        for row in list(self._store.snapshot().get("records") or []):
            item = self._decode(row)
            if cap and item.capability != cap:
                continue
            if op and item.operation != op:
                continue
            if node_id is not None and item.node_id != str(node_id):
                continue
            if skill_id is not None and item.skill_id != str(skill_id):
                continue
            if (
                implementation is not None
                and item.implementation_fingerprint != implementation
            ):
                continue
            output.append(item)
        output.sort(
            key=lambda item: (
                item.evidence_strength,
                item.reliability,
                item.verified_successes,
                item.last_observed_at,
            ),
            reverse=True,
        )
        return output[: max(1, min(500, int(limit)))]

    def summary_for(
        self,
        capability: str,
        *,
        operation: str = "",
        node_ids: Iterable[str] = (),
        implementation_fingerprint: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        allowed_nodes = {str(item) for item in node_ids if str(item)}
        rows = self.find(
            capability=capability,
            operation=operation,
            implementation_fingerprint=implementation_fingerprint,
            limit=200,
        )
        if allowed_nodes:
            rows = [item for item in rows if not item.node_id or item.node_id in allowed_nodes]
        return [
            {
                "capability": item.capability,
                "operation": item.operation,
                "node_id": item.node_id,
                "skill_id": item.skill_id,
                "implementation_fingerprint": item.implementation_fingerprint,
                "attempts": item.attempts,
                "successes": item.successes,
                "failures": item.failures,
                "verified_successes": item.verified_successes,
                "reliability": item.reliability,
                "evidence_strength": item.evidence_strength,
                "latency_samples": item.latency_samples,
                "mean_latency_ms": item.mean_latency_ms,
                "last_success": item.last_success,
                "last_observed_at": item.last_observed_at,
            }
            for item in rows[: max(1, min(50, int(limit)))]
        ]

    def status(self) -> dict[str, Any]:
        rows = [self._decode(row) for row in list(self._store.snapshot().get("records") or [])]
        return {
            "version": self.VERSION,
            "records": len(rows),
            "attempts": sum(item.attempts for item in rows),
            "verified_successes": sum(item.verified_successes for item in rows),
            "capabilities": len({item.capability for item in rows}),
            "nodes": len({item.node_id for item in rows if item.node_id}),
            "skills": len({item.skill_id for item in rows if item.skill_id}),
            "implementation_bound_records": sum(
                1 for item in rows if item.implementation_fingerprint
            ),
            "legacy_unbound_records": sum(
                1 for item in rows if not item.implementation_fingerprint
            ),
            "authority": (
                "durable operational evidence only; does not grant permission, "
                "select a model/node, or define Mary identity"
            ),
        }

    @staticmethod
    def _decode(row: dict[str, Any]) -> CompetenceRecord:
        values = dict(row)
        values["evidence_ids"] = tuple(values.get("evidence_ids") or [])
        values.setdefault("skill_id", "")
        values.setdefault("node_id", "")
        values.setdefault("verified_successes", 0)
        values.setdefault("latency_samples", 0)
        values.setdefault("mean_latency_ms", None)
        values.setdefault("reliability", 0.5)
        values.setdefault("evidence_strength", 0.0)
        values.setdefault("last_result", "")
        values.setdefault("last_success", None)
        values.setdefault("implementation_fingerprint", "")
        return CompetenceRecord(**values)
