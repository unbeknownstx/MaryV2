"""Mary-specific character evaluation contracts.

This is intentionally separate from memory and training feedback.  It provides
repeatable *acceptance cases* for answering a different question than ordinary
unit tests: did a response still behave like Mary?

The deterministic evaluator only checks explicit invariants/anti-patterns.  It
never claims to fully judge character quality, and an optional future external
judge can consume the same cases without becoming character authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable


@dataclass(frozen=True)
class MaryEvalCase:
    case_id: str
    prompt: str
    category: str = "character"
    description: str = ""
    required_phrases: tuple[str, ...] = ()
    forbidden_phrases: tuple[str, ...] = ()
    forbidden_patterns: tuple[str, ...] = ()
    expected_labels: tuple[str, ...] = ()
    notes: str = ""
    source: str = "creator_authored"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MaryEvalResult:
    case_id: str
    passed: bool
    failures: tuple[str, ...]
    checks: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MaryEvaluationSet:
    VERSION = "1.0"
    MAX_CASES = 1000

    # High-signal generic assistant patterns.  These are deliberately narrow;
    # false positives are worse than missing a style problem.
    DEFAULT_FORBIDDEN_PATTERNS = (
        r"\bas an ai language model\b",
        r"\bi don't have personal (?:feelings|opinions|experiences)\b",
        r"\bhow can i assist you today\b",
        r"\bis there anything else i can help you with\b",
    )

    def __init__(self, cases: Iterable[MaryEvalCase] = (), *, load_errors: Iterable[str] = ()) -> None:
        self.cases = tuple(list(cases)[: self.MAX_CASES])
        self.load_errors = tuple(str(item)[:500] for item in load_errors)
        digest = sha256()
        for case in self.cases:
            digest.update(case.case_id.encode("utf-8"))
            digest.update(case.prompt.encode("utf-8"))
        self.fingerprint = digest.hexdigest()[:20]

    @classmethod
    def empty(cls) -> "MaryEvaluationSet":
        return cls(())

    @classmethod
    def from_environment(cls, *, root: str | Path | None = None) -> "MaryEvaluationSet":
        raw = str(os.getenv("MARY_CHARACTER_EVALS", "") or "").strip()
        if not raw:
            base = Path(root) if root is not None else Path.cwd()
            candidates = [
                base / "character_sources" / "mary_evaluation.json",
                base / "docs" / "character" / "mary_evaluation.json",
            ]
            path = next((item for item in candidates if item.exists()), None)
            return cls.from_file(path) if path else cls.empty()
        return cls.from_file(Path(raw).expanduser())

    @classmethod
    def from_file(cls, path: str | Path | None) -> "MaryEvaluationSet":
        if path is None:
            return cls.empty()
        target = Path(path)
        if not target.exists():
            return cls((), load_errors=[f"missing Mary evaluation set: {target}"])
        try:
            if target.suffix.lower() == ".jsonl":
                rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                raw = json.loads(target.read_text(encoding="utf-8"))
                rows = raw.get("cases", []) if isinstance(raw, dict) else raw
            cases = [cls._case(row, index) for index, row in enumerate(rows or [], start=1) if isinstance(row, dict)]
            return cls(cases)
        except Exception as exc:
            return cls((), load_errors=[f"{target}: {type(exc).__name__}: {exc}"])

    @staticmethod
    def _case(row: dict[str, Any], index: int) -> MaryEvalCase:
        prompt = str(row.get("prompt") or "").strip()
        if not prompt:
            raise ValueError(f"Mary evaluation case {index} has no prompt")
        case_id = str(row.get("case_id") or row.get("id") or f"mary_eval_{index:04d}").strip()
        return MaryEvalCase(
            case_id=case_id[:120],
            prompt=prompt[:8000],
            category=str(row.get("category") or "character")[:80],
            description=str(row.get("description") or "")[:1000],
            required_phrases=tuple(str(x)[:240] for x in list(row.get("required_phrases", []) or [])[:32]),
            forbidden_phrases=tuple(str(x)[:240] for x in list(row.get("forbidden_phrases", []) or [])[:32]),
            forbidden_patterns=tuple(str(x)[:400] for x in list(row.get("forbidden_patterns", []) or [])[:32]),
            expected_labels=tuple(str(x)[:40] for x in list(row.get("expected_labels", []) or [])[:16]),
            notes=str(row.get("notes") or "")[:1500],
            source=str(row.get("source") or "creator_authored")[:80],
            metadata={str(k)[:80]: v for k, v in list(dict(row.get("metadata", {}) or {}).items())[:24] if isinstance(v, (str, int, float, bool)) or v is None},
        )

    def get(self, case_id: str) -> MaryEvalCase:
        for case in self.cases:
            if case.case_id == case_id:
                return case
        raise KeyError(case_id)

    def evaluate(self, case: MaryEvalCase | str, response: str) -> MaryEvalResult:
        item = self.get(case) if isinstance(case, str) else case
        text = str(response or "")
        lowered = text.lower()
        failures: list[str] = []
        checks = 0
        for phrase in item.required_phrases:
            checks += 1
            if phrase.lower() not in lowered:
                failures.append(f"missing required phrase: {phrase}")
        for phrase in item.forbidden_phrases:
            checks += 1
            if phrase.lower() in lowered:
                failures.append(f"forbidden phrase present: {phrase}")
        for pattern in (*self.DEFAULT_FORBIDDEN_PATTERNS, *item.forbidden_patterns):
            checks += 1
            try:
                if re.search(pattern, text, flags=re.IGNORECASE):
                    failures.append(f"forbidden pattern matched: {pattern}")
            except re.error:
                failures.append(f"invalid evaluation pattern: {pattern}")
        return MaryEvalResult(item.case_id, not failures, tuple(failures), checks)

    def snapshot(self) -> dict[str, Any]:
        categories: dict[str, int] = {}
        for case in self.cases:
            categories[case.category] = categories.get(case.category, 0) + 1
        return {
            "enabled": bool(self.cases),
            "version": self.VERSION,
            "cases": len(self.cases),
            "categories": categories,
            "fingerprint": self.fingerprint,
            "errors": list(self.load_errors)[:16],
            "semantics": {
                "memory_owner": False,
                "character_authority": False,
                "acceptance_evidence": True,
                "automatic_training": False,
            },
        }
