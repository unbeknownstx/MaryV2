# MaryV2 Full Operational Certification

**Certification date:** 2026-08-31 America/Los_Angeles / 2026-09-01 UTC  
**Specification:** Task #21 — MaryV2 Full Operational Certification  
**Method:** Evidence-first production exercise, bounded negative tests, canonical offline verification, and source ownership audit  
**Final verdict:** **PARTIAL**

## Executive conclusion

MaryV2 is operating as one canonical Core-owned identity through the production Mobile surface. The observable portions of normal turns, real provider fallback, private-route isolation, lifecycle gating, retry idempotency, attention queueing/claiming, growth journaling, projection parity, and bounded request/provider failures were exercised live. Post-processing and serialization recovery were exercised only in canonical tests.

The system cannot receive `PASS — COHERENT OPERATIONAL SYSTEM` because several required major loops did not complete:

1. The production learning experiment created only a deferred preference candidate. Common explicit preference phrasings were not recognized, no preference was promoted, no fresh-session retrieval occurred, and no later behavioral effect was demonstrated.
2. Autonomy evaluation is wired and sleep-paused, but no harmless live proposal with traceable causal evidence was produced.
3. Production Core restart/reconstruction was unsafe to perform because the remote deployment exposes no state backup/export or restart control.
4. Physical capability-node, iPhone, and Windows desktop behavior remains unverified.
5. Cross-system telemetry does not carry enough durable object IDs to prove every step of memory, relationship, developed-self, attention, and autonomy causally from a turn.
6. The release gate is currently red solely because it treats the user-supplied `attached_assets/` certification specification as a forbidden root directory.

This is not a blanket failure. The live evidence supports a coherent canonical runtime with important operational loops working, but not the complete computational-character system required by the specification.

## Certification labels

- **LIVE VERIFIED:** exercised successfully against production Core/Mobile.
- **LIVE VERIFIED WITH LIMITATIONS:** exercised live, but observability or unavailable dependencies limit the claim.
- **TEST VERIFIED ONLY:** exercised through canonical isolated tests, not production.
- **IMPLEMENTED BUT NOT EXERCISED:** present and wired, but no successful operational exercise was performed.
- **PARTIAL:** part of the intended loop worked, but the full required loop did not.
- **FAILED:** a required behavior was exercised and failed.
- **UNKNOWN:** evidence was insufficient for a defensible classification.

## Master certification matrix

