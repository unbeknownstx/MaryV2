# MaryV2 Live Learning / Developed-Self Loop

**Task:** #22  
**Certification date:** 2026-08-31 (America/Los_Angeles)  
**Final verdict:** **PARTIAL**

## Executive result

The extractor and governed developed-self loop are repaired and verified through canonical `MaryApplication.run()` composition.

The production-equivalent acceptance completed:

```text
authenticated creator evidence
→ structured bounded evidence
→ candidate
→ five governed consistent observations
→ promotion
→ durable developed preference
→ fresh conversation retrieval
→ context influence
→ measurable later behavior change
→ process-local reconstruction and retrieval
```

The verdict remains **PARTIAL**, not `LIVE LEARNING LOOP VERIFIED`, because the revised code is not deployed on the remote Railway Core. Deploying it would restart the authoritative production process, and Task #21 established that no safe remote backup/export and controlled restart path exists yet. The remote canonical state was not risked merely to force a live verdict.

## 1. Exact extractor/root-cause defect

`mary/development/preference_evidence.py` previously:

1. normalized the entire creator statement;
2. required a narrow direct opening;
3. tested whole-string regular expressions with `re.match()`;
4. returned immediately after the first match; and
5. returned at most one `PreferenceEvidence`.

Consequences:

- adjective/noun adjacency was overly strict;
- `actionable answer first` and `summary before detail` were not represented;
- compound statements could silently lose a second supported dimension;
- common creator language could be classified `not_applicable`;
- same-dimension conflicts in later clauses were not examined.

The repair keeps the narrow opening, quote, attribution, and provenance boundaries but returns at most one evidence item per approved dimension. It scans recognized polarity across the complete statement before emitting a dimension, so a statement containing both supported directions is rejected for that dimension regardless of clause order.

## 2. Supported preference dimensions

No new durable preference dimensions were added.

| Signal | Durable candidate |
|---|---|
| `response_length` | `creator interaction response length` |
| `directness` | `creator interaction directness` |
| `list_structure` | `creator interaction list structure` |
| `follow_up_questions` | `creator interaction follow-up questions` |

`actionable answer first` and `summary before detail` are bounded forms of the existing `directness` dimension. They are not new memory or personality categories.

## 3. Extraction behavior before versus after

| Creator statement | Before | After |
|---|---|---|
| `I prefer concise actionable answers first.` | Missed/partially represented | `response_length` + `directness` |
| `I prefer technical explanations to start with a short summary before the detail.` | `not_applicable` | `directness` |
| `That was too verbose. Give me the actionable answer first in situations like this.` | Response-length only | `response_length` + `directness` |
| `I prefer tea in the afternoon.` | `not_applicable` | `not_applicable` |
| `I prefer answers that are not concise.` | Not explicitly protected against the new broad form | `not_applicable` |
| `I prefer non-actionable answers.` | Not explicitly protected against the new broad form | `not_applicable` |
| `I prefer concise answers but detailed responses.` | Order-dependent risk | No response-length evidence |
| `I prefer detailed responses but concise answers.` | Order-dependent risk | No response-length evidence |
| `That was too verbose, but give more detail in your responses.` | First corrective direction could win | No response-length evidence |
| `That response was too brief, but please keep your answers concise.` | First corrective direction could win | No response-length evidence |

The implementation does not infer unsupported negation. Scoped negative modifiers and ambiguous same-dimension conflicts are rejected instead of guessed.

## 4. Governance rules preserved

The repair did not change promotion policy.

### Provenance gates

- input must be creator-authored;
- `input_authority` must be `creator`;
- guest and conflicting guest-origin input is blocked;
- provider/model output is never creator evidence;
- failed generation is blocked;
- initiative/environment context is blocked;
- quotes, reported speech, and attributed statements remain rejected.

### Promotion gates

Base candidate eligibility remains:

- minimum observations: 3;
- mean confidence: 0.70;
- consistency: 0.75;
- mean magnitude: 0.50.

Automatic growth promotion remains stricter:

- minimum observations: 5;
- mean confidence: 0.85;
- consistency: 0.90;
- mean magnitude: 0.60.

The fifth consistent observation promoted in the acceptance. Conflicting evidence remained governed and did not promote.

### Integrity gates

- stable evidence IDs remain bound to canonical turn IDs and normalized signals;
- retry replay does not add an observation;
- evidence IDs are deduplicated across active candidates and decision history;
- canonical/authored preferences cannot be overwritten through experience promotion;
- CharacterSourcebook is never a persistence target of this loop.

