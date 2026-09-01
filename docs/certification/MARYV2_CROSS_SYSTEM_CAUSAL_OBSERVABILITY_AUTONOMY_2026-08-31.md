# MaryV2 Task #24 Certification

**Scope:** Cross-system causal observability and live proposal-only autonomy  
**Safety rule:** Durable fingerprint equality is mandatory before any live
acceptance turn.

## Restart-time fingerprint forensics

The first Task #24 deployment and its rollback were stopped before acceptance
because their pre-turn durable fingerprints did not equal the verified
pre-deployment fingerprint:

- pre-deployment: `4655b5db90cb8881b5f3a0d82381abcee6550e1f275a45d015a30b6535bffb26`
- first deployment: `b2681c1bc1642478bb489ab130097ea22f65ca94115ad81d1623c961be4c37c9`
- rollback startup: `71e3179eb323a4f0cb89db5c3c02c186f541ee18664fd6c0163de9140a2e0c01`

File count, projected byte count, and CharacterSourcebook remained unchanged.
No creator, learning, or autonomy acceptance turn ran during either failed
attempt.

An offline restore of the verified Task #23 production archive isolated load
from shutdown. Construction did not change disk state. `MaryApplication.close()`
then changed one fingerprint-relevant file:

| Relative path | Before hash | After hash | Changed JSON paths | Classification |
|---|---|---|---|---|
| `personality/developed_self.json` | `fc438c3a5806619f7ba3714e1766302d1f4d0f125ebc1cc4348d922915ab34e5` | `614b21036ae41c072ea41b53ad00c024b8e103919d3bac3d9ca2f4254cf06f76` | `$.preference_overrides.creator interaction response length.created_at`; `$.preference_overrides.creator interaction response length.updated_at` | durable canonical chronology; defect |
| `runtime/conversation_engagement.json` | `e772923cf14310db9697c70836ae000591f646a22f3e8e0baab80f3b824f6b5f` | raw file reserialized | no JSON value path changed | serialization-only; projection-v2 already canonicalizes/excludes process-local plan fields |

### Owner and writer

`DevelopedSelfStateStore.load()` delegates persisted preference reconstruction
to `Preferences.load()`. That loader used the normal mutation method,
`set_preference()`, which generated current `created_at` and `updated_at`
timestamps. The mutation existed in memory before the first creator turn and
became durable when `MaryApplication.close()` unconditionally saved developed
self-state during graceful Railway replacement.

The fingerprint contract was correct: learned preference chronology is durable.
The persistence loader was wrong. The repair retains normal validation and
normalization but restores serialized timestamp presence and values exactly,
making load observational. Missing or malformed legacy timestamp metadata is
also preserved until a real preference mutation replaces it.

## Regression evidence

- Exact archived production shape: fingerprint identical before load, after
  load, and after close.
- Developed preference timestamp metadata: exact preservation covered,
  including missing and malformed legacy fields.
- Real developed-preference mutation: changes the fingerprint.
- Engagement process-local fields: remain excluded by projection-v2 tests.
- CharacterSourcebook projection: unchanged.
- Focused persistence/integration suite: `40 passed`.
- Full suite: `1,485 passed, 1 skipped`.
- Compilation and diff hygiene: PASS.
- Deterministic/offline release verification: PASS.
- Independent architecture/privacy review: PASS.

## Remediation transition

The repaired Task #24 tree was deployed as Railway remediation revision
`7cd3d8d6763eaf9f8f06cba482165fe93f6f5a61`. No acceptance turn ran.

Fresh patched-state backup:

- backup: `MaryV2-state-20260901-033538Z-d16ffabc7199`
- format/projection: `maryv2-state-backup-v2` / `2`
- files/bytes: `12` / `81,347`
- fingerprint:
  `d16ffabc7199471a9ca3c683f396216f835fd4fe3c89ca4c167d50d742aadb45`
- sourcebook: version `1.0`, 189 records, hash `49f3c9963de2b35d108d`
- required developed preference:
  `developed_preference_cc60f5a44c9b9bbc45f1812c`, active
- backup verification: PASS

## Certification restart and live acceptance

Certification revision:
`a20329227fc3f335433de4bfcd0d3ffe69b839c8`

The single certification deployment replaced Core instance
`618557bc-7b87-4603-91df-3f1f739ca0bb` with
`499ba90f-0d2f-4b3f-9739-f472f73835e8`.

Before any acceptance turn:

- fingerprint:
  exact `d16ffabc7199471a9ca3c683f396216f835fd4fe3c89ca4c167d50d742aadb45`
  match;
- files/bytes: exact `12` / `81,347` match;
- sourcebook: exact version/count/hash match.

### Live causal evidence

- Four bounded authenticated turns completed successfully.
- Every queried historical trace returned the same content-free completion by
  raw turn filter and opaque request filter.
- The normal provider-backed turn recorded:
  `provider_availability=success`, `provider_generation=success`, and
  `provider_fallback=not_needed`.
- Each relevant trace projected the existing active developed preference ID
  `developed_preference_cc60f5a44c9b9bbc45f1812c`.
- The preference remained the sole active developed preference; certification
  did not create another one.
- Traces linked authentication, ingress, lifecycle, attention, context,
  sourcebook, memory, relationship, developed-self, growth, persistence,
  autonomy evaluation, and response serialization without prompt/response
  content.

### Proposal-only autonomy evidence

- A harmless creator-directed curiosity established one real Agency
  orientation.
- Evaluation `evaluation_4f1d0e8daeaa456a` produced pending-confirmation
  proposal `proposal_47dc810581c44727`.
- Repeated relevant evaluation `evaluation_72227c5347e94475` returned
  `deduplicated_existing` with that exact proposal ID.
- Both traces reported `proposals_recorded_not_executed`.
- No approval, ready action, execution attempt, tool call, spending, message,
  capability dispatch, filesystem action, or external consequential action
  occurred.

### Sleep/wake and Mobile parity

- Manual offline state produced `OFFLINE`,
  `attention_paused_by_sleep=true`, and
  `autonomy_paused_by_sleep=true`.
- After clearing manual offline and explicitly waking the registered
  certification surface, Core returned `ACTIVE` with both pause flags false.
- The Mobile workflow ran as `remote-core client` and explicitly did not create
  a second Mary.
- Authenticated Mobile `/api/state` projected Core instance
  `499ba90f-0d2f-4b3f-9739-f472f73835e8`, exactly matching production Core.

## Final verdict

**PASS — Task #24 cross-system causal observability and live proposal-only
autonomy are certified.**

The restart-time discrepancy was an owner-level deserialization defect, not
state loss and not a fingerprint-contract defect. The durable gate was never
weakened: failed deployments stopped before acceptance, remediation was
verified offline and independently reviewed, a fresh patched-state backup was
created, the single certification restart matched it exactly, and live
acceptance proved causal linkage, bounded lookup, learned-state continuity,
proposal deduplication, lifecycle gating, Core/Mobile parity, and zero
autonomous execution.