| System | Intended behavior | Live evidence | Cross-system evidence | Persistence evidence | Failure evidence | Verdict | Remaining work |
|---|---|---|---|---|---|---|---|
| Canonical identity/runtime | One Core-owned Mary; surfaces/providers/nodes are replaceable clients/capabilities; no competing runtime state | Mobile and Core reported the same Core instance throughout 15 accepted turns and all lifecycle transitions | Mobile experience declares `identity_owner=mary_core`; Core owns sourcebook, routing, growth, lifecycle, and nodes | Identity and sourcebook reconstruct from canonical composition/assets in tests | Mobile/Core stayed on one instance through provider, auth, lifecycle, and malformed-request failures | **LIVE VERIFIED WITH LIMITATIONS** | No live node replacement occurred; competing state was not exhaustively ruled out; production restart unverified |
| Normal turn pipeline | Mobile → Core → application → context → cognition → post-processing → projections | Authenticated Mobile turns returned turn/request IDs; growth journal and attention advanced once per accepted turn | Representative turns linked request, turn, experience, provider, growth, and attention snapshots | Growth journal was configured and updated; durable memory was not written by incidental inputs | Sleeping/offline turns were rejected without partial mutation | **PARTIAL** | Prove per-turn memory retrieval, relationship/developed projection, autonomy evaluation, and persistence with causal IDs |
| Memory and experience evolution | Temporary recall; selective learning; governed durable learning; later influence | Temporary marker recall succeeded; incidental marker was not promoted; explicit/corrective evidence created one deferred candidate | Fallback turn still advanced growth and attention | No semantic/episodic memory was created; no preference promotion or fresh-session retrieval occurred | Unsupported explicit phrasings produced `not_applicable`; corrective evidence reached only two observations | **PARTIAL** | Repair preference extraction and complete promotion → restart → retrieval → behavior experiment |
| Character integrity | Canonical 189-record authored authority remains immutable and influences behavior | Core loaded 189 records; hash `49f3c9963de2b35d108d` stayed unchanged through all probes | Core and Mobile agreed on 189 records | Sourcebook is source-backed and reconstructed at startup | Provider failures, learning probes, lifecycle changes, and private route did not alter count/hash | **PARTIAL** | Mobile should project hash; prove bounded sourcebook-to-behavior influence |
| Relationship | Creator relationship evidence is governed, persisted, and later projected | Benign appreciation turn completed; no affection or milestone was manufactured; score/history/profile counts appropriately stayed unchanged | Core and Mobile relationship aggregates matched | Relationship persistence/recovery passed canonical tests | Guest overwrite and provenance negatives are test-only | **PARTIAL** | Prove live evidence write, persistence, later context use, and guest protection with trace IDs |
| Developed self | Governed evidence becomes durable developed preference/personality and affects behavior | One response-length candidate reached two consistent observations; no promotion | Growth and Mobile projections agreed on candidate/durable-state counts | Developed-self persistence passed isolated restart tests | Two ordinary explicit phrasings were missed; later comparable response was not shorter | **PARTIAL** | Fix extractor coverage and repeat full operational learning loop |
| Provider/cognition routing | Free-first fallback; private means Ollama-only; safe return to normal | Groq, Gemini, and OpenRouter all produced live turns; real Groq failure fell back to Gemini; another turn fell through Groq and Gemini to OpenRouter | Successful fallback advanced growth and attention; provider attempts were projected | Routing override is intentionally session-local | Private probe attempted only unavailable Ollama and never cloud; restore cleared override | **LIVE VERIFIED** | Real Ollama inference requires a connected node |
| Attention/events | Every accepted creator input reaches relevance, attention, claim, and bounded evaluation | Final process counters showed 15 turns, 15 published, 15 claimed, zero pending/dropped | Per-turn attention increments matched accepted turns; replay and rejected turns did not duplicate | Queue is intentionally ephemeral | Sleeping/offline gates suppressed new accepted work | **PARTIAL** | Prove relevance processing and carry attention event ID into turn/autonomy trace |
| Autonomy | Bounded evaluation; proposal-only; no spending/uncontrolled execution; sleep pause | Sleep and OFFLINE both set `autonomy_paused_by_sleep=true`; wake restored false | Lifecycle → autonomy pause/resume was live | Runtime scheduling is reconstructed; transient queues are ephemeral | No live autonomous tool/spend execution occurred | **IMPLEMENTED BUT NOT EXERCISED** | Produce one harmless live proposal and expose cycle/proposal causal IDs |
| Lifecycle | SLEEPING ↔ ACTIVE; OFFLINE distinct; same Mary after reconnect; provider/autonomy/tool/node work suppressed while gated | SLEEPING rejected turns; register/wake restored ACTIVE; OFFLINE rejected turns; disconnect restored SLEEPING; reconnect preserved instance/state | Mobile and Core lifecycle projections matched exactly | Sourcebook hash, growth count, and memory counts stayed unchanged across transitions | Expired lease wake was rejected until re-registration; no partial state mutation | **LIVE VERIFIED WITH LIMITATIONS** | Generic network interruption/recovery, live tool/node suppression, and Core process failure untested |
| Persistence/reconstruction | Durable state survives restart; ephemeral state clears | Host-local state integrity passed; production restart not performed | Canonical runtime tests cover application close/reopen and path isolation | 10/10 host-local JSON files readable; 18 backup generations; restart verifiers passed | Recovery and corruption paths passed tests | **TEST VERIFIED ONLY** for restart | Add safe remote backup/export and controlled restart workflow |
| Core↔Mobile projection | Mobile reflects canonical Core, not shadow state | Identity, lifecycle, memory, growth, relationship, nodes, autonomy aggregates, and attention matched | Experience projection names Core as identity owner | Projection contracts passed targeted tests | Hash omitted; Ollama model label differs by purpose; trace lacks Core instance ID | **LIVE VERIFIED WITH LIMITATIONS** | Resolve projection defects and add historical/queryable trace |
| Tools/capabilities | Typed request → permission → confirmation → broker → normalized result | No connected capability node; no destructive live action attempted | Core reported zero nodes and unavailable Ollama route | Node trust durable; sessions/tasks/grants intentionally ephemeral | Focused permission, stale-session, dispatch, and tool tests passed | **TEST VERIFIED ONLY** | Exercise harmless real node/tool on physical hardware |
| Security | Creator/node authorities remain separate; invalid/stale credentials fail; telemetry excludes private upstream detail | Invalid creator auth returned 401; malformed request returned 422; sleeping/offline bypass returned 409 | Core remained coherent with unchanged counters after rejected requests | Trust/proof persistence and session rotation passed tests | Node credential, creator impersonation, stale session, guest learning, and tool auth negatives passed tests; Core routing state exposed raw provider account metadata | **PARTIAL** | Sanitize provider errors; validate public TLS/proxy and physical-node boundaries |
| Shared work | Canonical durable work events reconstruct and are retrievable without becoming dialogue memory | Aggregate reported two durable events, but a bounded recall query was not acknowledged and did not populate `last_recall` | Mobile/Core shared canonical memory projection | Canonical shared-work tests passed | Live retrieval path produced no positive evidence | **PARTIAL** | Clarify aggregate semantics and prove live write → restart → recall |
| Observability | Diagnose provider, fallback, timing, failures, restart, and IDs without private content | Live trace exposed turn/request/provider/timing; fallback attempts were visible | Mobile latest trace and Core snapshots allowed external correlation | Core instance/uptime reveal process identity | Mobile omits Core instance; no trace history/query; Core routing state retained raw provider error text | **PARTIAL** | Sanitize routing errors and add causal/historical trace fields |
| Soak/long session | Multi-turn continuity without drift, duplication, leaks, or paid overuse | 15 accepted turns over several minutes and multiple providers/lifecycle states; no Core error | 15 attention events matched 15 accepted turns; retry added no duplicate | Growth journal advanced to 61/2048 with zero evictions | Latency varied with real fallback/cooldown but returned to sub-second; no paid calls | **LIVE VERIFIED WITH LIMITATIONS** | Longer hours-scale and physical network soak remain pending |
| Test/runtime equivalence | Full-system/release/acceptance/production/persistence/integration claims use canonical composition; unit tests may remain intentionally lower-level | Live Mobile/Core authority matched expected composition | AST guard covers all release/install verifiers and all integration tests | Canonical lifecycle persistence uses configured isolated roots; owner-level persistence tests intentionally isolate stores | Release gate is red; production/persistence tests outside guarded scopes were not exhaustively classified | **PARTIAL** | Extend the authority inventory/guard and fix structure policy without deleting uploads |

