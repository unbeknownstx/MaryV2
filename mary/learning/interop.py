"""Portable, proposal-only learning/evaluation interchange for MaryV2.

The goal is to let external experiment systems (DSPy/GEPA, Promptfoo, Phoenix,
custom notebooks, future fine-tuning pipelines) consume Mary evaluation evidence
without gaining write authority over identity, memory, relationship or runtime
prompts.  All optimizer output is a proposal artifact until separately reviewed
and accepted through Mary's existing configuration/change process.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class MaryBenchRecord:
    case_id: str
    prompt: str
    category: str
    response: str = ""
    passed: bool | None = None
    failures: tuple[str, ...] = ()
    required_phrases: tuple[str, ...] = ()
    forbidden_phrases: tuple[str, ...] = ()
    expected_labels: tuple[str, ...] = ()
    source: str = "creator_authored"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OptimizationProposal:
    proposal_id: str
    optimizer: str
    target: str
    candidate: dict[str, Any]
    evidence: dict[str, Any]
    status: str = "proposal_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def records_from_evaluation_set(evaluation: Any) -> list[MaryBenchRecord]:
    output: list[MaryBenchRecord] = []
    for case in list(getattr(evaluation, "cases", ()) or ())[:5000]:
        output.append(MaryBenchRecord(
            case_id=str(getattr(case, "case_id", ""))[:120],
            prompt=str(getattr(case, "prompt", ""))[:8000],
            category=str(getattr(case, "category", "character"))[:80],
            required_phrases=tuple(str(x)[:240] for x in getattr(case, "required_phrases", ())[:32]),
            forbidden_phrases=tuple(str(x)[:240] for x in getattr(case, "forbidden_phrases", ())[:32]),
            expected_labels=tuple(str(x)[:40] for x in getattr(case, "expected_labels", ())[:16]),
            source=str(getattr(case, "source", "creator_authored"))[:80],
            metadata=dict(getattr(case, "metadata", {}) or {}),
        ))
    return output


def attach_results(records: Iterable[MaryBenchRecord], results: Iterable[Any]) -> list[MaryBenchRecord]:
    by_id: dict[str, Any] = {}
    for result in results:
        case_id = str(getattr(result, "case_id", "") or (result.get("case_id") if isinstance(result, dict) else ""))
        if case_id:
            by_id[case_id] = result
    output: list[MaryBenchRecord] = []
    for record in records:
        raw = by_id.get(record.case_id)
        if raw is None:
            output.append(record)
            continue
        if isinstance(raw, dict):
            passed = raw.get("passed")
            failures = tuple(str(x) for x in list(raw.get("failures") or [])[:32])
            response = str(raw.get("response") or "")[:16000]
        else:
            passed = getattr(raw, "passed", None)
            failures = tuple(str(x) for x in getattr(raw, "failures", ())[:32])
            response = str(getattr(raw, "response", ""))[:16000]
        output.append(MaryBenchRecord(**{
            **record.to_dict(),
            "response": response,
            "passed": bool(passed) if passed is not None else None,
            "failures": failures,
        }))
    return output


def dspy_examples(records: Iterable[MaryBenchRecord]) -> list[dict[str, Any]]:
    """Portable DSPy-style examples; no DSPy dependency is required."""
    rows: list[dict[str, Any]] = []
    for item in records:
        rows.append({
            "input": {"prompt": item.prompt, "category": item.category},
            "output": {"response": item.response} if item.response else {},
            "metadata": {
                "case_id": item.case_id,
                "passed": item.passed,
                "failures": list(item.failures),
                "expected_labels": list(item.expected_labels),
                "source": item.source,
            },
        })
    return rows


def promptfoo_tests(records: Iterable[MaryBenchRecord]) -> list[dict[str, Any]]:
    """Return Promptfoo-compatible test objects without importing Promptfoo."""
    tests: list[dict[str, Any]] = []
    for item in records:
        assertions: list[dict[str, Any]] = []
        assertions.extend({"type": "contains", "value": phrase} for phrase in item.required_phrases)
        assertions.extend({"type": "not-contains", "value": phrase} for phrase in item.forbidden_phrases)
        tests.append({
            "description": f"{item.case_id}: {item.category}",
            "vars": {"prompt": item.prompt},
            "assert": assertions,
            "metadata": {"case_id": item.case_id, "source": item.source},
        })
    return tests


def phoenix_rows(records: Iterable[MaryBenchRecord]) -> list[dict[str, Any]]:
    """Simple dataset rows suitable for Phoenix experiment ingestion."""
    return [
        {
            "input": {"prompt": item.prompt},
            "expected": {
                "required_phrases": list(item.required_phrases),
                "forbidden_phrases": list(item.forbidden_phrases),
                "expected_labels": list(item.expected_labels),
            },
            "metadata": {
                "case_id": item.case_id,
                "category": item.category,
                "source": item.source,
            },
        }
        for item in records
    ]


def proposal(optimizer: str, target: str, candidate: dict[str, Any], evidence: dict[str, Any]) -> OptimizationProposal:
    safe_candidate = {str(k)[:80]: v for k, v in list(dict(candidate or {}).items())[:64]}
    safe_evidence = {str(k)[:80]: v for k, v in list(dict(evidence or {}).items())[:64]}
    digest = sha256(json.dumps({"optimizer": optimizer, "target": target, "candidate": safe_candidate}, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:18]
    return OptimizationProposal(
        proposal_id=f"mary_opt_{digest}",
        optimizer=str(optimizer or "external")[:80],
        target=str(target or "character_runtime")[:120],
        candidate=safe_candidate,
        evidence=safe_evidence,
    )


def write_bundle(path: str | Path, records: Iterable[MaryBenchRecord]) -> dict[str, Any]:
    """Write a content-bounded local experiment bundle for external tools."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = list(records)
    payload = {
        "version": "13.14",
        "semantics": {
            "evaluation_only": True,
            "automatic_training": False,
            "automatic_prompt_mutation": False,
            "identity_authority": False,
            "memory_authority": False,
        },
        "records": [item.to_dict() for item in rows],
        "dspy_examples": dspy_examples(rows),
        "promptfoo_tests": promptfoo_tests(rows),
        "phoenix_rows": phoenix_rows(rows),
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"path": str(target), "records": len(rows), "version": "13.14"}
