# MaryV2 12.12.2 Hybrid Dialogue Runtime

Status: benchmark/shadow experiment only. It is not imported by
`CharacterMind`, the production router, or any presentation path. No model is
selected or promoted by this work.

## Premise

Mary's existing systems remain responsible for identity, memory, relationship,
personality, values, stance, factual authority, capability truth, intent, and
whether deeper work is needed. The experiment separates four response-risk
classes:

- `PRECISION_LOCAL`: already represented facts, preferences, disagreement,
  uncertainty, shared history, relationship state, capability/runtime/project
  truth, and reference-sensitive answers. A typed deterministic composer is the
  benchmark candidate; Qwen is not called by default.
- `SOCIAL_LOW_RISK`: a strict allowlist of fact-free greetings,
  acknowledgements, thanks, laughter/reactions, and a preselected generic
  follow-up. The deterministic composer remains the response candidate;
  qwen3:1.7b runs only as an invisible shadow.
- `OPEN_CONVERSATION`: novel or abstract ordinary discussion. The experiment
  preserves the existing stronger-language class and does not route it to 1.7B.
- `THINKING_REQUIRED`: tool, research, state-changing, expert, or deep work.
  The experiment preserves the existing thinking/tool class.

Classification is deterministic and fail-closed. Hard-work evidence wins;
authority-bearing or reference-sensitive semantics then win over style. Social
requires both an allowlisted dialogue act and the existing `social_instant`
lane. Unknown mixed cases do not become social.

## Procedural LocalComposer V2

V2 is a separate benchmark module. Production still instantiates the existing
`LocalResponseComposer`.

The V2 plan uses typed participant roles (`SELF`, `ADDRESSEE`, `JOINT`, and
explicit named/world entities) and supported clause frames. Facts are not
recovered by parsing reservoir prose. Actor, patient, recipient, temporal
order, negation, uncertainty, and ownership are therefore structural inputs.

The composer enumerates a bounded set of safe fragments and constructions,
verifies that every selected clause was consumed, then uses a stable SHA-256
seed and read-only recent phrase history to reduce repetition. Unsupported or
incomplete frames fail closed. Novel wording never outranks semantic safety.

## Sparse benchmark matrix

The fixed 18 cases cover six low-risk social turns, ten precision turns, one
open discussion, and one thinking/tool turn. qwen3:1.7b runs automatically on
only the six social cases. Four precision cases are explicitly labeled
diagnostic probes (preference/stance, pronoun-sensitive history,
capability/runtime truth, and addressee emotion ownership); the classifier
still reports them as `PRECISION_LOCAL` and does not grant default Qwen
permission.

Exact `qwen3:4b` comparisons run only on explicitly flagged greeting,
joke/reaction, and open-discussion fixtures. The report does not rank or choose
a winner. Its known thinking/template mismatch is preserved as evidence rather
than silently substituting another tag.

Each case preserves:

- classifier inputs, class, reasons, and timing;
- the authoritative typed semantic plan;
- deterministic variants and realization trace;
- raw Qwen/stronger samples only when policy permits;
- first-content/full-response/Ollama component timings and token data;
- semantic, ownership/referent, stance, form, assistant-language,
  unsupported-addition, naturalness-triage, and repetition measurements;
- null human-review fields and readable samples.

Automated `naturalness` and `harmlessness` values are explicitly triage. They
are not a human character judgment.

## Local model specialist roles

| Model | Evidence-based experimental role | Not trusted for |
|---|---|---|
| `qwen3:1.7b` | Fast experimental low-risk local social shadow/verbalizer | Precision semantics, identity, memory, relationship, capability truth |
| `qwen3:4b-instruct` | Richer but slower local comparison | Precision semantics or automatic promotion |
| `qwen3:4b` | Current Mary-like conversational quality baseline; explicit comparison only here | Surface-realizer template compatibility or precision authority |
| `gemma3:1b` | Candidate background extraction/compression utility | Mary dialogue by default |

These are benchmark roles, not production routing rules.

## Run on Windows

From the repository root:

```powershell
.\scripts\benchmark_hybrid_dialogue_runtime_windows.ps1 -Runs 3
```

The launcher creates a temporary isolated `MARY_DATA_DIR`, restores the prior
environment value, and writes only an explicit JSON developer artifact under
`runtime_reports/`. It never pulls a model. If a required exact tag is absent,
the report records that fact and the command exits incomplete instead of
substituting a model.

The Python entry point is:

```powershell
.\.venv\Scripts\python.exe -m scripts.benchmark_hybrid_dialogue_runtime --runs 3 --save runtime_reports\hybrid-dialogue-runtime-manual.json
```

No output is displayed as Mary's reply, spoken, written to canonical state, or
used to modify routing.

## Current finding

Validated on the canonical Windows host on 2026-08-23 with three runs per
eligible case. Report:
`runtime_reports/hybrid-dialogue-runtime-20260823-validated.json`.

| Candidate / class | Strict verifier acceptance | Ownership | Stance | Form | Full response p50 / p95 |
|---|---:|---:|---:|---:|---:|
| Procedural V2, social | 18/18 (100%) | 100% | n/a | 100% | 0.61 / 0.92 ms |
| Procedural V2, precision | 30/30 (100%) | 100% | 9/9 (100%) | 100% | 0.75 / 0.94 ms |
| qwen3:1.7b social shadow | 15/18 (83.33%) | 100% | n/a | 100% | 450.79 / 901.03 ms |
| qwen3:1.7b explicit precision probes | 0/12 (0%) | 75% | 0/3 (0%) | 100% | 771.33 / 1,097.60 ms |
| qwen3:4b explicit social controls | 0/6 (0%) | 0% | n/a | 50% | 6,089.75 / 6,541.61 ms |
| qwen3:4b explicit open controls | 0/3 (0%) | 0% | n/a | 100% | 6,047.66 / 6,432.20 ms |

The 1.7B social shadow reached 100% required semantic coverage,
ownership/referent fidelity, and form fidelity with no assistant language or
third-person/planner leakage. Its three rejected samples were the same neutral
follow-up drift: `Are you sure you want to continue?`, which added unsupported
uncertainty/pressure. It repeated exact outputs in 11/18 samples, so its speed
does not solve repetition by itself.

The explicitly unsafe precision probes confirmed the boundary. 1.7B flattened
the represented preference relation, split an exact temporal/reference answer
past its one-sentence contract, changed a capability condition into an
instruction to the listener, and reversed `you sound exhausted` into `I'm
really tired`. None was eligible to replace the deterministic answer.

Exact qwen3:4b emitted its internal planner/thinking text into the content
channel and hit the 72-token ceiling in every comparison. This validates the
documented template incompatibility; it is not a fair judgment of the model's
normal Mary-like conversational quality route.

Ollama `/api/ps` reported 1,313,309,981 of 1,313,309,981 allocated bytes in
VRAM for 1.7B and 2,534,953,450 of 2,750,217,981 bytes (92.17%) for exact 4B.
These are allocation values only, not proof of actual CPU/GPU compute
placement. Initial and final requested-model residency were both empty and
restoration reported no errors.

The hybrid separation is materially stronger than treating Qwen as a universal
verbalizer: typed deterministic rendering protected every precision fixture,
while the small model was confined to fast, low-consequence shadow work. The
1.7B result is promising for continued social-only shadow study, but its 83.33%
acceptance and high repetition are not enough to replace the deterministic
social composer. No production integration or model promotion is recommended.