## Representative live evidence ledger

Raw prompts, responses, credentials, and memory contents are intentionally excluded.

| Purpose | Turn ID | Request ID | Experience ID | Provider/result |
|---|---|---|---|---|
| Temporary context storage | `turn_e62e39aa25114f56afcda1f61c7c00cc` | `request_f4d1da896a4f4b7fb0c4cb956a45059b` | `experience_9260911b99ec411b864114cbe21ab3b8` | Groq success |
| Temporary recall and real fallback | `turn_d203e16d4bd84479abc68904c52bc6ca` | `request_26e3b69d7c384e2aa28b61a4a7d29829` | `experience_baa15b05fe214368ba7dfa8409d9aee9` | Groq failed; Gemini succeeded |
| Explicit preference candidate | `turn_d0470d2780f54d7bb561cf6a73e975a1` | `request_bfbd9036e6134af6914b1944f86cc55a` | `experience_ebfa7f147d9649fe9d41b43318858673` | OpenRouter success after fallback |
| Corrective feedback | `turn_50ef108c3eed4bedbe028475d880e6c0` | `request_adbac14aec6d45828d64daed553d05f6` | `experience_3012491c48e04466815ff527f40997cd` | OpenRouter success |
| Private-route probe | `turn_965f51d1522c4327a188d9024f7a7404` | `request_7c4210a99e60427d9f0903e37898f1e8` | Not surfaced atomically | Ollama only; not configured |
| Idempotency probe | `certification-retry-proof-20260831` | First request recorded; replay received a new transport request ID | One growth event only | Same response; no duplicate turn/growth/attention |

## 1. Overall operational verdict

**PARTIAL**

The canonical runtime and several cross-system loops are operational. The complete learning/developed-self loop, live autonomy proposal chain, production restart reconstruction, and physical capability execution are not certified. Those are major intended behaviors, so a conditional pass would overstate the evidence.

## 2. Canonical runtime proof

- Production Core reported service `mary-core`, protocol `1`, architecture `13.2`.
- Mobile `/api/state` and Core `/v1/state` repeatedly reported the same Core instance.
- Mobile `/api/experience` reported `identity_owner=mary_core` and `authority=presentation_projection_only`.
- Providers appeared only as routed cognition engines.
- Nodes appeared only under Core-owned compute-fabric projections; none were registered or connected.
- Lifecycle, sourcebook, memory, growth, relationship, attention, nodes, and provider routing were all obtained from Core-backed Mobile projections.
- No competing production Mary identity was observed through the exercised Core/Mobile paths, but the certification did not exhaustively rule out every possible shadow state.
- Capability nodes were projected as Core-owned, permission-bounded providers, but no node was connected and replacement behavior was test-only.

**Verdict: LIVE VERIFIED WITH LIMITATIONS.**

## 3. Complete live turn proof

Fifteen accepted turns were completed during the Core process. For accepted turns:

1. Mobile returned a Mary turn ID and request ID.
2. Provider or local/system provenance was returned.
3. Growth journal advanced once.
4. Attention published and claimed once.
5. Mobile returned a Core-derived dashboard.
6. Sourcebook count/hash stayed stable.

The real fallback turn proves that provider fallback still reaches post-turn growth and attention. The idempotent replay proves that one logical turn is not processed twice.

The trace does not atomically expose memory IDs, relationship observation IDs, preference evidence IDs, attention IDs, or autonomy cycle IDs. Production durable memory remained zero, and per-turn memory retrieval, relationship/developed-state projection, autonomy evaluation, and persistence could not be causally proven. Consequently, only the observable portion of the chain is operationally demonstrated.

**Verdict: PARTIAL.**

## 4. Complete learning-loop proof

### Immediate context

The temporary certification marker was recalled correctly in the same conversation.

### Selective non-learning

The temporary marker did not create preference evidence, semantic memory, developed preference, or sourcebook mutation.

### Explicit preference evidence

One constrained explicit preference statement created a structured response-length candidate.

### Governance and reinforcement

A later corrective statement added a second consistent observation. Governance correctly deferred the candidate because it had only two observations. No unsafe automatic promotion occurred.

### Failure

Two common explicit phrasings were classified `not_applicable`, reproduced directly by `extract_preference_evidence()`. The candidate therefore did not reach promotion. No fresh-session persistence/retrieval or developed-state context injection could be demonstrated.

### Behavioral influence

The comparable response after correction was not shorter:

- Before correction: 289 characters.
- After correction: 315 characters.

One corrective turn alone is not expected to guarantee promotion, but the required full loop was not completed.