## 5. Files changed

- `mary/development/preference_evidence.py`
  - bounded multi-dimension extraction;
  - exact actionable/summary-first forms;
  - scoped-negation protection;
  - full-statement polarity conflict suppression;
  - stable opaque candidate and developed-preference references.
- `mary/development/growth.py`
  - observes each bounded evidence item independently;
  - preserves stable per-signal dedupe;
  - records content-free evidence/candidate/promotion/developed-state diagnostics;
  - projects active developed-preference IDs.
- `tests/integration/test_canonical_lifecycle.py`
  - natural-language, compound, negation, conflict, ID-chain, behavior, and persistence coverage.
- `docs/certification/MARYV2_LIVE_LEARNING_DEVELOPED_SELF_LOOP_2026-08-31.md`
  - this report.

## 6. Canonical integration tests

All integration behavior uses canonical application composition and `MaryApplication.run()`.

| Required scenario | Evidence |
|---|---|
| Common concise/action-first phrase | Compound test yields length + directness |
| Summary-first technical phrase | Summary test yields directness |
| Corrective feedback | Corrective test yields length + directness |
| Compound supported dimensions | Two independently identified evidence items and IDs |
| Unsupported/incidental statements | Remain `not_applicable` |
| Provider-authored statement | Provider response cannot become input evidence |
| Guest/noncreator overwrite | Blocked |
| Failed turn | Blocked with `failed_turn` |
| Retry | Observation count unchanged |
| Consistent reinforcement | Observation count advances |
| Conflicting evidence | Consistency governance prevents promotion |
| Promotion threshold | Promotion occurs only at strict observation 5 |
| Durable persistence | Developed preference stored |
| Fresh session retrieval | New conversation receives developed state |
| Later context | Disposition receives concise instruction and length bound |
| Later behavior | Comparable deterministic response becomes shorter |
| CharacterSourcebook | Snapshot unchanged |
| Sleep/wake | Preference remains active |
| Reconstruction | New application loads and applies preference |

## 7. Security and provenance tests

Verified:

- quoted creator-preference examples are not evidence;
- single-quoted document text is not evidence;
- reported third-party preferences are not evidence;
- incidental facts are not preferences;
- provider output is not evidence;
- provider-unavailable/failed generation is not evidence;
- guest and creator/guest-origin conflict are blocked;
- Mary-initiated/environment context is blocked;
- duplicate turn IDs do not inflate evidence;
- post-promotion retry does not recreate a candidate;
- scoped negation does not become positive evidence;
- corrective and explicit contradictions are order-independent;
- diagnostics contain opaque IDs/status, not the raw creator statement.

Independent implementation review result: **PASS; no remaining material security defect identified.**

## 8. Focused-suite result

```text
74 passed
```

Coverage included:

- canonical lifecycle;
- deep growth bounds;
- preference promotion;
- developed-self persistence;
- persistence recovery;
- persistent path isolation;
- turn failure observability;
- CharacterSourcebook and retrieval;
- canonical runtime authority.

## 9. Full-suite result

```text
1,455 passed
1 skipped
1 failed
```

The sole failure is:

```text
tests/scripts/test_repository_structure.py::test_current_repository_passes_structure_gate
```

Reason: the structure guard rejects the user-supplied `attached_assets/` directory containing the Task #22 specification. No functional learning, persistence, provenance, or runtime test failed.

## 10. Live production sequence with content-free IDs

**Not executed on the revised code.**

The authoritative Railway Core is remote, while this implementation remains in the current Replit working tree. Updating Railway would require a production deployment/restart. Task #21 found no safe remote state export/backup or controlled restart path, so production Core was not redeployed or restarted.

No claim is made that the repaired extraction is live on Railway.

### Production-equivalent bounded sequence

The complete sequence was run using canonical composition, temporary configured persistence, and a deterministic provider. No raw creator statement was included in diagnostics.

