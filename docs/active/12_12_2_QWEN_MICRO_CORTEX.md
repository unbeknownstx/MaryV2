# Qwen Micro-Cortex benchmark (12.12.2)

Status: benchmark only. No model is selected, promoted, or connected to Mary's
production routing.

## Experiment boundary

Mary's local systems decide the dialogue act, response intent, required
meanings, grounded facts and provenance, represented stance, relevant context,
delivery target, and response form before a model is called. The immutable
`CompactVerbalizationPlan` gives the model one narrow job:

> Turn this already-decided Mary response plan into natural conversational wording.

The compact v2 prompt omits raw source IDs and evaluator rules. It grants no
access to authoritative state and forbids new identity, memory, preference,
motive, relationship, capability, truth, or state decisions. Raw output is
stored only in the requested developer report for human review.

The benchmark is not imported by production code. It does not instantiate Mary
or call `LLMRouter`, CharacterMind, memory, relationship, agency, developed-self,
or persistence owners. Tests use isolated state roots and verify both state and
routing canaries.

## Running it on Windows

Required comparison:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\benchmark_qwen_micro_cortex_windows.ps1
```

Add the installed non-thinking 4B control explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\benchmark_qwen_micro_cortex_windows.ps1 -IncludeInstructControl
```

Reports are no-clobber by default. Use `-Overwrite` only when intentionally
replacing an exact report path. Cold measurement temporarily unloads only the
requested tags, polls them absent, and restores their initial digest/context
residency best-effort. Unrelated tags are never unloaded.

## Method

The versioned `core_10_v2` suite covers greeting, represented preference,
shared-work recall, playful reaction, disagreement, uncertainty, a factual
reservoir answer, a follow-up question, concern, and ordinary back-and-forth.
Every tag receives identical rendered message content; model templates and
tokenization are correctly not claimed identical.

Settings are `think=false`, temperature `0.2`, seed `424242`, context `1024`,
output ceiling `48`, keep-alive `10m`, and native Ollama NDJSON streaming. Each
tag receives:

1. one separate cold diagnostic;
2. a confirmed unload and empty-prompt preload;
3. ten warm novel prompts used for quality review;
4. ten separately reported exact repeats.

The report preserves raw output, first-content timing, Ollama component timing,
token counts, output length, completion state, runtime allocation, exact model
digests, initial/final residency, source hashes, and a blinded human-review
packet. Deterministic checks are triage only; there is no aggregate character
score or automatic winner.

## Canonical-host measurements

Final run: 2026-08-23, Ollama 0.32.14, Windows/AMD64, Python 3.14.7. Report:
`runtime_reports/qwen-micro-cortex-v2-20260823.json`.

| Metric | qwen3:1.7b | qwen3:4b | qwen3:4b-instruct control |
|---|---:|---:|---:|
| Cold Ollama total | 6,546.66 ms | 14,551.58 ms | 13,128.78 ms |
| Cold load | 5,929.31 ms | 10,373.71 ms | 11,139.41 ms |
| Warm novel client wall, median | 1,307.18 ms | 4,398.42 ms | 2,414.22 ms |
| Warm novel client wall, p95 | 1,729.85 ms | 4,502.84 ms | 3,155.31 ms |
| Warm novel first content, median | 764.59 ms | 1,936.11 ms | 1,950.91 ms |
| Warm novel prompt evaluation, median | 515.68 ms | 1,676.93 ms | 1,663.69 ms |
| Warm novel generation, median | 563.91 ms | 2,462.15 ms | 632.24 ms |
| Warm generated tokens, median | 16.5 | 48 | 13 |
| Warm generation rate, median | 28.92 tok/s | 19.49 tok/s | 20.56 tok/s |
| Exact-repeat client wall, median | 910.57 ms | 2,811.94 ms | 1,152.51 ms |
| Complete novel outputs | 10/10 | 0/10 | 10/10 |
| Effective thinking-disabled behavior | 10/10 | 0/10 | 10/10 |
| Fact-fidelity triage | 5/10 | 0/10 | 8/10 |
| Stance triage | 2/3 | 0/3 | 2/3 |
| Naturalness triage | 8/10 | 0/10 | 9/10 |

