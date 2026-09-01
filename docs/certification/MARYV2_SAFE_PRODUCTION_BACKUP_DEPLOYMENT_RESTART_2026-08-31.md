# MaryV2 Safe Production Backup, Deployment, Restart & Live Learning Certification

**Certification date:** 2026-08-31 America/Los_Angeles  
**Task:** #23  
**Final verdict:** **CERTIFIED — DEPLOYED, BACKED UP, LEARNED, AND RESTART-STABLE**

## 1. Immutable revisions

- Task #22:
  `4f21b7b81cbaf0c5fb79cbd44d98623d2b9fcc7f`
- Task #23 implementation:
  `b6f121ebe4a2a89229201a0c81ded74213435ff8`
- Original certification:
  `a7359674224d0e2aa6446f11786f18271ca4a67c`
- Library registration:
  `6f270e589920077272e85339dcec8241cbf5e046`
- Verified pre-deployment production backup evidence:
  `65b654bc230356f7294e77fd604cde411dc38bd6`
- Restart-stable engagement backup projection:
  `0767b44b2662081dac16a167d027b92cf8397dbd`

Production and the controlled restart both used exact code revision
`0767b44b2662081dac16a167d027b92cf8397dbd`.

## 2. Release gates and independent review

**PASS**

- Narrow `attached_assets/` staging exception passed.
- Strict release hygiene and repository structure passed.
- Focused engagement/backup/restore/protocol suite: **19 passed**.
- Complete deterministic/offline release verification: **PASS**.
- Existing pre-fix full-suite baseline: **1,469 passed, 1 skipped**.
- Two new projection/backward-compatibility regressions also passed inside the
  complete release verification.
- Independent architecture review: **PASS**.

The reviewer agreed that projection version 2 aligns backup semantics with
`ConversationEngagement.load()`, preserves old v2 archive validation through
projection version 1, fails safely on invalid JSON/schema, and makes the forward
fix safer than rolling back to code that would repeat the same normalization.

## 3. Production persistence and backup policy

Canonical production state:

- Railway project: `outstanding-charm`
- service/environment: `MaryV2` / `production`
- volume: `maryv2-volume`
- volume mount: `/data`
- canonical root: `/data/production-v1`
- protected application backup root: `/data/production-backups`

The `maryv2-state-backup-v2` format remains a strict allowlist. It excludes
credentials, workspace/source files, caches, reservoir indexes, leases,
provider cooldowns, node sessions/tokens/grants, in-flight work, and traces.
Unknown JSON under durable owner roots fails closed.

Projection version 2 additionally canonicalizes
`runtime/conversation_engagement.json`:

- preserved: mode, active session, thread, turns remaining, start time, stats;
- cleared: `last_plan`, `last_question_asked`;
- reason: those planner observations are process-local and intentionally not
  reconstructed by `ConversationEngagement.load()`.

Old Task #23 v2 archives without a projection field remain verifiable and
reconstructable with projection version 1.

## 4. Verified raw pre-deployment production backup

The creator lifecycle was taken offline for the export. Production reported
zero surfaces and zero nodes. All 12 JSON generations had identical hashes
before and after transfer.

- Backup ID:
  `MaryV2-state-20260901-021008Z-1cf6c48d29a4`
- Files/bytes: `12` / `72,291`
- Raw fingerprint:
  `1cf6c48d29a41a36ca14fdb36aa884139935c08dc55ca744d74f9b4270b64af6`
- Archive SHA-256:
  `2b064dfa990919a5fa684b7c4cc9ab8505ed50297cc85870574cc4960b237581`
- Remote JSON-set SHA-256:
  `ac22a3dc8380ff70e40c5487514b252660c1d9f997fe8a2ebdf8377c1e394005`
- CharacterSourcebook:
  version `1.0`, 189 records, hash `49f3c9963de2b35d108d`
- Secret scan, ZIP CRC, empty-root restore, fresh Mary reconstruction:
  **PASS**

The archive and content-free attestation are gitignored, mode 0600, and retained
under `backups/production/`. Export/restore staging and the temporary Railway
SSH key were securely removed.

## 5. First deployment stop condition and root cause

GitHub `main` advanced atomically from Task #22 to
`65b654bc230356f7294e77fd604cde411dc38bd6`. Railway deployed:

- deployment:
  `3fecf94f-8293-496f-93bd-190f4248cf4f`
