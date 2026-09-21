"""Deterministic regression evaluation for Mary's local knowledge fabric.

Checks expected-source recall, disabled/forbidden-source leakage, citation
completeness, pack scoping, and bounded model-facing evidence. It performs no
LLM calls and cannot promote retrieval into memory, truth, identity, permission,
or model authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable

from mary.runtime.persistence import atomic_write_json, load_json_recovering

from mary.mind.context_governor import ContextEvidenceGovernor
from .fabric import KnowledgeFabric


def _strings(value: Any, limit: int = 100) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(str(x).strip()[:800] for x in list(value)[:limit] if str(x).strip())


def _source(locator: str) -> str:
    value = str(locator or "").replace("\\", "/").strip()
    marker = value.casefold().rfind("#chunk-")
    return value[:marker] if marker >= 0 else value


@dataclass(frozen=True)
class KnowledgeEvaluationCase:
    case_id: str
    query: str
    pack_ids: tuple[str, ...] = ()
    retrieval_mode: str = "auto"
    minimum_hits: int = 1
    expected_pack_ids: tuple[str, ...] = ()
    expected_locators: tuple[str, ...] = ()
    excluded_locators: tuple[str, ...] = ()
    require_citations: bool = True
    require_expected_in_context: bool = False
    context_budget_characters: int = 6000
    limit: int = 12

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "KnowledgeEvaluationCase":
        case_id = str(raw.get("case_id") or raw.get("id") or "").strip()
        query = str(raw.get("query") or "").strip()
        if not case_id:
            raise ValueError("knowledge evaluation case_id is required")
        if not query:
            raise ValueError(f"knowledge evaluation query is required for {case_id}")
        return cls(
            case_id=case_id[:160],
            query=query[:1000],
            pack_ids=_strings(raw.get("pack_ids")),
            retrieval_mode=str(raw.get("retrieval_mode") or "auto").strip().casefold(),
            minimum_hits=max(0, int(raw.get("minimum_hits", 1))),
            expected_pack_ids=_strings(raw.get("expected_pack_ids")),
            expected_locators=_strings(raw.get("expected_locators")),
            excluded_locators=_strings(raw.get("excluded_locators")),
            require_citations=bool(raw.get("require_citations", True)),
            require_expected_in_context=bool(raw.get("require_expected_in_context", False)),
            context_budget_characters=max(2000, int(raw.get("context_budget_characters", 6000))),
            limit=max(1, min(50, int(raw.get("limit", 12)))),
        )


@dataclass(frozen=True)
class KnowledgeEvaluationResult:
    case_id: str
    passed: bool
    failures: tuple[str, ...]
    raw_hits: int
    model_context_hits: int
    citation_coverage: float
    raw_evidence_characters: int
    model_context_characters: int
    context_budget_characters: int
    seen_pack_ids: tuple[str, ...]
    seen_locators: tuple[str, ...]
    selected_locators: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        for key in ("failures", "seen_pack_ids", "seen_locators", "selected_locators"):
            out[key] = list(out[key])
        return out


class KnowledgeFabricEvaluator:
    VERSION = 1

    def __init__(self, fabric: KnowledgeFabric) -> None:
        self.fabric = fabric

    @staticmethod
    def _chars(rows: Iterable[dict[str, Any]]) -> int:
        return sum(len(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)) for row in rows)

    @staticmethod
    def _matches(expected: str, actual: str) -> bool:
        e = _source(expected).casefold()
        a = _source(actual).casefold()
        return bool(e and (a == e or a.endswith("/" + e)))

    def evaluate_case(self, case: KnowledgeEvaluationCase) -> KnowledgeEvaluationResult:
        hits = self.fabric.search(
            case.query,
            pack_ids=case.pack_ids,
            limit=case.limit,
            retrieval_mode=case.retrieval_mode,
        )
        evidence = [hit.to_dict() for hit in hits]
        governor = ContextEvidenceGovernor(
            total_characters=case.context_budget_characters,
            lane_budgets={"knowledge": case.context_budget_characters},
        )
        selected, report = governor.govern({"knowledge": evidence})
        selected_rows = list(selected.get("knowledge") or [])
        seen_pack_ids = tuple(dict.fromkeys(hit.pack_id for hit in hits))
        seen_locators = tuple(dict.fromkeys(_source(hit.locator) for hit in hits))
        selected_locators = tuple(dict.fromkeys(
            _source(str(row.get("locator") or ""))
            for row in selected_rows if str(row.get("locator") or "")
        ))
        cited = sum(1 for hit in hits if str(hit.citation_id or "").strip())
        citation_coverage = 1.0 if not hits else cited / len(hits)
        failures: list[str] = []

        if len(hits) < case.minimum_hits:
            failures.append(f"minimum hits not met: {len(hits)} < {case.minimum_hits}")
        for pack_id in case.expected_pack_ids:
            if pack_id not in seen_pack_ids:
                failures.append(f"expected pack not retrieved: {pack_id}")
        for locator in case.expected_locators:
            if not any(self._matches(locator, actual) for actual in seen_locators):
                failures.append(f"expected locator not retrieved: {locator}")
        for locator in case.excluded_locators:
            if any(self._matches(locator, actual) for actual in seen_locators):
                failures.append(f"excluded locator appeared in retrieval: {locator}")
        if case.require_citations and hits and citation_coverage < 1.0:
            failures.append(f"citation coverage incomplete: {citation_coverage:.3f}")

        model_chars = int(report.get("used_characters") or self._chars(selected_rows))
        budget = int(report.get("total_budget_characters") or case.context_budget_characters)
        if model_chars > budget:
            failures.append(f"model context exceeded budget: {model_chars} > {budget}")
        if case.require_expected_in_context:
            for locator in case.expected_locators:
                if not any(self._matches(locator, actual) for actual in selected_locators):
                    failures.append(f"expected locator omitted from model context: {locator}")

        return KnowledgeEvaluationResult(
            case_id=case.case_id,
            passed=not failures,
            failures=tuple(failures),
            raw_hits=len(hits),
            model_context_hits=len(selected_rows),
            citation_coverage=round(citation_coverage, 4),
            raw_evidence_characters=self._chars(evidence),
            model_context_characters=model_chars,
            context_budget_characters=budget,
            seen_pack_ids=seen_pack_ids,
            seen_locators=seen_locators,
            selected_locators=selected_locators,
        )

    def evaluate(self, cases: Iterable[KnowledgeEvaluationCase]) -> dict[str, Any]:
        results = [self.evaluate_case(case) for case in cases]
        passed = sum(1 for item in results if item.passed)
        return {
            "version": self.VERSION,
            "passed": passed,
            "failed": len(results) - passed,
            "cases": len(results),
            "all_passed": bool(results) and passed == len(results),
            "results": [item.to_dict() for item in results],
            "policy": "deterministic retrieval regression only; no LLM judge and no automatic state/model promotion",
        }


def load_knowledge_evaluation_cases(path: str | Path) -> list[KnowledgeEvaluationCase]:
    source = Path(path)
    output: list[KnowledgeEvaluationCase] = []
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid knowledge evaluation JSONL at line {number}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"knowledge evaluation line {number} must be an object")
        output.append(KnowledgeEvaluationCase.from_mapping(raw))
    return output


def knowledge_substrate_fingerprint(fabric: KnowledgeFabric) -> str:
    """Hash retrieval-affecting substrate state without retaining source/query text."""
    packs = []
    for pack in list(fabric.packs())[:512]:
        packs.append({
            "id": str(pack.id),
            "collection": str(pack.collection),
            "kind": str(pack.kind),
            "query_mode": str(pack.query_mode),
            "ingest_policy": str(pack.ingest_policy),
            "enabled": bool(pack.enabled),
            "local_only": bool(pack.local_only),
            "content_fingerprint": str(pack.content_fingerprint or ""),
            "disabled_documents": list(pack.disabled_documents),
            "metadata": dict(pack.metadata or {}),
        })
    payload = {
        "profile": dict(fabric.substrate_profile() or {}),
        "packs": packs,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()


def knowledge_case_set_fingerprint(cases: Iterable[KnowledgeEvaluationCase]) -> str:
    """Fingerprint exact regression cases while retaining no query body in evidence."""
    payload = [asdict(case) for case in list(cases)]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()


class KnowledgeEvaluationEvidenceStore:
    """Content-free durable evidence that deterministic retrieval regression ran.

    This is evaluation lineage only. It never stores queries, retrieved snippets,
    locators, prompts, source bodies, or model output and grants no truth/memory
    authority.
    """

    VERSION = 1

    def __init__(self, path: str | Path, *, capacity: int = 24) -> None:
        self.path = Path(path)
        self.capacity = max(4, min(128, int(capacity)))

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": self.VERSION, "runs": []}
        payload, _source = load_json_recovering(self.path, backup_generations=2)
        if not isinstance(payload, dict):
            return {"version": self.VERSION, "runs": []}
        return payload

    def record(
        self,
        summary: dict[str, Any],
        *,
        substrate_fingerprint: str,
        case_set_fingerprint: str,
    ) -> dict[str, Any]:
        cases = []
        for raw in list(summary.get("results") or [])[:500]:
            if not isinstance(raw, dict):
                continue
            cases.append({
                "case_id": str(raw.get("case_id") or "")[:160],
                "passed": bool(raw.get("passed")),
                "failure_count": len(list(raw.get("failures") or [])),
                "raw_hits": int(raw.get("raw_hits") or 0),
                "model_context_hits": int(raw.get("model_context_hits") or 0),
                "citation_coverage": float(raw.get("citation_coverage") or 0.0),
            })
        run = {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "substrate_fingerprint": str(substrate_fingerprint or "")[:128],
            "case_set_fingerprint": str(case_set_fingerprint or "")[:128],
            "passed": int(summary.get("passed") or 0),
            "failed": int(summary.get("failed") or 0),
            "cases": int(summary.get("cases") or len(cases)),
            "all_passed": bool(summary.get("all_passed")),
            "case_results": cases,
            "content_retained": False,
            "queries_retained": False,
            "retrieved_text_retained": False,
            "automatic_promotion": False,
        }
        payload = self._load()
        runs = [item for item in list(payload.get("runs") or []) if isinstance(item, dict)]
        runs.append(run)
        payload = {"version": self.VERSION, "runs": runs[-self.capacity:]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.path, payload, backup_generations=2, indent=2)
        return dict(run)

    def snapshot(self, *, current_substrate_fingerprint: str = "") -> dict[str, Any]:
        payload = self._load()
        runs = [dict(item) for item in list(payload.get("runs") or []) if isinstance(item, dict)]
        latest = dict(runs[-1]) if runs else {}
        recorded = str(latest.get("substrate_fingerprint") or "")
        current = str(current_substrate_fingerprint or "")
        stale = bool(latest and current and recorded != current)
        return {
            "version": self.VERSION,
            "runs": len(runs),
            "latest": latest,
            "latest_all_passed": bool(latest.get("all_passed")) if latest else False,
            "stale": stale,
            "current_substrate_match": bool(latest and current and recorded == current),
            "content_retained": False,
            "queries_retained": False,
            "retrieved_text_retained": False,
            "automatic_promotion": False,
            "authority": "deterministic retrieval evaluation evidence only",
        }
