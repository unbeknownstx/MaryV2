# Qwen Micro-Cortex benchmark (12.12.2)

Status: benchmark only. No model is selected, promoted, or connected to Mary's
production routing.

## Experiment boundary

Mary's local systems decide the dialogue act, response intent, required
meanings, grounded facts and provenance, represented stance, relevant context,
delivery target, and response form before a model is called. The immutable
`CompactVerbalizationPlan` remains evaluator/internal context and gives the
model one narrow job:

> Turn this already-decided Mary response plan into natural conversational wording.

The compact v2 prompt omits raw source IDs and evaluator rules. V3 goes further:
`SemanticSurfaceContract` projects only `speaker`, `mode`, `form`, sentence and
word ceilings, required speaker-relative meanings, and an optional exact
question count. It removes the original turn, dialogue-act/intent/drive names,
facts/stance metadata, relationship hints, provenance, authority, confidence,
delivery scalars, and identity labels such as Mary/user/creator. Necessary
project names or factual entities may remain inside a selected semantic unit.

Neither version grants access to authoritative state. Both forbid new identity,
memory, preference, motive, relationship, capability, truth, or state decisions.
Raw output is stored only in the requested developer report for human review.

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

Run the strict V3 surface-realizer comparison with the exact requested pair:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\benchmark_qwen_surface_realizer_v3_windows.ps1 -WarmRuns 2 -Report .\runtime_reports\qwen-surface-realizer-v3-<timestamp>.json
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

## Semantic Surface Realizer V3

V3 keeps the original ten categories and adds eight adversarial cases for
third-person reference, question-form drift, disagreement, uncertainty,
fact-bounded warmth, exact factual recall, refusal to embellish, and pronoun
handling. Both tags receive identical rendered message content. Settings remain
`think=false`, temperature `0.2`, seed `424242`, context `1024`, output ceiling
`48`, keep-alive `10m`, and Ollama streaming.

The deterministic verifier uses evaluator-only semantic patterns and explicit
reference relations. It checks required meaning, stance, form, sentence/word
ceilings, role/planner leakage, assistant framing, unexpected entities/numbers,
unsupported causes, first-person personal claims, and obvious embellishment.
Ordinary sentence-initial capitalization is not treated as a proper noun by
itself. One optional repair pass may only remove wrappers/labels or restore
unambiguous question punctuation; it cannot add meaning, rewrite facts, change
referents, or soften stance. Anything else is rejected.

Validated run: 2026-08-23, Ollama 0.32.14, Windows/AMD64, Python 3.14.7. Report:
`runtime_reports/qwen-surface-realizer-v3-20260823-validated.json`.

| Metric | qwen3:1.7b | qwen3:4b-instruct |
|---|---:|---:|
| Cold Ollama total | 6,916.01 ms | 11,260.94 ms |
| Cold load | 6,533.79 ms | 10,301.43 ms |
| Cold first content | 6,819.67 ms | 11,024.54 ms |
| Warm first content, p50 / p95 | 449.24 / 497.18 ms | 781.54 / 820.93 ms |
| Warm full client response, p50 / p95 | 821.37 / 1,216.81 ms | 1,699.10 / 2,619.84 ms |
| Verified-ready, p50 / p95 | 821.58 / 1,217.12 ms | 1,699.31 / 2,620.17 ms |
| Prompt evaluation, p50 / p95 | 208.82 / 263.68 ms | 505.22 / 543.67 ms |
| Generation, p50 / p95 | 360.58 / 774.78 ms | 915.73 / 1,862.57 ms |
| Generated tokens, p50 / p95 | 12.0 / 24.6 | 12.5 / 24.3 |
| Generation rate, p50 / p95 | 33.28 / 36.74 tok/s | 13.65 / 14.13 tok/s |
| Response median, chars / words / sentences | 50 / 10 / 1 | 51 / 9 / 1.5 |

| V3 boundary result | qwen3:1.7b | qwen3:4b-instruct |
|---|---:|---:|
| Strict semantic fidelity | 8/18 (44.44%) | 9/18 (50.00%) |
| Stance fidelity where represented | 3/4 (75.00%) | 2/4 (50.00%) |
| Question/statement form fidelity | 18/18 (100%) | 16/18 (88.89%) |
| Third-person/planner leakage | 1/18 | 0/18 |
| Unsupported personal claims | 4/18 | 1/18 |
| Unsupported additions | 7/18 | 3/18 |
| Post-verifier accepted | 8/18 (44.44%) | 9/18 (50.00%) |
| Post-verifier rejected | 10/18 (55.56%) | 9/18 (50.00%) |
| Repair attempted / accepted | 0 / 0 | 0 / 0 |

The 1.7B p95 full-response target was met, and its form fidelity reached 100%.
It missed every quality target: strict fidelity, stance, combined
third-person/planner leakage, and unsupported personal claims. The single
leakage was instruction replay (`/No_think`), not a Mary/user/creator noun;
literal third-person role-label leakage was zero. The 4B control missed the
two-second p95 target as well as fidelity/form/personal-claim targets.