### Character authority

Sourcebook remained 189 records with hash `49f3c9963de2b35d108d`.

**Verdict: PARTIAL.**

## 5. Character integrity result

- Core loaded 189 canonical records from seven active sources.
- Core sourcebook hash remained stable through ordinary dialogue, fallback, learning probes, private route, retry, sleep, OFFLINE, reconnect, and failures.
- Mobile agreed on the record count.
- Developed preference count remained zero, so no authored personality rewrite occurred.
- Provider output did not change sourcebook authority.
- Responses were behaviorally coherent, but this certification cannot causally separate sourcebook influence from selected context/provider realization without exposing restricted source evidence.

**Verdict: PARTIAL.**

## 6. Relationship result

- Core and Mobile agreed on score 2, label “Getting familiar,” two history events, zero profile records, and zero milestones.
- A benign appreciation interaction completed through the canonical turn/growth path.
- Counters appropriately remained unchanged; the test did not manufacture affection or a milestone.
- Relationship persistence, deduplication, and guest/noncreator overwrite boundaries passed canonical tests.
- A normal-turn trace cannot identify the relationship observation/profile/history object for a given turn.

**Verdict: PARTIAL.**

## 7. Developed-self result

- Authored traits remained separately labeled and unchanged.
- A governed response-length candidate was created with high confidence and consistent evidence.
- Candidate observations advanced from one to two after corrective feedback.
- Promotion count and durable developed preference/personality counts remained zero.
- Developed-self restart persistence passed isolated tests.
- No live promotion, reconstruction, retrieval, context injection, or behavioral influence was demonstrated.

**Verdict: PARTIAL.**

## 8. Cognition/provider result

### Normal routing

The configured order was:

`Groq → Gemini → OpenRouter → Ollama`

Live turns succeeded on Groq, Gemini, and OpenRouter.

### Real fallback

- One turn: Groq failed; Gemini succeeded.
- Another turn: Groq failed, Gemini failed, OpenRouter succeeded.
- Cooldown states were subsequently respected.
- Successful fallback still advanced growth and attention.
- The fallback recall turn did not create false preference evidence.

### Private/local routing

1. Local/system control set `route=private`.
2. The probe attempted only Ollama.
3. Ollama reported `not_configured`.
4. No cloud provider was attempted.
5. Local/system control restored normal/free-first and cleared the override.

### Hardware limitation

No connected capability node existed, so real Ollama inference remains deferred.

**Verdict: LIVE VERIFIED.**

## 9. Attention/events result

- Each of 15 accepted turns produced one published and one claimed attention item.
- Final counters: 15 published, 15 claimed, zero pending, zero dropped.
- The idempotent replay did not create a second item.
- Malformed, unauthorized, sleeping, and OFFLINE requests did not create accepted attention work.
- Attention items had stable `attention_*` IDs in the bounded recent projection.
- The exposed production path does not separately show the relevance decision.
- Those IDs are not carried into turn or autonomy trace, preventing causal event→proposal proof.

**Verdict: PARTIAL.**

## 10. Autonomy result

- SLEEPING and OFFLINE both paused autonomy.
- Register/wake/online restored the unpaused state.
- The focused canonical tests verify bounded evaluation, proposal-only authority, no automatic spending, no unconfirmed tool execution, and no unrestricted loop.
- No safe, meaningful live autonomy trigger produced a proposal during the certification session.
- The live projection has no autonomy cycle/proposal ID linked to the triggering attention item.

**Verdict: IMPLEMENTED BUT NOT EXERCISED.**

## 11. Lifecycle result

The following production sequence completed on the same Core instance:

1. SLEEPING with a valid but inactive surface.
2. Turn attempt rejected with 409.
3. Re-register existing client identity.
4. ACTIVE.
5. Wake and renew.
6. OFFLINE.
7. Turn attempt rejected with 409.
8. Online/reconnect.
9. ACTIVE.
10. Disconnect certification surface.
11. SLEEPING and autonomy paused.
12. Reconnect.
13. ACTIVE with unchanged Mary state.
14. Clean disconnect.

An expired certification lease also caused wake to fail until the surface was registered again, distinguishing stale lease recovery from ordinary wake.

OFFLINE was distinct from:

- **SLEEPING:** Core healthy, `offline=false`, execution gated until active surface.
- **Network failure:** conceptually distinct at the client transport boundary, but an actual interruption/recovery was not exercised.
- **Core process failure:** not exercised; would change health/process identity.

Durable-state fingerprints were unchanged across lifecycle transitions:

- Sourcebook hash unchanged.
- Memory counts unchanged.
- Growth journal unchanged by rejected turns.
- Runtime accepted-turn count unchanged by rejected turns.

Live tool dispatch and live capability-node task suppression could not be tested because no capability node was connected. Those lifecycle suppression contracts passed the focused canonical tests. Generic client-to-Core network interruption and recovery were also not exercised.

**Verdict: LIVE VERIFIED WITH LIMITATIONS.**

## 12. Persistence and reconstruction result

### Persistence matrix

