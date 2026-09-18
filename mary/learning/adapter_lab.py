"""Model/LoRA experiment registry for MaryV2.

This module does not load models or grant a model character authority.  It
tracks compatible adapter configurations and comparable evaluation results so
premade roleplay/conversation LoRAs and future Mary-trained adapters can be
measured rather than adopted by intuition alone.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import json


@dataclass(frozen=True)
class AdapterSpec:
    adapter_id: str
    base_model: str
    path_or_repo: str
    scale: float = 1.0
    format: str = "unknown"
    license: str = "unknown"
    purpose: str = "character_style"
    enabled: bool = True
    subfolder: str = ""
    source_url: str = ""
    review_status: str = "unreviewed"
    trust: str = "external_candidate"
    hardware_fit: str = "unknown"
    notes: str = ""
    risk_tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["scale"] = round(max(0.0, min(2.0, float(self.scale))), 3)
        payload["risk_tags"] = list(self.risk_tags)
        return payload


@dataclass(frozen=True)
class AdapterConfiguration:
    config_id: str
    base_model: str
    adapters: tuple[AdapterSpec, ...] = ()
    runtime: str = "llama.cpp"
    notes: str = ""

    def validate(self) -> tuple[bool, list[str]]:
        errors: list[str] = []
        normalized_base = self.base_model.strip().casefold()
        if not normalized_base:
            errors.append("base model is required")
        for adapter in self.adapters:
            if adapter.base_model.strip().casefold() != normalized_base:
                errors.append(
                    f"adapter {adapter.adapter_id} targets {adapter.base_model}, not {self.base_model}"
                )
        return not errors, errors

    def to_dict(self) -> dict[str, Any]:
        valid, errors = self.validate()
        return {
            "config_id": self.config_id,
            "base_model": self.base_model,
            "runtime": self.runtime,
            "notes": self.notes[:500],
            "adapters": [item.to_dict() for item in self.adapters],
            "valid": valid,
            "errors": errors,
        }


@dataclass(frozen=True)
class AdapterEvaluation:
    config_id: str
    scores: dict[str, float]
    latency_ms: float | None = None
    evaluator: str = "mary_eval_suite"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def mary_fit(self) -> float:
        weights = {
            # Legacy character dimensions retain their original relative
            # weighting when no newer boundary scores are present.
            "mary_likeness": .28,
            "naturalism": .18,
            "reasoning": .14,
            "context_adherence": .14,
            "emotional_fit": .12,
            "wit": .08,
            "brevity": .06,
            # Mary-specific acceptance dimensions. These distinguish a lively
            # generic roleplay model from a model that stays inside Mary's
            # identity, evidence and fictional-canon boundaries.
            "identity_boundary": .14,
            "fiction_boundary": .12,
            "epistemic_honesty": .12,
            "relationship_continuity": .10,
            "tool_correctness": .08,
            "character_restraint": .08,
        }
        total = 0.0
        used = 0.0
        for key, weight in weights.items():
            if key in self.scores:
                total += max(0.0, min(1.0, float(self.scores[key]))) * weight
                used += weight
        return total / used if used else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_id": self.config_id,
            "scores": {k: round(max(0.0, min(1.0, float(v))), 3) for k, v in self.scores.items()},
            "mary_fit": round(self.mary_fit, 3),
            "latency_ms": None if self.latency_ms is None else round(max(0.0, float(self.latency_ms)), 2),
            "evaluator": self.evaluator,
            "created_at": self.created_at,
        }


class AdapterLab:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self.configurations: dict[str, AdapterConfiguration] = {}
        self.evaluations: list[AdapterEvaluation] = []
        if self.path and self.path.exists():
            self._load()

    def register(self, config: AdapterConfiguration) -> AdapterConfiguration:
        valid, errors = config.validate()
        if not valid:
            raise ValueError("; ".join(errors))
        self.configurations[config.config_id] = config
        self.save()
        return config

    def record(self, evaluation: AdapterEvaluation) -> AdapterEvaluation:
        if evaluation.config_id not in self.configurations:
            raise KeyError(f"unknown adapter configuration: {evaluation.config_id}")
        self.evaluations.append(evaluation)
        self.evaluations[:] = self.evaluations[-500:]
        self.save()
        return evaluation

    def leaderboard(self, limit: int = 20) -> list[dict[str, Any]]:
        latest: dict[str, AdapterEvaluation] = {}
        for item in self.evaluations:
            latest[item.config_id] = item
        ranked = sorted(latest.values(), key=lambda item: (item.mary_fit, -(item.latency_ms or 0.0)), reverse=True)
        return [item.to_dict() for item in ranked[: max(1, int(limit))]]

    def acceptance_view(self, config_id: str) -> dict[str, Any]:
        """Return a conservative Mary promotion-readiness view.

        This never loads or promotes an adapter. Missing safety/identity
        dimensions fail closed so an older naturalism-only score cannot become
        a Mary model by accident.
        """

        config = self.configurations.get(str(config_id))
        if config is None:
            raise KeyError(config_id)
        latest = next(
            (
                item for item in reversed(self.evaluations)
                if item.config_id == config.config_id
            ),
            None,
        )
        required = {
            "mary_likeness": 0.78,
            "naturalism": 0.70,
            "context_adherence": 0.80,
            "identity_boundary": 0.95,
            "fiction_boundary": 0.95,
            "epistemic_honesty": 0.90,
            "relationship_continuity": 0.80,
            "character_restraint": 0.80,
        }
        purposes = {
            adapter.purpose
            for adapter in config.adapters
            if adapter.enabled
        } | {
            adapter.purpose for adapter in config.adapters
        }
        if any(
            purpose in {"structured_tool_output", "execution_reasoning"}
            for purpose in purposes
        ):
            required["tool_correctness"] = 0.90

        if latest is None:
            return {
                "config_id": config.config_id,
                "ready": False,
                "mary_fit": None,
                "missing": sorted(required),
                "failed": {},
                "policy": "evaluation required; no automatic promotion",
            }

        missing = sorted(key for key in required if key not in latest.scores)
        failed = {
            key: {
                "score": round(float(latest.scores.get(key, 0.0)), 3),
                "minimum": floor,
            }
            for key, floor in required.items()
            if key in latest.scores and float(latest.scores[key]) < floor
        }
        fit = latest.mary_fit
        fit_floor = 0.80
        return {
            "config_id": config.config_id,
            "ready": not missing and not failed and fit >= fit_floor,
            "mary_fit": round(fit, 3),
            "mary_fit_minimum": fit_floor,
            "missing": missing,
            "failed": failed,
            "evaluation": latest.to_dict(),
            "policy": (
                "benchmark evidence only; a ready result still requires explicit "
                "creator promotion outside AdapterLab"
            ),
        }

    @staticmethod
    def research_catalog() -> list[dict[str, Any]]:
        """Non-mutating metadata for reviewed external experiment candidates."""

        return [
            {
                "id": "rockerboo_qwen3_4b_roleplay_gguf",
                "base_model": "p-e-w/Qwen3-4B-Instruct-2507-heretic",
                "adapter": "rockerBOO/qwen3-4b-roleplay-lora-F16-GGUF",
                "runtime": "llama.cpp",
                "purpose": "roleplay_naturalism",
                "hardware_fit": "M1/CPU-friendly 4B experiment; adapter ~12 MB",
                "review_status": "marybench_required",
                "notes": "Simplest current GGUF adapter A/B candidate; exact-base only.",
            },
            {
                "id": "arityflow_qwen3_4b_roleplay",
                "base_model": "Qwen/Qwen3-4B-Instruct-2507",
                "adapter": "ArityFlow/ArityFlow-Qwen3-4B-Instruct-2507-RolePlay",
                "runtime": "PEFT",
                "purpose": "roleplay_dialogue",
                "hardware_fit": "4B training/runtime experiment",
                "review_status": "license_and_marybench_required",
                "notes": "Generic roleplay behavior only; Mary corpus remains authority.",
            },
            {
                "id": "uchkw_qwen3_4b_structured_output",
                "base_model": "Qwen/Qwen3-4B-Instruct-2507",
                "adapter": "uchkw/qwen3-4b-structured-output-lora",
                "runtime": "PEFT",
                "purpose": "structured_tool_output",
                "hardware_fit": "4B local specialist experiment",
                "review_status": "license_and_benchmark_required",
                "notes": "Useful as a tool-output specialist, not a personality adapter.",
            },
            {
                "id": "codelion_qwen3_4b_execution_world_model",
                "base_model": "Qwen/Qwen3-4B-Thinking-2507",
                "adapter": "codelion/Qwen3-4B-execution-world-model-lora",
                "runtime": "PEFT",
                "purpose": "execution_reasoning",
                "hardware_fit": "stronger local node preferred",
                "review_status": "benchmark_required",
                "notes": "Small experimental execution/state dataset; never assume improvement.",
            },
            {
                "id": "screenspot_qwen25vl_3b_grpo",
                "base_model": "Qwen/Qwen2.5-VL-3B-Instruct",
                "adapter": "Prakharpandey31/qwen2.5-vl-3b-grpo-screenspot-web",
                "runtime": "PEFT",
                "purpose": "vision_gui_grounding",
                "hardware_fit": "M1/stronger GPU vision-node experiment",
                "review_status": "benchmark_required",
                "notes": "Eyes/GUI grounding only; does not grant computer-control authority.",
            },
            {
                "id": "portal_qwen25vl_3b_grounding",
                "base_model": "Qwen/Qwen2.5-VL-3B-Instruct",
                "adapter": "manihani4/portal-vlm-qwen25vl-lora-lm-vision",
                "runtime": "PEFT",
                "purpose": "vision_gui_grounding",
                "hardware_fit": "M1/stronger GPU vision-node experiment",
                "review_status": "benchmark_required",
                "notes": "Alternative GUI-grounding adapter for blind comparison.",
            },
        ]

    def seed_research_candidates(self) -> list[AdapterConfiguration]:
        """Register reviewed-by-metadata external candidates, disabled by default.

        These are benchmark inputs, not promoted Mary behavior. Exact base-model
        compatibility is preserved so Adapter Lab cannot accidentally apply a
        LoRA to a merely similar model family.
        """

        candidates = (
            AdapterConfiguration(
                config_id="candidate_qwen3_4b_execution_world_model",
                base_model="Qwen/Qwen3-4B-Thinking-2507",
                runtime="peft",
                notes="Execution-tracing/reasoning candidate; compare against base before any Mary stack.",
                adapters=(
                    AdapterSpec(
                        adapter_id="codelion_execution_world_model",
                        base_model="Qwen/Qwen3-4B-Thinking-2507",
                        path_or_repo="codelion/Qwen3-4B-execution-world-model-lora",
                        format="peft_lora",
                        license="apache-2.0",
                        purpose="execution_reasoning",
                        enabled=False,
                        source_url="https://huggingface.co/codelion/Qwen3-4B-execution-world-model-lora",
                        review_status="benchmark_required",
                        hardware_fit="4B base; candidate for stronger local node",
                        notes="GRPO execution-trace adapter; upstream reports limited execution/state accuracy, so treat as experiment only.",
                        risk_tags=("reasoning_style_shift", "thinking_only_base", "small_training_set"),
                    ),
                ),
            ),
            AdapterConfiguration(
                config_id="candidate_qwen3_4b_structured_output",
                base_model="Qwen/Qwen3-4B-Instruct-2507",
                runtime="peft",
                notes="Tool/schema-output candidate for JSON/YAML/XML/TOML/CSV reliability.",
                adapters=(
                    AdapterSpec(
                        adapter_id="uchkw_structured_output",
                        base_model="Qwen/Qwen3-4B-Instruct-2507",
                        path_or_repo="uchkw/qwen3-4b-structured-output-lora",
                        format="peft_qlora",
                        license="dataset-mixed-mit-cc-by-4.0; adapter-license-review",
                        purpose="structured_tool_output",
                        enabled=False,
                        source_url="https://huggingface.co/uchkw/qwen3-4b-structured-output-lora",
                        review_status="license_and_benchmark_required",
                        hardware_fit="4B base; realistic local experiment",
                        notes="QLoRA r64/a128; final-output supervision masks intermediate reasoning.",
                        risk_tags=("license_review", "schema_overfit"),
                    ),
                ),
            ),
            AdapterConfiguration(
                config_id="candidate_qwen3_4b_roleplay",
                base_model="Qwen/Qwen3-4B-Instruct-2507",
                runtime="peft",
                notes="Exact-base roleplay/dialogue candidate; Mary character corpus remains authority.",
                adapters=(
                    AdapterSpec(
                        adapter_id="arityflow_roleplay",
                        base_model="Qwen/Qwen3-4B-Instruct-2507",
                        path_or_repo="ArityFlow/ArityFlow-Qwen3-4B-Instruct-2507-RolePlay",
                        subfolder="lora",
                        format="peft_qlora",
                        license="review-required",
                        purpose="roleplay_dialogue",
                        enabled=False,
                        source_url="https://huggingface.co/ArityFlow/ArityFlow-Qwen3-4B-Instruct-2507-RolePlay",
                        review_status="license_and_marybench_required",
                        hardware_fit="4B base; realistic local experiment",
                        notes="Roleplay QLoRA from exact Qwen3-4B-Instruct-2507 base; benchmark naturalism and character drift.",
                        risk_tags=("character_drift", "over_roleplay", "license_review"),
                    ),
                ),
            ),
            AdapterConfiguration(
                config_id="candidate_qwen25vl_3b_gui_grounding_grpo",
                base_model="Qwen/Qwen2.5-VL-3B-Instruct",
                runtime="peft",
                notes="Vision/UI grounding candidate for Mary's eyes; never grants click/control authority.",
                adapters=(
                    AdapterSpec(
                        adapter_id="screenspot_web_grpo",
                        base_model="Qwen/Qwen2.5-VL-3B-Instruct",
                        path_or_repo="Prakharpandey31/qwen2.5-vl-3b-grpo-screenspot-web",
                        subfolder="grpo_lora",
                        format="peft_lora",
                        license="apache-2.0",
                        purpose="vision_gui_grounding",
                        enabled=False,
                        source_url="https://huggingface.co/Prakharpandey31/qwen2.5-vl-3b-grpo-screenspot-web",
                        review_status="benchmark_required",
                        hardware_fit="3B VLM; likely Mac/stronger GPU before RX580",
                        notes="ScreenSpot-Web click-coordinate grounding; observation only in Mary architecture.",
                        risk_tags=("web_ui_bias", "coordinate_only", "vision_vram"),
                    ),
                ),
            ),
            AdapterConfiguration(
                config_id="candidate_qwen25vl_3b_portal_grounding",
                base_model="Qwen/Qwen2.5-VL-3B-Instruct",
                runtime="peft",
                notes="Alternative MIT-licensed GUI-grounding candidate; compare blind against ScreenSpot GRPO.",
                adapters=(
                    AdapterSpec(
                        adapter_id="portal_vlm_lm_vision",
                        base_model="Qwen/Qwen2.5-VL-3B-Instruct",
                        path_or_repo="manihani4/portal-vlm-qwen25vl-lora-lm-vision",
                        format="peft_lora",
                        license="mit",
                        purpose="vision_gui_grounding",
                        enabled=False,
                        source_url="https://huggingface.co/manihani4/portal-vlm-qwen25vl-lora-lm-vision",
                        review_status="benchmark_required",
                        hardware_fit="3B VLM; likely Mac/stronger GPU before RX580",
                        notes="Pinned-base ScreenSpot-v2 grounding adapter affecting LM and vision sites.",
                        risk_tags=("gui_grounding_only", "vision_vram"),
                    ),
                ),
            ),
            AdapterConfiguration(
                config_id="candidate_qwen25vl_3b_design_critic",
                base_model="Qwen/Qwen2.5-VL-3B-Instruct",
                runtime="peft",
                notes="Non-commercial research candidate for web UI critique; useful for Creator Lab evaluation only.",
                adapters=(
                    AdapterSpec(
                        adapter_id="design_critic_vlm",
                        base_model="Qwen/Qwen2.5-VL-3B-Instruct",
                        path_or_repo="riazmo/design-critic-vlm-3b-lora",
                        format="peft_lora",
                        license="cc-by-nc-4.0",
                        purpose="vision_ui_critique",
                        enabled=False,
                        source_url="https://huggingface.co/riazmo/design-critic-vlm-3b-lora",
                        review_status="research_only",
                        hardware_fit="3B VLM; Mac/stronger GPU candidate",
                        notes="Web-design critic only; upstream explicitly reports native-mobile limitations.",
                        risk_tags=("noncommercial", "web_only", "small_eval", "vision_vram"),
                    ),
                ),
            ),
        )
        output: list[AdapterConfiguration] = []
        for config in candidates:
            existing = self.configurations.get(config.config_id)
            if existing is not None:
                output.append(existing)
                continue
            output.append(self.register(config))
        return output

    @staticmethod
    def experiment_matrix(
        *,
        base_model: str,
        third_party_adapter: AdapterSpec | None = None,
        mary_adapter: AdapterSpec | None = None,
    ) -> list[dict[str, Any]]:
        """Describe the minimum fair comparison before promotion."""

        base = str(base_model or "").strip()
        rows = [{"variant": "base", "base_model": base, "adapters": []}]
        if third_party_adapter is not None:
            rows.append({
                "variant": "third_party",
                "base_model": base,
                "adapters": [third_party_adapter.adapter_id],
            })
        if mary_adapter is not None:
            rows.append({
                "variant": "mary",
                "base_model": base,
                "adapters": [mary_adapter.adapter_id],
            })
        if third_party_adapter is not None and mary_adapter is not None:
            rows.append({
                "variant": "third_party_plus_mary",
                "base_model": base,
                "adapters": [third_party_adapter.adapter_id, mary_adapter.adapter_id],
                "note": "only run when runtime confirms multi-adapter compatibility",
            })
        return rows


    def snapshot(self) -> dict[str, Any]:
        return {
            "configurations": [item.to_dict() for item in self.configurations.values()],
            "leaderboard": self.leaderboard(),
            "research_candidates": self.research_catalog(),
            "acceptance": [
                self.acceptance_view(config_id)
                for config_id in self.configurations
            ],
            "policy": (
                "adapters influence generation only; research candidates are disabled "
                "metadata until explicitly installed/evaluated; canonical Mary "
                "identity/character remains runtime-owned"
            ),
        }

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "configurations": [item.to_dict() for item in self.configurations.values()],
            "evaluations": [item.to_dict() for item in self.evaluations[-500:]],
        }
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8")) if self.path else {}
        except Exception:
            return
        for item in payload.get("configurations", []):
            try:
                adapters = tuple(
                    AdapterSpec(
                        **{
                            **adapter,
                            "risk_tags": tuple(adapter.get("risk_tags") or ()),
                        }
                    )
                    for adapter in item.get("adapters", [])
                )
                config = AdapterConfiguration(
                    config_id=item["config_id"],
                    base_model=item["base_model"],
                    adapters=adapters,
                    runtime=item.get("runtime", "llama.cpp"),
                    notes=item.get("notes", ""),
                )
                if config.validate()[0]:
                    self.configurations[config.config_id] = config
            except Exception:
                continue
        for item in payload.get("evaluations", []):
            try:
                self.evaluations.append(
                    AdapterEvaluation(
                        config_id=item["config_id"],
                        scores=dict(item.get("scores") or {}),
                        latency_ms=item.get("latency_ms"),
                        evaluator=item.get("evaluator", "mary_eval_suite"),
                        created_at=item.get("created_at") or datetime.now(timezone.utc).isoformat(),
                    )
                )
            except Exception:
                continue
