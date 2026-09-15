# Prompt Evidence Aging 13.46

MaryV2 13.46 adds **prompt-only aging and selection** for ephemeral orchestration evidence. It does not delete task history and it does not alter canonical memory.

## Why this exists

Long-running task workspaces can accumulate large tool results, web research, verification output, and model suggestions. Keeping every rebuildable result in every later specialist prompt wastes context and can let stale operational evidence overpower newer facts.

Mary already separates ephemeral task work from durable identity/memory. 13.46 extends that separation to the LLM-facing prompt projection.

## Policy

`mary.orchestration.evidence_selection.select_prompt_evidence()` classifies evidence by provenance.

Protected evidence is preferentially retained regardless of age:

- creator evidence;
- persistent-memory evidence;
- relationship-model evidence;
- Mary-runtime evidence.

Rebuildable evidence may age out of the **prompt** after the configured TTL when it is not exceptionally high-confidence/importance:

- local tool output;
- test results;
- web evidence;
- cloud/local model inference evidence.

The default rebuildable TTL is 30 minutes and remains bounded between 30 seconds and 24 hours. High-confidence verification evidence can remain eligible beyond the TTL.

## Wiring

`OrchestrationExecutor._generation_prompt()` no longer takes the last eight task-evidence rows blindly. It calls the selector and serializes only the selected evidence.

The selector telemetry records only task-local opaque evidence IDs and counts:

- selected count;
- omitted count;
- stale count;
- protected count;
- omitted/stale IDs.

No evidence prose is copied into the telemetry record.

## Audit and memory boundaries

TaskWorkspace remains unchanged and keeps the full bounded ephemeral evidence collection. An item omitted from a model prompt is still present for task audit/debugging until normal workspace capacity/eviction policy removes the task.

13.46 does **not**:

- delete evidence because it is old;
- demote or edit durable semantic/episodic memory;
- promote task evidence into durable memory;
- summarize private evidence with another model;
- reintroduce workspace evidence into redact-first prompts.

Redact-first generation continues to use only the explicit redacted request and reports zero selected workspace evidence.

## Architectural result

This creates three clean layers:

1. **Canonical memory/state** — long-lived Mary-owned truth under existing memory governance.
2. **Task workspace** — bounded ephemeral evidence and work history for audit and orchestration.
3. **Prompt projection** — the smallest useful evidence slice sent to a replaceable specialist/model for the current step.

That keeps long tasks efficient without confusing context retention with memory deletion.
