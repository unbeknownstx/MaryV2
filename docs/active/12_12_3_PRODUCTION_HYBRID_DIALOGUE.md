# MaryV2 12.12.3 Production Hybrid Dialogue

Status: production deterministic architecture. No local language model is
promoted by this release.

## Decision path

Mary's existing authoritative system handlers retain precedence for memory,
relationship, capability, runtime, tools, and explicit state-changing intents.
For remaining dialogue, the production path is:

```text
User turn
  -> CharacterMind / existing dialogue policy
  -> immutable CanonicalResponsePlan
  -> deterministic response-risk classification
  -> LocalComposerV2
  -> independent semantic / ownership / form / provenance audit
  -> local response, or the existing cognition/provider route
```

The four classes are `precision_local`, `social_low_risk`,
`open_conversation`, and `thinking_required`. Only the first two are eligible
for deterministic local composition, and only when the full selected meaning
is structurally represented. Missing or unsupported semantics fail closed.

## Authority boundary

`CanonicalResponsePlan` is an immutable, bounded projection of decisions and
state already owned elsewhere. It has no save/load API, no state discovery,
and no authority to create identity, memory, relationship, preferences,
personality, knowledge, capabilities, or project truth. The reservoir remains
a derived cache. Structured record metadata supplies response semantics;
arbitrary reservoir prose is never parsed into a production answer.

The independent local audit checks complete clause coverage, participant and
possessive ownership, represented certainty/stance, response form and length,
source/authority linkage, and unsupported capability or planner language. A
failed projection, composition, or audit returns no invented local wording and
continues through Mary's existing route.

## Natural variation

LocalComposerV2 selects among bounded compositional fragments and clause
forms. `CharacterMind` keeps at most eight recent realized phrases in
process-local memory to reduce exact repetition. This history is cosmetic,
non-authoritative, cleared on close, absent from persistence, and redacted from
diagnostics. Facts, ownership, stance, certainty, form, and dialogue act do not
vary.

## Provider and model boundary

This release does not change `free_first`, the ordinary conversation route,
private/offline Ollama routing, or explicit paid OpenAI expert authorization.
`qwen3:1.7b` remains benchmark/shadow evidence only. Production shadow fields
are reported as disabled; no Qwen candidate is displayed, spoken, persisted,
or allowed to affect Mary's answer or state.

## Observability

The existing ephemeral turn trace now reports response class, response engine,
classification time, local-composer time, local-audit time, escalation reason,
and disabled shadow status. The trace allowlists only diagnostic fields and
does not copy canonical plans, grounded facts, semantic values, slots, or plan
rationale. The desktop shows these fields only in Runtime Diagnostics.

## Isolated production benchmark

Run the real `MaryApplication` path without external or paid calls:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\benchmark_production_hybrid_dialogue_windows.ps1
```

The launcher uses fresh temporary Mary state, a nonexistent dotenv path, an
in-memory reservoir, and an in-process counting provider for routes that must
escalate. It restores the caller's environment and writes only a no-clobber
developer report under `runtime_reports/`.