- Core instance:
  `88071a41-a7b4-4c5e-b0f7-2ae584e1b2db`
- startup logs: clean

The mandatory fingerprint gate stopped before any creator or learning turn:

- expected raw fingerprint:
  `1cf6c48d29a41a36ca14fdb36aa884139935c08dc55ca744d74f9b4270b64af6`
- live raw fingerprint:
  `b1b541a51d8ca1771fe67ce88539b4b31be2be96dc068a9efaf7b3386f9ebf4f`
- file count: unchanged at 12
- only category difference:
  engagement 635 bytes → 277 bytes

Offline replay of the retained archive through `ConversationEngagement.load()`
produced exactly 277 bytes and the exact live whole-state fingerprint. The only
structural change was removal of values under `last_plan`.

CharacterSourcebook never diverged:

- version `1.0`
- records `189`
- hash `49f3c9963de2b35d108d`
- errors `[]`

This was a durable-fingerprint policy defect, not state loss. No rollback was
performed because old code would repeat the same restart normalization.

## 6. Projection-v2 correction and replacement deployment

The corrected offline projection of both raw and restart-normalized state is:

`69c651a812dd59890d5e92804c5f5049f277683bd118744c635c5bcbdad32fe1`

A projected recovery archive was created and independently restored:

- backup:
  `MaryV2-state-20260901-023026Z-69c651a812dd`
- files/bytes: `12` / `71,867`
- archive SHA-256:
  `c7ff4af989142eb856e7d5836b328a3d237091766cd0b58bc7d3ff831a833756`
- reconstruction: **PASS**

GitHub `main` then advanced non-force by exactly commit `0767b44b…`.
Railway deployed:

- corrected deployment:
  `cf59e603-e011-4940-8d8d-bb6a1b315027`
- corrected Core:
  `26582d65-df81-462b-94a2-b84e5ed89d71`
- projection version: `2`
- live fingerprint:
  `69c651a812dd59890d5e92804c5f5049f277683bd118744c635c5bcbdad32fe1`
- files/bytes: `12` / `71,867`
- startup logs: clean
- sourcebook: exact match

No turn was sent until every corrected gate passed.

## 7. Mobile reconnect and ordinary baseline turn

The local Mobile workflow reconnected as a remote-Core client. One ordinary
non-learning turn used a fresh conversation and the prompt:

`How should I plan tomorrow?`

- request:
  `request_1d50c4c2953d456cbc136c07b719c899`
- turn:
  `turn_ae016f5ec9d9424d956f7bc689780e1b`
- response: 156 words / 907 characters
- growth disposition: `not_applicable`

This became the bounded behavioral baseline.

## 8. Five valid production observations

The retained production backup already contained two qualifying direct creator
observations for `creator interaction response length`:

1. `creator_turn_da7e85d3ced51dcd25b190a7f57c1835`
   - source: `creator_explicit_preference`
   - confidence/strength: `0.96` / `0.88`
2. `creator_turn_142e777067ee3dd00a0e4aa0d109475c`
   - source: `creator_corrective_feedback`
   - confidence/strength: `0.92` / `0.82`

They were preserved rather than deleted or reset. Three additional valid direct
creator observations completed the total of five:

3. `creator_turn_90a1a67fe50bc95c78cc1ff89211ce92`
   - candidate count: 3
   - state: eligible
   - promotion: deferred
4. `creator_turn_0977044f48dac93e077f7f321f27d4b6`
   - candidate count: 4
   - state: eligible
   - promotion: deferred
5. `creator_turn_24f241f7739afa82e8e42228ea6b9098`
   - disposition/result: promoted

The new narrow wording was:

`I prefer concise responses by default.`

Local extraction proved it produces only `response_length`; the broader phrase
containing “actionable” would also have created an unrelated directness
candidate and was not used.

One intervening provider generation failed internally:

- turn: `turn_a8bd6387ae1946ab9bc27038e8864ad2`
- block reason: `failed_turn`
- durable observation count remained 4

The policy correctly refused to learn from that failed turn. It is not counted
among the five valid observations.

Final promotion:

- candidate:
  `preference_candidate_61c393c0978673d0ce2a2908`
- developed preference:
  `developed_preference_cc60f5a44c9b9bbc45f1812c`
- state: `active`
- promotions: exactly one
- remaining candidates: zero

## 9. Fresh-session behavioral proof