| State | Intended durable? | Actual durability | Restart behavior | Reconstruction owner | Certification |
|---|---|---|---|---|---|
| Canonical identity | Yes, canonical boundary | Recreated from canonical Mary/Core composition; creator facts use governed stores | Fresh process identity; same Mary authority model | `Mary`, root authority, Core composition | Test verified; production restart unverified |
| Sourcebook | Yes | Source-controlled active assets; runtime index is rebuildable | Reloaded from active source inventory | Character sourcebook | Live integrity; restart test verified |
| Dialogue sessions | No, except promoted facts | Bounded process-local context | Clears; durable promotions remain | Dialogue/turn continuity | Live temporary recall; restart behavior test-only |
| Episodic memory | Selected events | Configured atomic JSON with backups | Reloads; corrupt primary can recover from backup | Episodic store / MemoryManager | Test verified only |
| Semantic memory | Approved/consolidated facts | Canonical memory; vector/reservoir indexes derived | Facts reload; indexes rebuild | Semantic store / MemoryManager | Test verified only |
| Developed preferences | Only after governance | Tentative evidence and developed-self stored separately | Approved state reloads; rejected dialogue does not | Developed state / preference promotion | Candidate live; promotion restart test-only |
| Developed personality | Authored core plus approved development | Authored core plus developed-self records | Core reloads and approved traits reapply | Personality / developed state | Test verified only |
| Relationship/history | Governed creator facts/history | Configured relationship/profile/history stores | Reloads conservatively | Relationship manager/history/user | Live projection; restart test-only |
| Growth journal | Yes | Configured bounded journal | Reloaded by GrowthEngine | Growth engine/journal | Live writes; restart verifier passed |
| Shared work | Yes when explicitly recorded | Represented through canonical relationship/growth/memory owners | Reloads only if accepted by owner | Relationship/memory/growth | Live retrieval not proven |
| Autonomy proposals | Mostly no; domain records may persist | Runtime scheduling/proposals are transient unless explicitly stored | Runtime reconstructs; transient proposals clear | Autonomy runtime/scheduler/actions | Test verified only |
| Creator surface leases | No | Process-local leases | Empty after restart; starts SLEEPING | Core surface coordinator | Live verified |
| Attention queues | No | Process-local bounded queue | Clears | Realtime/AttentionBus | Live verified |
| Node trust | Yes | Durable proof digest/generation/audit; no raw proof | Trust reloads; node must re-register | Core enrollment registry | Test verified only |
| Node sessions | No | Tokens, session generations, leases, and capabilities are ephemeral | Discarded; fresh authenticated session required | Core node registry/session authority | Test verified only |
| Node work ownership | No | Claimed task ownership and in-flight device work are process/session scoped | Discarded or reconciled as failed; never inherited by a replacement session | Core device-task registry | Test verified only |
| Tool grants | No | Request/runtime scoped | Must be reauthorized | Tool registry/manager | Test verified only |

### Integrity and backup evidence

- Host-local integrity: 10 current JSON files, 10 readable.
- Backup generations: 18.
- No stored values were displayed or modified.
- Offline release persistence/restart milestones passed.
- Focused persistence recovery, path isolation, and developed-self restart tests passed.

### Production restart decision

No production Core restart was performed. The remote service has no exposed backup/export or restart control, and the repository backup script protects only the host-local configured data root. Restarting without a remote backup and deployment recovery path would violate the specification’s safety condition.

**Verdict: TEST VERIFIED ONLY for reconstruction; production restart UNKNOWN.**

## 13. Capabilities/tools result

- Core reported zero registered/connected nodes.
- Ollama capability route was unavailable.
- No destructive or consequential live tool was invoked.
- The focused tests exercised typed previews, dispatch contracts, permission separation, creator confirmation, stale leases, token rotation, normalized results, and provider inability to bypass canonical authorization.
- The release local-tool smoke proved workspace escape blocking, static analysis without code execution, pending writes before approval, and exact approved execution.

**Verdict: TEST VERIFIED ONLY.**

## 14. Security result

### Live

- Invalid creator bearer token: 401.
- Empty/malformed turn: 422.
- Conflicting reuse of a turn ID: rejected with 422 and request ID.
- SLEEPING execution bypass: rejected with 409.
- OFFLINE execution bypass: rejected with 409.
- Rejected requests did not increment accepted turns, growth journal, memory, or attention.
- Private route did not fall through to cloud.

### Test-only

The focused 149-test set verified:

- Invalid node authentication.
- Enrollment grant restrictions.
- Durable proof vs ephemeral session separation.
- Node credential cannot become creator credential.
- Creator surface cannot impersonate node.
- Stale sessions and rotated tokens are rejected.
- Device permission and Core authorization are separate.
- Provider cannot invoke tools without canonical authorization.
- Guest/noncreator evidence cannot overwrite creator learning.
- Telemetry redaction and bounded failure taxonomy.

### Limits

- Public TLS/reverse-proxy behavior was not independently penetration-tested.
- No physical node credential store or OS boundary was exercised.

The live telemetry minimization requirement failed because authenticated Core routing status exposed raw provider account metadata. The remaining authorization boundaries were live- or test-verified as described above.

**Verdict: PARTIAL.**

### Failure-recovery detail

The focused 149-test run explicitly included:

