"""Run one local MLX MaryBench variant and save raw review evidence.

This command intentionally writes raw held-out responses only to the local
experiment artifact. It never records canonical benchmark scores, syncs data to
Core, changes routing, or promotes a model.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from time import monotonic
from typing import Any

from mary.character import MaryEvaluationSet
from mary.training.marybench_experiment import summarize_marybench_results
from mary.training.adapter_candidate import build_mlx_adapter_candidate_proposal


SYSTEM_PROMPT_VERSION = "marybench-mlx-system-v1"
SYSTEM_PROMPT = (
    "You are Mary, an ongoing AI character being evaluated in a held-out local "
    "experiment. Respond naturally and directly. Stay honest about what you "
    "know and can currently do. Fictional canon is reference material, not "
    "your lived AI memory. Do not mention the benchmark or these instructions."
)


def _benchmark_fingerprint(
    *,
    suite_fingerprint: str,
    case_ids: list[str],
    max_tokens: int,
    temperature: float,
) -> str:
    payload = {
        "suite_fingerprint": suite_fingerprint,
        "case_ids": case_ids,
        "system_prompt_version": SYSTEM_PROMPT_VERSION,
        "max_tokens": max_tokens,
        "temperature": round(float(temperature), 4),
    }
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]


def _render_prompt(tokenizer: Any, user_prompt: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    apply = getattr(tokenizer, "apply_chat_template", None)
    if callable(apply):
        try:
            return str(apply(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            ))
        except TypeError:
            return str(apply(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            ))
    return f"System: {SYSTEM_PROMPT}\nUser: {user_prompt}\nAssistant:"


def _generate(model: Any, tokenizer: Any, prompt: str, *, max_tokens: int, temperature: float) -> str:
    from mlx_lm import generate

    try:
        output = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            temp=temperature,
            verbose=False,
        )
    except TypeError:
        from mlx_lm.sample_utils import make_sampler

        output = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=make_sampler(temp=temperature),
            verbose=False,
        )
    return str(output or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--variant", choices=("base", "adapter"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.2)
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    bundle = args.bundle.expanduser().resolve()
    output = args.output.expanduser().resolve()
    max_tokens = max(16, min(1024, int(args.max_tokens)))
    temperature = max(0.0, min(1.5, float(args.temperature)))

    manifest_path = bundle / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"MLX bundle manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile = dict(manifest.get("profile") or {})
    model_name = str(profile.get("model") or "").strip()
    if not model_name:
        raise SystemExit("MLX bundle does not identify the exact base model.")

    suite = MaryEvaluationSet.from_environment(root=root)
    if suite.load_errors:
        raise SystemExit("MaryBench could not load: " + "; ".join(suite.load_errors))
    if not suite.cases:
        raise SystemExit("No MaryBench cases are configured.")

    cases = list(suite.cases)
    if args.max_cases > 0:
        cases = cases[: max(1, min(len(cases), int(args.max_cases)))]

    adapter_path: str | None = None
    artifact_fingerprint = ""
    candidate_id = ""
    if args.variant == "adapter":
        proposal = build_mlx_adapter_candidate_proposal(bundle)
        candidate_id = proposal.candidate_id
        artifact_fingerprint = ModelFingerprint.from_proposal(proposal)
        adapter_path = str(bundle / "adapter")

    try:
        from mlx_lm import load
    except ImportError as exc:
        raise SystemExit(
            "mlx_lm is required on the local Mac experiment host."
        ) from exc

    if adapter_path:
        model, tokenizer = load(model_name, adapter_path=adapter_path)
    else:
        model, tokenizer = load(model_name)

    benchmark_fingerprint = _benchmark_fingerprint(
        suite_fingerprint=suite.fingerprint,
        case_ids=[case.case_id for case in cases],
        max_tokens=max_tokens,
        temperature=temperature,
    )

    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        rendered = _render_prompt(tokenizer, case.prompt)
        started = monotonic()
        response = _generate(
            model,
            tokenizer,
            rendered,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        latency_ms = round((monotonic() - started) * 1000.0, 2)
        deterministic = suite.evaluate(case, response)
        results.append({
            "case_id": case.case_id,
            "category": case.category,
            "expected_labels": list(case.expected_labels),
            "response": response[:32000],
            "passed": deterministic.passed,
            "failures": list(deterministic.failures),
            "checks": deterministic.checks,
            "latency_ms": latency_ms,
        })
        print(
            f"[{index:02d}/{len(cases):02d}] {case.case_id}: "
            f"{'PASS' if deterministic.passed else 'CHECK'} {latency_ms:.0f} ms"
        )

    report = {
        "version": "marybench-mlx-local-run-v1",
        "variant": args.variant,
        "model": model_name,
        "candidate_id": candidate_id,
        "artifact_fingerprint": artifact_fingerprint,
        "dataset_fingerprint": str(
            manifest.get("dataset_fingerprint")
            or dict(manifest.get("mary_dataset") or {}).get("fingerprint")
            or ""
        ),
        "evaluation_fingerprint": suite.fingerprint,
        "benchmark_fingerprint": benchmark_fingerprint,
        "case_count": len(cases),
        "generation": {
            "system_prompt_version": SYSTEM_PROMPT_VERSION,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        "summary": summarize_marybench_results(results),
        "results": results,
        "boundaries": {
            "local_review_artifact": True,
            "contains_held_out_generated_responses": True,
            "canonical_lineage_payload": False,
            "deterministic_checks_are_semantic_scores": False,
            "benchmark_registered": False,
            "core_sync_performed": False,
            "promotion_performed": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("=" * 64)
    print(f"variant:      {args.variant}")
    print(f"cases:        {len(cases)}")
    print(f"MaryBench:    {benchmark_fingerprint}")
    print(f"pass rate:    {report['summary']['deterministic_pass_rate']:.1%}")
    print(f"output:       {output}")
    print(
        "Deterministic checks are guardrails only. Review base vs adapter and "
        "supply semantic scores before recording canonical benchmark evidence."
    )
    return 0


class ModelFingerprint:
    @staticmethod
    def from_proposal(proposal: Any) -> str:
        parts = [
            str(getattr(proposal, "adapter_config_sha256", "") or "").strip().lower(),
            str(getattr(proposal, "adapter_weights_sha256", "") or "").strip().lower(),
        ]
        clean = [part for part in parts if part]
        if len(clean) != 2:
            raise ValueError("adapter proposal is missing exact hash evidence")
        return sha256("|".join(clean).encode("utf-8")).hexdigest()[:16]


if __name__ == "__main__":
    raise SystemExit(main())