IPv4 loopback removed the old `localhost` IPv6-fallback artifact: median
client-wall minus Ollama-total overhead was about 4.6-4.9 ms. Exact-repeat
results are cache-favorable and are not mixed into the novel-prompt medians.

Ollama `/api/ps` reported the full 1,342,932,253-byte 1.7B allocation in VRAM.
For both 4B tags it reported 2,534,953,450 of 2,750,217,981 bytes in VRAM. These
are allocation values, not proof of definitive CPU/GPU compute placement, so no
GPU model or compute split is guessed.

## Human sample review

Representative 1.7B successes:

- Concern: “I'm sorry you're feeling exhausted. Take a moment to rest and recharge.”
- Ordinary reply: “I agree—the compact plan feels cleaner. Local systems keep the decisions, while the model handles wording only.”

Representative 1.7B failures:

- Shared recall: “Mary and the creator have been working together...” uses third-person planner language instead of speaking as Mary.
- Disagreement: “Mary opposes...” preserves the stance but does not perform the decided dialogue act as Mary.
- Factual answer omits that the reservoir is derived and rebuildable.
- Follow-up recites “The user reports...” and violates the one-sentence/20-word form.
- Preference output describes a style but does not clearly own the represented preference.

The exact `qwen3:4b` tag replayed prompt fields in all ten novel cases and hit the
48-token ceiling every time. For example:

> We are given: TURN: "hey mary" DIALOGUE: act=greet; drive=acknowledge...

Its installed template forces an open thinking block. The exact-tag comparison
is valid evidence of incompatibility, but it cannot supply the intended
thinking-disabled Mary-like quality baseline.

The explicit `qwen3:4b-instruct` control produced several clean responses:

- “Was the slowness due to loading or response generation?”
- “We've been working on MaryV2 12.12.2 natural-conversation calibration.”

It still failed the represented-preference case with “That's all I ever
wanted,” inventing an enduring personal desire, and omitted the reservoir's
derived/cache status. It is a useful control, not a substitute or promotion.

## Finding and risks

`qwen3:1.7b` is useful as a fast experimental verbalizer: on this host its warm
novel median and p95 both met the two-second full-response target, it stayed in
thinking-disabled mode, and it introduced no unsupported memories, capabilities,
or tool calls. It is not reliable enough to promote. Only about half the fixed
cases passed strict fact/stance/form triage; its dominant failures were planner
recitation, third-person perspective, omitted meaning, and form drift.

Additional risks:

- one cold observation per tag is diagnostic, not a distribution;
- one fixed host/order cannot exclude thermal or background-load effects;
- 1.7B throughput varied materially between validation runs, so token rate
  should not be treated as a stable hardware constant;
- first content can still become an unusable answer, as exact 4B demonstrates;
- exact-repeat cache misses occurred, so repeat medians need their p95 context;
- live residency restoration was verified from empty to empty; restoration of
  an initially resident requested tag is covered by tests but not this live run;
- automatic rules cannot replace human semantic and character review.

No model was ranked, promoted, or connected to production routing.

## Verification

- Focused benchmark/boundary suite: **156 passed**.
- `scripts/test_fast.ps1`: **13 + 174 + 24 passed**; both deterministic
  verifiers and frontend syntax passed.
- `scripts/test_release.ps1`: **896 passed, 1 skipped**; compile, diagnostics,
  routing guarantees, persistence/state integrity, release hygiene, standalone
  readiness, and local tool safety all passed.

Pytest emitted one non-failing warning because the existing `.pytest_cache`
path is unusable. All test and verifier state used fresh isolated roots; live
persistent Mary data, `.env`, API keys, user state, and network voice synthesis
were untouched.