| Observation | Experience ID | Evidence ID | Candidate ID | Count | Candidate state | Gate/result |
|---:|---|---|---|---:|---|---|
| 1 | `experience_47bfdbf51573453f92386a51fe5ff3e2` | `creator_turn_365d700aa9b9cbed071a94460f308d4e` | `preference_candidate_61c393c0978673d0ce2a2908` | 1 | candidate | deferred |
| 2 | `experience_81422919a40943cca872bb921de64dd0` | `creator_turn_67f7142aeaee3cedf134553dcc82842d` | same | 2 | candidate | deferred |
| 3 | `experience_3a5c73a79cef4af1b62b3e73a45ad304` | `creator_turn_5fa84f0a45e362b98b86e9949faf2ee0` | same | 3 | eligible | `base_eligible` / deferred |
| 4 | `experience_fad5f01a24e449b7b40d0adcbbe43305` | `creator_turn_65e0a1181b7ef3054f33c58c8d14067f` | same | 4 | eligible | `base_eligible` / deferred |
| 5 | `experience_0dac0836070a41ca9fe5ec994e325327` | `creator_turn_f725a89f96913fdc5794d5db80492e63` | same | 5 | promoted | promoted |

Developed preference:

```text
developed_preference_cc60f5a44c9b9bbc45f1812c
state=active
```

## 11. Candidate observation progression

```text
1 candidate/deferred
2 candidate/deferred
3 eligible (`gate_outcome=base_eligible`)/deferred
4 eligible (`gate_outcome=base_eligible`)/deferred
5 promoted
```

This proves that base eligibility did not bypass the stricter automatic growth threshold.

## 12. Promotion result

At observation 5:

- `disposition=promoted`;
- `promotion_result=promoted`;
- candidate state changed to `promoted`;
- the active candidate moved to promotion history;
- a developed interaction preference was written;
- one governed relationship-development milestone was recorded.

## 13. Durable developed-preference result

Before promotion:

```text
developed_preferences=0
```

After promotion:

```text
developed_preferences=1
developed_preference_id=developed_preference_cc60f5a44c9b9bbc45f1812c
state=active
```

No semantic memory or developed personality trait was manufactured.

## 14. Fresh-session retrieval result

A fresh conversation, without restating the learned preference, produced:

```text
preferred_length=brief
developed preference state=active
```

A newly constructed canonical application loading the same configured persistence root also produced:

```text
preferred_length=brief
developed_preferences=1
state=active
```

Full remote process restart remains deferred to the safe restart-certification task.

## 15. Measured behavioral influence

The same long technical request was used before and after promotion. The final request did not restate or remind Mary of the preference.

| Measurement | Before | Fresh session after promotion | Reconstructed application |
|---|---:|---:|---:|
| Output characters | 251 | 40 | 40 |
| Preferred length | medium | brief | brief |

Reduction:

```text
211 characters
84.1%
```

The deterministic provider changed output only when the canonical compiled generation prompt carried the concise length directive. This proves retrieval → context → provider-facing instruction → observable behavior in the production-equivalent composition.

## 16. CharacterSourcebook before/after

| Point | Records | Version | Hash | Errors |
|---|---:|---|---|---:|
| Before evidence | 189 | 1.0 | `49f3c9963de2b35d108d` | 0 |
| After promotion | 189 | 1.0 | `49f3c9963de2b35d108d` | 0 |
| After reconstruction | 189 | 1.0 | `49f3c9963de2b35d108d` | 0 |

The complete snapshots were equal.

## 17. Remaining limitations

1. The repaired code has not been safely deployed to the remote Railway Core.
2. No revised-code Mobile→remote-Core live promotion was attempted.
3. Full remote process restart/reconstruction remains deferred until backup/export and controlled restart exist.
4. Provider-facing behavioral proof used a deterministic offline provider; cloud-provider phrasing variance was not used as a pass criterion.
5. Extraction remains intentionally bounded to four interaction dimensions.
6. Ambiguous same-dimension compound statements are rejected rather than interpreted.
7. The repository structure gate remains red while the required uploaded task file is present.

## 18. Exact commit hash

Current repository `HEAD`:

```text
a58cab5db983856d80289fc579ce3d6a3f457ae3
```

The Task #22 implementation and this report are working-tree changes on top of that commit. No commit, push, Railway deployment, or production restart was performed because none was explicitly authorized and the remote restart safety prerequisite is still absent.

# PARTIAL

The governed learning/developed-self loop is repaired and completely verified in canonical production-equivalent composition, including persistence, fresh-session retrieval, provider-facing context influence, measurable behavioral adaptation, reconstruction, security boundaries, and CharacterSourcebook immutability.

The required live Railway proof cannot honestly be certified until this revision is safely deployed. Therefore the only evidence-supported final task verdict is:

**PARTIAL**