- `test_failed_pipeline_turn_skips_autonomy_cycle_and_post_turn_experience`: a failed main pipeline does not run autonomy or post-turn experience.
- `test_growth_failure_is_visible_as_post_processing_without_losing_response`: post-processing failure remains visible while preserving the already-produced response and avoiding a false full-success claim.
- `test_serialization_failure_returns_request_id_and_records_safe_failure`: response serialization failure returns a safe request-correlated error and records `response_serialization` / `serialization_failure`.
- `test_secret_shaped_upstream_id_and_application_error_are_never_reflected`: application errors and secret-shaped upstream identifiers are not reflected.

These are **TEST VERIFIED ONLY** simulations. They are not presented as live production failures. The live malformed, unauthorized, provider-unavailable, fallback, stale-lease, SLEEPING, and OFFLINE cases all left accepted-turn, growth, memory, and attention counters coherent.

## 15. Projection-parity result

### Exact matches

- Core instance ID.
- Lifecycle state/offline/surface counts/autonomy pause.
- Episodic, semantic, and working memory counts.
- Growth journal, durable-state counts, candidate count, and promotion count.
- Relationship score/label/profile/history/milestone counts.
- Registered/connected node counts.
- Autonomy/agency aggregate counts.
- Attention published/claimed/pending/dropped counts.
- All five provider names and availability.

### Defects/limitations

1. Mobile sourcebook projection includes count but not sourcebook hash.
2. Mobile labels unavailable Ollama as `device:general:offline`; Core conversation routing labels it `device:conversation:offline`.
3. Mobile latest trace includes request/turn IDs but not Core instance ID.
4. Mobile exposes only the latest trace, while Core internally retains a bounded trace history.

**Verdict: LIVE VERIFIED WITH LIMITATIONS.**

## 16. Observability result

Live telemetry successfully diagnosed:

- Selected provider.
- Provider failure and fallback order.
- Cooldown state.
- Provider and pipeline timing.
- Mary request and turn IDs.
- Core process instance and uptime through health/state.
- Lifecycle-gated failures.
- Stable sourcebook and aggregate state around failures.

The Mobile trace was content-free in the captured output. Raw prompts, responses, memory contents, sourcebook evidence, and credentials were not required for diagnosis.

Limitations:

- Cross-system correlation required external before/after snapshots.
- Mobile trace lacks Core instance and durable subsystem object IDs.
- Core `compute_fabric.routing.last_generation.attempts` retained raw normalized provider error text. The observed 429 text included provider account metadata and a billing URL. No credential was exposed, but this is broader than the content-free diagnostic contract and should be sanitized.
- A real Core process failure/restart trace was not available.

**Verdict: PARTIAL.**

## 17. Soak-test result

The certification conversation itself was used as the quota-conscious soak:

- 15 accepted turns across several minutes.
- Providers exercised: Groq, Gemini, OpenRouter, local/system, and unavailable Ollama.
- Conditions exercised: successful generation, real fallback, multi-provider fallback, cooldown, private routing, idempotent replay, stale lease, sleep, wake, OFFLINE, reconnect, malformed request, and invalid auth.
- Final attention: 15 published, 15 claimed, zero pending/dropped.
- Growth journal: 61 of 2,048 records, zero evictions.
- Memory counts remained zero because no input met durable-memory promotion policy.
- No duplicate Mary turn/request IDs were found in the measured learning window.
- Identical replay did not duplicate turn, growth, or attention state.
- Eight measured provider turns ranged from 489.56 ms to 11,977.81 ms, median 2,609.96 ms. The final measured turn returned to 748.42 ms, so no monotonic latency drift was observed.
- Resource snapshot at 13 turns showed 23 provider attempts, 11 provider successes, and zero paid calls.
- Core `last_error` remained empty.

Context trimming and hours-scale resource stability were not directly observable from the exposed production projections.

**Verdict: LIVE VERIFIED WITH LIMITATIONS.**

## 18. Cross-system interaction result

| Interaction chain | Evidence | Result |
|---|---|---|
| Immediate context → cognition → behavior | Temporary marker recalled in same conversation | **Live verified** |
| Incidental input → governance → non-learning | Marker created no preference/semantic/developed state | **Live verified** |
| Feedback → experience → candidate | Corrective feedback advanced candidate to two observations | **Live verified** |
| Candidate → promotion → future cognition | No promotion occurred; later response was not shorter | **Failed to complete** |
| Relationship state → context → dialogue | Relationship projection present; causal turn linkage absent | **Limited** |
| Provider failure → fallback response → growth | Groq failure → Gemini success; journal and attention advanced | **Live verified** |
| Event → attention → claim | Accepted turns matched attention published/claimed counts | **Live verified** |
| Attention → autonomy proposal | No live proposal or causal ID | **Not exercised** |
| Sleep/OFFLINE → provider/autonomy suppression | Turns rejected; autonomy paused; no state mutation | **Live verified** |
| Wake/reconnect → same state → normal turn | Same Core/sourcebook/growth/memory; turns resumed | **Live verified** |
| Tool result → context/shared work/memory | No live capability connected | **Test verified only** |
| Restart → reconstruction → future retrieval | Isolated canonical tests passed; production restart unsafe | **Test verified only** |
| Shared-work state → retrieval | Aggregate existed; bounded recall produced no positive evidence | **Partial** |

