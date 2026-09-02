"""Reproducible Mary model/LoRA experiments against a local llama.cpp server.

The experiment runner is deliberately outside Mary's canonical conversation and
identity owners.  It can ask a local model to answer held-out Mary evaluation
prompts with per-request LoRA scales, then writes an experiment artifact under
private ``data/training`` for creator review.  It never promotes an output into
memory, character canon, developed self, or relationship state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
from time import monotonic
from typing import Any, Iterable, Mapping, Sequence

from mary.character.sourcebook import CharacterSourcebook
from mary.llm.interface import LLMMessage
from mary.llm.providers.llama_cpp import LlamaCppProvider


@dataclass(frozen=True)
class AdapterMix:
    """One server-loaded llama.cpp adapter id and request-local scale."""

    adapter_id: int
    scale: float = 1.0
    label: str = ""

    def normalized(self) -> dict[str, float | int]:
        return {
            "id": max(0, int(self.adapter_id)),
            "scale": round(max(-4.0, min(4.0, float(self.scale))), 4),
        }


@dataclass(frozen=True)
class ExperimentConfiguration:
    config_id: str
    label: str
    base_model: str = "local"
    adapters: tuple[AdapterMix, ...] = ()
    temperature: float = 0.7
    max_tokens: int = 600
    system_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_id": self.config_id[:120],
            "label": self.label[:180],
            "base_model": self.base_model[:300],
            "adapters": [item.normalized() | ({"label": item.label[:120]} if item.label else {}) for item in self.adapters[:16]],
            "temperature": max(0.0, min(2.0, float(self.temperature))),
            "max_tokens": max(32, min(4096, int(self.max_tokens))),
            # Keep actual prompt content out of run metadata.  The prompt may
            # contain private character material; only a one-way hash is kept.
            "system_prompt_sha256": hashlib.sha256(self.system_prompt.encode("utf-8")).hexdigest() if self.system_prompt else "",
        }


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    prompt: str
    relationship: str = ""
    tags: tuple[str, ...] = ()
    must_have: tuple[str, ...] = ()
    should_have: tuple[str, ...] = ()
    fail_if: tuple[str, ...] = ()
    score_dimensions: tuple[str, ...] = ()
    literal_must_have: tuple[str, ...] = ()
    literal_should_have: tuple[str, ...] = ()
    literal_fail_if: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvalCase":
        case_id = str(value.get("id") or value.get("case_id") or "").strip()
        prompt = str(value.get("prompt") or "").strip()
        if not case_id or not prompt:
            raise ValueError("evaluation case requires id/case_id and prompt")
        def values(key: str) -> tuple[str, ...]:
            raw = value.get(key) or ()
            if isinstance(raw, str):
                raw = [raw]
            return tuple(str(item).strip()[:300] for item in list(raw)[:32] if str(item).strip())
        return cls(
            case_id=case_id[:120],
            prompt=prompt[:8000],
            relationship=str(value.get("relationship") or "")[:120],
            tags=values("tags"),
            must_have=values("must_have"),
            should_have=values("should_have"),
            fail_if=values("fail_if"),
            score_dimensions=values("score_dimensions"),
            literal_must_have=values("literal_must_have"),
            literal_should_have=values("literal_should_have"),
            literal_fail_if=values("literal_fail_if"),
        )

    def review_context(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "prompt": self.prompt,
            "relationship": self.relationship,
            "tags": list(self.tags),
            "must_have": list(self.must_have),
            "should_have": list(self.should_have),
            "fail_if": list(self.fail_if),
            "score_dimensions": list(self.score_dimensions),
            "literal_must_have": list(self.literal_must_have),
            "literal_should_have": list(self.literal_should_have),
            "literal_fail_if": list(self.literal_fail_if),
        }


@dataclass(frozen=True)
class ExperimentResult:
    run_id: str
    case_id: str
    config_id: str
    content: str
    latency_ms: float
    provider: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    error_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "config_id": self.config_id,
            "content": self.content[:20000],
            "latency_ms": round(max(0.0, float(self.latency_ms)), 2),
            "provider": self.provider[:80],
            "model": self.model[:300],
            "usage": {str(k)[:80]: max(0, int(v)) for k, v in dict(self.usage or {}).items()},
            "error_type": self.error_type[:120],
        }


@dataclass(frozen=True)
class AutomaticCaseScore:
    case_id: str
    config_id: str
    score: float
    must_coverage: float
    should_coverage: float
    fail_hits: tuple[str, ...] = ()
    hard_fail: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "config_id": self.config_id,
            "score": round(max(0.0, min(1.0, float(self.score))), 3),
            "must_coverage": round(max(0.0, min(1.0, float(self.must_coverage))), 3),
            "should_coverage": round(max(0.0, min(1.0, float(self.should_coverage))), 3),
            "fail_hits": list(self.fail_hits),
            "hard_fail": bool(self.hard_fail),
        }


@dataclass(frozen=True)
class ExperimentSummary:
    run_id: str
    created_at: str
    output_dir: str
    cases: int
    configurations: int
    generations: int
    failures: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdapterExperimentRunner:
    """Run held-out character cases with request-local llama.cpp LoRA scales."""

    VERSION = "1"

    def __init__(
        self,
        provider: LlamaCppProvider,
        *,
        output_root: str | Path,
        sourcebook: CharacterSourcebook | None = None,
    ) -> None:
        self.provider = provider
        self.output_root = Path(output_root)
        self.sourcebook = sourcebook

    @staticmethod
    def load_cases(path: str | Path, *, limit: int | None = None) -> list[EvalCase]:
        output: list[EvalCase] = []
        source = Path(path)
        for line in source.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                raw = json.loads(line)
                if isinstance(raw, dict):
                    output.append(EvalCase.from_mapping(raw))
            except (ValueError, json.JSONDecodeError):
                continue
            if limit is not None and len(output) >= max(1, int(limit)):
                break
        return output

    def _character_system_prompt(self, case: EvalCase, config: ExperimentConfiguration) -> str:
        records: list[dict[str, Any]] = []
        sourcebook_hash = ""
        if self.sourcebook is not None:
            try:
                selection = self.sourcebook.select(case.prompt, limit=6, max_characters=4200)
                view = selection.prompt_view()
                records = list(view.get("records") or [])[:6]
                sourcebook_hash = str(view.get("sourcebook_hash") or "")
            except Exception:
                records = []
        authored = "\n".join(
            f"- labels={','.join(str(x) for x in item.get('labels', []))}; "
            f"boundary={item.get('boundary', 'authored_character_evidence')}; "
            f"{str(item.get('text') or '')[:1400]}"
            for item in records if isinstance(item, dict)
        )
        base = (
            "You are realizing dialogue for Mary, a persistent creator-authored AI character, not a generic assistant. "
            "This is a held-out model-fit experiment: do not claim tools/actions occurred and do not invent memories or creator facts. "
            "Talk naturally and directly. Avoid customer-service closers, forced questions, forced jokes, and generic assistant disclaimers. "
            "Creator-authored evidence below is character direction; FC fictional canon is reference rather than AI-lived memory and NEG examples are failures to avoid. "
            f"Relationship lens for this case: {case.relationship or 'unspecified'}. "
            f"Sourcebook fingerprint: {sourcebook_hash or 'not_loaded'}."
        )
        if authored:
            base += "\n\nRelevant creator-authored Mary evidence:\n" + authored
        if config.system_prompt:
            base += "\n\nExperiment-specific direction:\n" + config.system_prompt[:4000]
        return base

    def _messages(self, case: EvalCase, config: ExperimentConfiguration) -> list[LLMMessage]:
        return [
            LLMMessage(role="system", content=self._character_system_prompt(case, config)),
            LLMMessage(role="user", content=case.prompt),
        ]

    @staticmethod
    def automatic_score(case: EvalCase, result: ExperimentResult) -> AutomaticCaseScore:
        """Apply only explicit held-out checks; never pretend this measures Mary by itself."""
        text = " ".join(str(result.content or "").casefold().split())

        def coverage(requirements: tuple[str, ...]) -> float:
            if not requirements:
                return 1.0
            hits = sum(1 for item in requirements if str(item).casefold() in text)
            return hits / len(requirements)

        # The existing Mary evaluation suite contains human semantic rubrics
        # such as "natural direct response".  Those are intentionally *not*
        # substring assertions.  Only explicitly named literal_* checks are
        # machine-scored; the semantic rubrics remain for blinded creator
        # review (and future trained evaluators).
        must = coverage(case.literal_must_have)
        should = coverage(case.literal_should_have)
        fail_hits = tuple(item for item in case.literal_fail_if if str(item).casefold() in text)
        hard_fail = bool(
            result.error_type
            or not text
            or fail_hits
            or (case.literal_must_have and must < 1.0)
        )

        # This is a literal regression gate, not a character judge. Creator
        # blind scoring remains the meaningful Mary-fit signal.
        has_literal_checks = bool(case.literal_must_have or case.literal_should_have or case.literal_fail_if)
        score = (
            .50 * must + .25 * should + (.25 if text and not result.error_type else 0.0)
            if has_literal_checks
            else (1.0 if text and not result.error_type else 0.0)
        )
        if fail_hits:
            score *= .15
        if result.error_type:
            score = 0.0
        return AutomaticCaseScore(
            case_id=case.case_id,
            config_id=result.config_id,
            score=max(0.0, min(1.0, score)),
            must_coverage=must,
            should_coverage=should,
            fail_hits=fail_hits,
            hard_fail=hard_fail,
        )

    @staticmethod
    def _automatic_leaderboard(
        scores: Sequence[AutomaticCaseScore],
        results: Sequence[ExperimentResult],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[AutomaticCaseScore]] = {}
        for item in scores:
            grouped.setdefault(item.config_id, []).append(item)
        latencies: dict[str, list[float]] = {}
        for item in results:
            latencies.setdefault(item.config_id, []).append(float(item.latency_ms))
        rows: list[dict[str, Any]] = []
        for config_id, items in grouped.items():
            avg = sum(item.score for item in items) / max(1, len(items))
            hard_fails = sum(1 for item in items if item.hard_fail)
            latency_values = latencies.get(config_id) or [0.0]
            rows.append({
                "config_id": config_id,
                "automatic_score": round(avg, 3),
                "hard_failures": hard_fails,
                "cases": len(items),
                "mean_latency_ms": round(sum(latency_values) / max(1, len(latency_values)), 2),
            })
        rows.sort(key=lambda row: (row["hard_failures"], -row["automatic_score"], row["mean_latency_ms"]))
        return rows

    @staticmethod
    def summarize_blind_review(run_dir: str | Path) -> dict[str, Any]:
        """Aggregate creator-entered blind scores without promoting anything into Mary."""
        root = Path(run_dir)
        review = json.loads((root / "blind_review.json").read_text(encoding="utf-8"))
        key_rows = json.loads((root / "blind_key.json").read_text(encoding="utf-8"))
        key = {str(item.get("option_id")): str(item.get("config_id")) for item in key_rows if isinstance(item, dict)}
        grouped: dict[str, list[float]] = {}
        preferred: dict[str, int] = {}
        dimensions: dict[str, dict[str, list[float]]] = {}
        scored_options = 0
        for row in review:
            if not isinstance(row, dict):
                continue
            for option in list(row.get("options") or []):
                if not isinstance(option, dict):
                    continue
                config_id = key.get(str(option.get("option_id") or ""))
                if not config_id:
                    continue
                raw_scores = option.get("scores") if isinstance(option.get("scores"), dict) else {}
                clean_scores: list[float] = []
                for dimension, raw in raw_scores.items():
                    try:
                        value = max(0.0, min(1.0, float(raw)))
                    except (TypeError, ValueError):
                        continue
                    clean_scores.append(value)
                    dimensions.setdefault(config_id, {}).setdefault(str(dimension)[:80], []).append(value)
                if clean_scores:
                    scored_options += 1
                    grouped.setdefault(config_id, []).append(sum(clean_scores) / len(clean_scores))
                if bool(option.get("preferred")):
                    preferred[config_id] = preferred.get(config_id, 0) + 1
        rows: list[dict[str, Any]] = []
        for config_id in sorted(set(grouped) | set(preferred) | set(dimensions)):
            scores = grouped.get(config_id) or []
            dim_summary = {
                name: round(sum(values) / len(values), 3)
                for name, values in sorted((dimensions.get(config_id) or {}).items())
                if values
            }
            rows.append({
                "config_id": config_id,
                "creator_score": None if not scores else round(sum(scores) / len(scores), 3),
                "preferred_count": preferred.get(config_id, 0),
                "dimensions": dim_summary,
                "scored_options": len(scores),
            })
        rows.sort(key=lambda row: (-(row["preferred_count"]), -(row["creator_score"] if row["creator_score"] is not None else -1)))
        payload = {
            "version": 1,
            "scored_options": scored_options,
            "leaderboard": rows,
            "policy": "creator experiment review only; no automatic character/canon/memory promotion",
        }
        (root / "creator_review_summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload

    def run(
        self,
        cases: Sequence[EvalCase],
        configurations: Sequence[ExperimentConfiguration],
        *,
        seed: int = 1337,
    ) -> ExperimentSummary:
        if not cases:
            raise ValueError("at least one evaluation case is required")
        if not configurations:
            raise ValueError("at least one experiment configuration is required")

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"adapter_{stamp}_{hashlib.sha256(str(seed).encode()).hexdigest()[:8]}"
        run_dir = self.output_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)

        # Metadata is intentionally source-safe: no credentials or system
        # prompt contents are written here.
        manifest = {
            "version": self.VERSION,
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "policy": "offline experiment only; creator review required; no canonical Mary state writes",
            "configurations": [item.to_dict() for item in configurations],
            "cases": [item.review_context() for item in cases],
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        results: list[ExperimentResult] = []
        failures = 0
        for case in cases:
            for config in configurations:
                started = monotonic()
                try:
                    response = self.provider.generate_with_lora(
                        self._messages(case, config),
                        lora=[adapter.normalized() for adapter in config.adapters],
                        temperature=config.temperature,
                        max_tokens=config.max_tokens,
                        model=config.base_model or None,
                    )
                    result = ExperimentResult(
                        run_id=run_id,
                        case_id=case.case_id,
                        config_id=config.config_id,
                        content=response.content,
                        latency_ms=(monotonic() - started) * 1000.0,
                        provider=response.provider,
                        model=response.model,
                        usage=dict(response.usage or {}),
                    )
                except Exception as exc:  # noqa: BLE001 - experiments record failure and continue
                    failures += 1
                    result = ExperimentResult(
                        run_id=run_id,
                        case_id=case.case_id,
                        config_id=config.config_id,
                        content="",
                        latency_ms=(monotonic() - started) * 1000.0,
                        provider="llama_cpp",
                        model=config.base_model,
                        error_type=type(exc).__name__,
                    )
                results.append(result)

        with (run_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
            for result in results:
                handle.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")

        case_lookup = {item.case_id: item for item in cases}
        automatic = [
            self.automatic_score(case_lookup[result.case_id], result)
            for result in results
            if result.case_id in case_lookup
        ]
        automatic_payload = {
            "version": 1,
            "scores": [item.to_dict() for item in automatic],
            "leaderboard": self._automatic_leaderboard(automatic, results),
            "policy": "explicit literal regression checks only; semantic Mary likeness requires blinded creator review",
        }
        (run_dir / "automatic_review.json").write_text(
            json.dumps(automatic_payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        self._write_blind_review(run_dir, cases, configurations, results, seed=seed)
        summary = ExperimentSummary(
            run_id=run_id,
            created_at=manifest["created_at"],
            output_dir=str(run_dir),
            cases=len(cases),
            configurations=len(configurations),
            generations=len(results),
            failures=failures,
        )
        (run_dir / "summary.json").write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
        return summary

    @staticmethod
    def _write_blind_review(
        run_dir: Path,
        cases: Sequence[EvalCase],
        configurations: Sequence[ExperimentConfiguration],
        results: Sequence[ExperimentResult],
        *,
        seed: int,
    ) -> None:
        by_case: dict[str, list[ExperimentResult]] = {}
        for item in results:
            by_case.setdefault(item.case_id, []).append(item)
        case_lookup = {item.case_id: item for item in cases}
        config_lookup = {item.config_id: item for item in configurations}
        rng = random.Random(seed)
        review_rows: list[dict[str, Any]] = []
        key_rows: list[dict[str, Any]] = []
        for case_id, candidates in by_case.items():
            shuffled = list(candidates)
            rng.shuffle(shuffled)
            options: list[dict[str, Any]] = []
            for index, result in enumerate(shuffled):
                option_id = f"{case_id}:option_{index + 1}"
                options.append({
                    "option_id": option_id,
                    "response": result.content,
                    "error_type": result.error_type,
                    "latency_ms": round(result.latency_ms, 2),
                    "scores": {},
                    "notes": "",
                    "preferred": False,
                })
                key_rows.append({
                    "option_id": option_id,
                    "config_id": result.config_id,
                    "config_label": config_lookup[result.config_id].label if result.config_id in config_lookup else result.config_id,
                })
            review_rows.append({
                "case": case_lookup[case_id].review_context(),
                "options": options,
            })
        (run_dir / "blind_review.json").write_text(json.dumps(review_rows, indent=2, ensure_ascii=False), encoding="utf-8")
        (run_dir / "blind_key.json").write_text(json.dumps(key_rows, indent=2, ensure_ascii=False), encoding="utf-8")