Compared on the original ten categories only, V3 gave 1.7B 5/10 strict
acceptance, 3/3 stance fidelity, 10/10 form fidelity, and zero role/planner
leaks. That is a clear perspective/form/stance improvement over V2's observed
third-person/planner failures and 2/3 stance triage, but not an improvement in
the 5/10 overall fidelity yield. The adversarial cases exposed the remaining
weakness sharply.

Representative accepted samples:

- 1.7B greeting: “Hi there! Want to chat more?”
- 1.7B exact reference: “I sent you the draft after you asked for it.”
- 1.7B bounded fact: “The process exited with code 2, and the cause is unknown.”
- 4B disagreement: “I don't agree with dramatic replies. Normal ones should be simple and calm.”
- 4B uncertainty: “I don't know if the installed tag supports thinking disabled.”
- 4B playful reaction: “One comma—bug solved! 😄”

Representative rejected samples:

- 1.7B changed the addressee's state into an unsupported speaker state:
  “I'm really tired, let me take a pause and rest.”
- 1.7B exact recall returned only “/temperature 0.2/”, dropping context and
  output-ceiling facts.
- 1.7B returned “/No_think” for uncertainty, replaying an instruction and
  dropping every required meaning.
- 1.7B preserved the preference stance but added a reason: “It's more
  comfortable for me.”
- 4B changed `your headache` to “My headache feels rough today.”
- 4B changed first-content-versus-generation timing into “before or after my
  first response,” dropping both required stage meanings.
- 4B said “I sent you the draft as asked,” dropping `after` and the explicit
  second-person request relation.
- 4B's known-preference reply added an unsupplied walking-down-the-street
  comparison and used three sentences against the two-sentence ceiling.

The safe repair path neither helped nor hurt this live matrix: no output had a
format-only defect that was eligible for repair. This is desirable for these
failures; a deterministic rewrite would have needed to invent missing meaning
or change referents. Focused tests separately prove the one-pass label/terminal
punctuation repair and full re-verification behavior.

Ollama `/api/ps` reported all 1,342,932,253 allocated bytes for 1.7B in VRAM and
2,534,953,450 of 2,750,217,981 bytes (92.17%) for 4B-instruct. Those are raw
allocation values, not proof of actual CPU/GPU compute placement, and the report
does not guess beyond them. Initially resident 4B-instruct digest/context
residency was restored exactly after the cold measurements.

## Finding and risks

`qwen3:1.7b` remains useful for benchmark-only latency and contract research,
but it is not currently useful as an unguarded Mary verbalizer. Its speed and
perfect V3 form fidelity are promising; its 44.44% strict acceptance, reference
reversals, missing meanings, instruction replay, and unsupported speaker claims
are disqualifying for production. V3 demonstrates that removing identity labels
solves literal third-person-role leakage, but a minimal payload alone does not
make 1.7B a reliable semantic realizer. No model is promoted.

Additional risks:

- one cold observation per tag is diagnostic, not a distribution;
- one fixed host/order cannot exclude thermal or background-load effects;
- 1.7B throughput varied materially between validation runs, so token rate
  should not be treated as a stable hardware constant;
- first content can still become an unusable answer, as exact 4B demonstrates;
- exact-repeat timings are cache-favorable and must stay separate from novel
  prompt p50/p95 values;
- the initially resident 4B-instruct tag was restored exactly in this run, but
  residency restoration remains best-effort if Ollama itself fails;
- automatic rules cannot replace human semantic and character review;
- the 18 novel prompts provide useful p50/p95 triage, not a statistically broad
  latency distribution;
- sentence-initial capitalization alone cannot distinguish a new proper noun,
  so entity detection remains deliberately conservative and human review is
  still required;
- deterministic paraphrase patterns can miss valid unseen wording or fail to
  recognize a novel invention;
- the repair policy is intentionally too weak to rescue substantive omissions,
  referent swaps, or stance flattening;
- 4B-instruct was more fluent but still accepted only half the adversarially
  expanded suite and exceeded the two-second p95 target.

No model was ranked, promoted, or connected to production routing.

## Hybrid dialogue follow-up experiment

The next benchmark-only architecture experiment is documented in
[`12_12_2_HYBRID_DIALOGUE_RUNTIME.md`](12_12_2_HYBRID_DIALOGUE_RUNTIME.md).
It does not retry the universal surface-realizer premise. Instead, a
deterministic authority/risk classifier keeps represented precision semantics
in a typed procedural composer, permits qwen3:1.7b only as an invisible
low-risk social shadow by default, and preserves open/thinking turns for their
existing stronger classes. Production routing remains unchanged and no model
is promoted.

## Verification

- Final focused V3 plan/verifier suite: **171 passed**.
- Full Micro-Cortex focused suite before the final added regressions:
  **211 passed**.
- `scripts/test_fast.ps1`: **13 + 238 + 24 passed**; both deterministic
  verifiers and frontend syntax passed.
- `scripts/test_release.ps1`: **960 passed, 1 skipped**; compile, diagnostics,
  routing guarantees, persistence/state integrity, release hygiene, standalone
  readiness, and local tool safety all passed.
- Validated live execution matrix: **18/18 cases for each model**, no sample
  failures, no completion errors, exact-repeat rate **18/18** for both tags.

All pytest and verifier state used fresh isolated roots. Live persistent Mary
data, `.env`, API keys, user state, production routing/defaults, and network
voice synthesis were untouched.