## Test/runtime equivalence check

### Governed canonical scopes

The AST authority guard passed and rejects direct `Mary()` construction or coordinator-level `mary.process()` turns in:

- `scripts/run_release_verification.py`
- `scripts/run_diagnostics.py`
- `scripts/benchmark_production_hybrid_dialogue.py`
- every `scripts/verify_*.py` release/install/acceptance verifier
- every `tests/integration/test_*.py` file

This covers the repository’s named release, acceptance, full-system integration, long-session, canonical lifecycle, and production-hybrid integration paths. `tests/integration/test_mary_full_system.py` is within the guarded integration scope. End-to-end turns in that scope are required to use canonical application composition and `MaryApplication.run()`.

### Persistence scope

- Canonical lifecycle, developed-self, memory reconstruction, and path-isolation tests use configured isolated data roots.
- Application-level persistence/reconstruction evidence is canonical.
- Owner-level corruption, backup, optional-storage, and store tests intentionally construct individual persistence owners or a plain Mary/application in temporary directories. They verify owner contracts, not full-system composition.

### Intentionally retained lower-level tests

Direct `Mary()` construction remains in unit/owner suites for:

- cognition and character realization
- Core coordinator behavior
- memory retrieval and consolidation
- personality and preference-promotion owners
- relationship and curiosity owners
- agency orientation
- local tool approval/execution owners
- local mind/reservoir behavior
- isolated runtime/subsystem integrity

Those tests are not counted as live or full-system proof.

### Remaining audit gap

The guard is exhaustive for release/install scripts and `tests/integration`, but production- or persistence-named tests outside those scopes are not separately allowlisted/classified by an automated guard. The current release gate is also red because of the uploaded-assets structure policy.

**Verdict: PARTIAL.**

## 19. Real defects and follow-up work

No defects were repaired during certification.

### F1 — Complete explicit interaction-preference recognition and operational promotion

**Priority:** High  
**Classification:** Functional learning-loop defect  
**Owner:** `mary/development/preference_evidence.py`, growth/promotion integration

**Evidence:** Two ordinary explicit creator phrasings returned `None`/`not_applicable`; only a narrower phrase and corrective feedback were accepted. Candidate stopped at two observations, no promotion occurred, and later behavior was not shorter.

**Required acceptance:**

- Recognize supported compound forms without expanding beyond the four approved interaction dimensions.
- Preserve quote, provenance, failed-turn, guest, retry, and provider-output blocks.
- Treat separate dimensions explicitly rather than silently discarding directness/list structure.
- Demonstrate repeated evidence → explainable promotion → fresh process/session reconstruction → relevant retrieval → later behavioral influence.
- Keep CharacterSourcebook hash unchanged.

### F2 — Make repository structure validation compatible with preserved user uploads

**Priority:** High for release readiness  
**Classification:** Release-tooling defect  
**Owner:** `scripts.verify_repository_structure`

**Evidence:** Full suite: 1,452 passed, 1 skipped, 1 failed. Sole failure: `forbidden active root directory: attached_assets`. Offline release gate failed only `pytest` and `repository_structure`; every functional milestone passed.

**Required acceptance:**

- Preserve uploaded specifications/assets.
- Distinguish user attachment staging from forbidden Mary runtime state.
- Keep rejection of source-tree runtime data and generated state reports.
- Restore a clean full suite and release gate without deleting project assets.

### F3 — Add causal, historical cross-system certification traces

**Priority:** High  
**Classification:** Observability/certifiability defect  
**Owner:** Core turn observability, subsystem results, Mobile trace projection

**Required fields or equivalent linkage:**

- Core instance ID in Mobile trace.
- Query/history by request or turn ID.
- Experience ID.
- Memory operation/object IDs.
- Relationship observation/profile/history IDs.
- Preference evidence/candidate/promotion IDs.
- Attention event ID.
- Autonomy cycle/proposal ID.
- Explicit stage outcome for persistence and post-processing.

All fields must remain content-free and bounded.

### F4 — Sanitize provider failure detail in Core routing status

**Priority:** Medium  
**Classification:** Telemetry minimization defect  
**Owner:** LLM router status and Core compute-fabric projection

**Evidence:** Authenticated Core routing state retained raw normalized provider 429 text containing provider account metadata and a billing URL.

**Required acceptance:**

- Project provider, attempt, status, failure kind, retry/cooldown, elapsed time, and safe upstream hash only.
- Do not expose raw exception/provider response text in status or Mobile projection.
- Preserve enough information to diagnose fallback.

### F5 — Resolve Core/Mobile projection gaps

**Priority:** Medium  
**Classification:** Projection parity defect

**Required acceptance:**

- Mobile projects canonical sourcebook hash.
- Core and Mobile use the same purpose-qualified Ollama model label or explicitly label the purpose difference.
- Mobile trace includes Core instance ID.
- Parity tests cover these exact fields.

### F6 — Prove and clarify shared-work continuity

**Priority:** Medium  
**Classification:** Functional/semantic ambiguity

**Evidence:** `shared_work.durable_events=2`, but bounded recall was not acknowledged and `last_recall` stayed empty.