Without restating the preference, a fresh conversation repeated the baseline
prompt:

- pre-promotion baseline: 156 words
- post-promotion/pre-restart: 116 words
- reduction: 40 words / 25.6%
- request:
  `request_72dfee076772491d846f83898305dd59`
- turn:
  `turn_645e7900e9c94e0d8b65afe1bdab2e82`
- preference evidence from the prompt: `not_applicable`
- developed preference active: yes
- pending candidate: no

## 10. Verified post-learning production backup

Before restart, production created:

- backup:
  `MaryV2-state-20260901-023710Z-171e4c969ccb`
- projection version: `2`
- files/bytes: `12` / `80,301`
- durable fingerprint:
  `171e4c969ccb6084ddac429fec811a8243e86cb2e6a9b12915cfab012befcf62`
- archive SHA-256, remote and local:
  `c5512eab0dc14472d15646e51e95e1bb9f46aea00f77286eccf424c0895f89ea`
- sourcebook:
  version `1.0`, 189 records, hash `49f3c9963de2b35d108d`
- ZIP CRC, strict manifest, empty-root restore, fresh Mary reconstruction:
  **PASS**
- reconstructed developed preference: active

The temporary Railway SSH key was removed from Railway and securely erased.

## 11. Controlled Railway restart

Railway redeployed the existing successful deployment without pulling a new
source revision:

- old deployment:
  `cf59e603-e011-4940-8d8d-bb6a1b315027`
- controlled restart deployment:
  `bc77b19a-72aa-40de-9d4e-26fe9f248e06`
- exact revision:
  `0767b44b2662081dac16a167d027b92cf8397dbd`
- pre-restart Core:
  `26582d65-df81-462b-94a2-b84e5ed89d71`
- post-restart Core:
  `17f25055-a4cd-4a04-bf4f-a9a16d2fea2d`
- startup logs: clean

Before any post-restart turn:

- fingerprint: exact `171e4c96…cf62` match
- files/bytes: exact 12 / 80,301 match
- every category: exact match
- sourcebook: exact match, zero errors
- developed preference: active with the same stable ID
- candidates: zero
- runtime turn count: 6 → 0
- connected/registered compute nodes: 0 / 0
- queued work: 0
- provider cooldowns: 0

The compatibility `preference_promotions` counter reset from 1 to 0 as designed;
its documented scope is `current_core_process`. Durable developed preference
count remained 1.

Terminal automatically established a new process-local lease. Mobile was then
explicitly registered on the restarted Core, producing two current surfaces.
This is reconnection, not restoration of an old lease.

## 12. Post-restart retrieval and behavior

Another fresh conversation repeated the baseline prompt without restating the
preference:

- response: 73 words / 404 characters
- reduction from pre-promotion baseline: 83 words / 53.2%
- request:
  `request_0e6ee9a585024d779229b255bff857ae`
- turn:
  `turn_f62c60b952454e9697a98b31eb7f33e8`
- developed preference: active with the same stable ID
- durable developed preference count: 1
- pending candidates: zero
- preference evidence from the prompt: `not_applicable`
- Mobile reconnect: verified

## 13. Rollback readiness

No rollback was required.

The last known-good pre-Task-23 Railway deployment remains:

`76cc5e90-5f44-4ab9-acf7-de231f521faa`

Railway CLI 5.47.1 does not provide a rollback subcommand. The documented
rollback is Railway **Deployments → select known-good deployment → Rollback**.
Do not substitute `redeploy` for rollback and do not force-rewind GitHub.

State rollback authorities:

1. raw verified production archive `MaryV2-state-20260901-021008Z-…`;
2. projected pre-learning archive `MaryV2-state-20260901-023026Z-…`;
3. verified post-learning archive `MaryV2-state-20260901-023710Z-…`.

Restore remains offline-only into an empty target; persistent JSON is never
manually edited.

## 14. Final verdict

# CERTIFIED — DEPLOYED, BACKED UP, LEARNED, AND RESTART-STABLE

Task #23 preserved Task #22, corrected the narrow repository gate, inventoried
production persistence, implemented authenticated content-safe v2 backups,
proved offline restoration and fresh reconstruction, documented deployment and
rollback, deployed the approved revisions, completed exactly five valid
governed observations, promoted the concise-response preference once, exported
a verified post-learning backup, and proved exact durable fingerprint and
learned behavior across a real Railway Core restart.