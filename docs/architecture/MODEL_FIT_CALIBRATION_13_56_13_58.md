# MaryV2 13.56–13.58 — Model Fit Calibration and Provenance

## Purpose

Mary's fit-aware scheduler must not guess model memory requirements. These revisions provide device-local measurement tooling for configured local-model roles and a bounded provenance guard so an operator-applied fit hint can be invalidated after the measured model/context changes.

This layer is operational only. It does not own Mary identity, memory, relationship state, permissions, provider policy, or model selection.

## 13.56 — Cold-load measurement

`scripts.calibrate_model_fit` reuses Mary's synthetic local-LLM benchmark and `mary.distributed.resource_calibration` to observe accelerator-memory change around one benchmark run.

For Ollama, a recommendation is produced only when `/api/ps` proves the target model transitioned from not loaded to loaded. An already-resident model, unavailable residency proof, missing resource observation, or non-positive observed delta produces no recommendation. llama.cpp observations may be recorded, but no residency-based recommendation is claimed without a portable residency proof.

The artifact is disposable operational evidence. It retains no prompt or model response and never edits `.env` automatically.

## 13.57 — Production role calibration

Calibration supports the same device roles used by capability-node execution:

- `general`
- `conversation`
- `fast`
- `utility`

Ollama calibration resolves the role through the existing device role-to-model policy rather than maintaining a second mapping. A successful measurement recommends only the matching fixed fit variable, such as `MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_CONVERSATION`.

A recommendation is scoped to the measured runtime, role, exact model, and `num_ctx`. It is a measurement-supported starting value, not a mathematical guarantee of every future prompt's peak allocation.

## 13.58 — Stale-hint provenance guard

A successful calibration now also emits a short deterministic provenance token derived from:

- runtime;
- role;
- exact configured model name;
- configured context size.

The companion variable is role-specific, for example:

`MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_CONVERSATION_PROVENANCE=<token>`

The operator may explicitly apply the fit value and provenance token together. At node registration, `mary.distributed.resource_requirements` recomputes the expected token from the node's current production role configuration.

Behavior is deliberately compatibility-preserving and fail-safe:

- no provenance variable: legacy explicit fit hint remains valid;
- matching provenance: fit hint is advertised normally;
- mismatched or malformed provenance: only that role's fit hint is suppressed;
- changing a different role does not invalidate unrelated role hints;
- suppressed hints fall back to existing unknown-fit routing rather than inventing a requirement;
- nothing automatically rewrites `.env` or changes the selected model.

This prevents a measured 1.7B-model requirement from silently surviving after that role is changed to a different model/context while preserving existing operator configuration made before 13.58.

## Operator workflow

1. Put the desired production model/context configuration in place.
2. Ensure the target Ollama model is genuinely cold/not resident.
3. Run `python -m scripts.calibrate_model_fit --runtime ollama --role <role>`.
4. If the tool reports a measurement-supported recommendation, copy both the suggested fit value and provenance setting into device-local configuration.
5. Restart/re-register the capability node.
6. Rerun calibration after changing that role's model or context size.

Calibration never grants a capability, permission, trust, liveness, or Core authority. It only supplies bounded scheduling evidence to an already-eligible capability node.