**Required acceptance:**

- Define what `durable_events` counts.
- Demonstrate canonical explicit work write → restart → retrieval.
- Record a content-free recall result.
- Prove Mobile/Desktop do not duplicate ownership.

### F7 — Add safe production backup and restart certification workflow

**Priority:** Medium  
**Classification:** Operational gap

**Required acceptance:**

- Obtain a verified remote-state backup without exposing contents.
- Record a manifest/fingerprint.
- Restart Core through the real deployment owner.
- Observe a new Core instance.
- Verify durable reconstruction and expected ephemeral clearing.
- Verify Mobile/node reconnection and post-restart retrieval.

### F8 — Produce one safe live autonomy proposal with causal evidence

**Priority:** Medium  
**Classification:** Operational certification gap

**Required acceptance:**

- Use a harmless bounded trigger.
- Link trigger/attention ID → evaluation → proposal ID.
- Prove dedupe/prioritization.
- Prove proposal-only authority and separate creator confirmation.
- Prove no spending or tool execution.

### F9 — Complete the test/runtime-equivalence inventory

**Priority:** Medium  
**Classification:** Certification/guard coverage gap

**Required acceptance:**

- Classify every test/script claiming full system, release, acceptance, production, persistence, or integration.
- Enforce canonical composition for system-level claims.
- Explicitly allowlist owner-level tests that intentionally construct plain Mary or isolated stores.
- Fail when a system-level test bypasses `MaryApplication.run()` or canonical Core composition.
- Keep the inventory understandable in release output.

## 20. Physical-device deferred matrix

Never promote these items to LIVE VERIFIED from simulation alone.

### Windows capability node

- [ ] Existing installation inspected.
- [ ] Startup task/service verified.
- [ ] Enrollment against production Core.
- [ ] Heartbeat and lease renewal.
- [ ] Ollama capability advertisement.
- [ ] Real Ollama inference.
- [ ] Private-route answer with no cloud fallback.
- [ ] Core restart reconnect.
- [ ] Windows reboot reconnect.
- [ ] Network interruption and recovery.
- [ ] Credential storage and old-session rejection on the real host.

### iPhone

- [ ] Real Safari/PWA or native launch.
- [ ] Background → foreground lifecycle.
- [ ] OS suspension and process eviction.
- [ ] Reconnect to same Core.
- [ ] Stale surface/session recovery.
- [ ] Microphone capture.
- [ ] Production STT round trip.
- [ ] Production TTS playback.
- [ ] Audio interruption/barge-in.
- [ ] Network offline/online recovery.

Backend readiness only: Mobile reported ElevenLabs TTS ready and Groq STT ready without synthesizing audio or spending TTS credits.

### Desktop

- [ ] Real Windows GUI.
- [ ] Remote Core authority.
- [ ] Desktop voice input/output.
- [ ] Capability handoff.
- [ ] Sleep/offline UI distinction.
- [ ] Reconnect after Core restart.

## 21. Final unresolved UNKNOWN items

1. Production Core durable-state reconstruction after a real process restart.
2. Hours-scale soak behavior and context trimming under sustained use.
3. Live semantic and episodic memory promotion/retrieval, because production counts remained zero.
4. Full developed-preference promotion and later behavioral influence.
5. Live developed-personality evolution where intentionally supported.
6. Live autonomy proposal persistence/dedupe/prioritization.
7. Attention-event-to-autonomy causal linkage.
8. Real capability node enrollment, work ownership, tool result ingestion, and reconnection.
9. Real Ollama inference and private-route quality.
10. Physical iPhone lifecycle, STT, TTS, and interruption behavior.
11. Physical Windows desktop/node startup, credential storage, reboot, and network recovery.
12. Public deployment TLS/reverse-proxy and distributed telemetry behavior.
13. Shared-work live write/restart/retrieval semantics.
14. Generic client-to-Core network interruption and recovery, separate from explicit OFFLINE control.

## Validation summary

### Production

- Live Core health, state, lifecycle, memory, growth, conversation, nodes, dashboard, and workspace projections.
- Live Mobile health, state, experience, lifecycle, trace, chat, and voice readiness.
- Fifteen accepted production turns.
- Real provider fallback and cooldown.
- Private Ollama-only route isolation.
- Retry/replay, conflicting ID, invalid auth, malformed input.
- Sleep, stale lease, register, wake, renew, OFFLINE, online, disconnect, reconnect.
- Core/Mobile parity snapshots.

### Canonical offline/test

- Focused certification set: **149 passed**.
- Full suite: **1,452 passed, 1 skipped, 1 failed**.
- Sole full-suite failure: uploaded `attached_assets/` directory rejected by repository structure gate.
- Offline release verification: every functional milestone passed; only `pytest` and `repository_structure` failed for the same upload-directory reason.
- State integrity: **10/10** JSON files readable; **18** backup generations.
- Mobile voice readiness: TTS and STT ready; no audio synthesized and no TTS credits spent.

## Final verdict

# PARTIAL

MaryV2 has a live canonical identity and several coherent operational loops, but the required complete learning/developed-self loop, live autonomy proposal chain, production restart reconstruction, and physical capability execution are not yet proven. The evidence does not support either full pass verdict.