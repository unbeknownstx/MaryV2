# MaryV2 Safe Production Backup, Deployment, Restart & Live Learning Certification

**Certification date:** 2026-08-31 America/Los_Angeles  
**Task:** #23  
**Final verdict:** **DEPLOYMENT READY — MANUAL ACTION REQUIRED**

Task #23 implementation is locally committed and independently reviewed. This
certification document is committed separately after the implementation so it
can record the implementation's immutable Git hash. The exact certification
commit is recorded in the final handoff and is recoverable with:

`git log -1 --format=%H -- docs/certification/MARYV2_SAFE_PRODUCTION_BACKUP_DEPLOYMENT_RESTART_2026-08-31.md`

The full two-commit Task #23 history is release-clean.
No GitHub push, Railway deployment, Railway restart, or production learning
experiment was performed because the environment has no verified Railway
project/service/volume/restart/rollback authority. A push may trigger an
automatic Railway deployment, so stopping before push is the required safe
behavior.

The production Core remains healthy on the prior deployment. Its authenticated
Task #23 durable-state endpoint returns HTTP 404, independently confirming that
the new code is not live.

## 1. Task #22 commit hash

`4f21b7bd47e41699312276483d4becb8f797aafd`

Short revision: `4f21b7b`  
Commit title: `Update agent growth logic and preference evidence processing`

At the Task #23 start, this was both local `HEAD` and `origin/main`. The Task
#22 files, report, tests, and attached specification were present in that clean
commit.

## 2. Task #23 implementation commit hash

`b6f121ebe4a2a89229201a0c81ded74213435ff8`

Short revision: `b6f121e`  
Commit title: `Add safe production backup and recovery workflow`

This implementation commit is local only. The certification report is the next
local commit. Git commits cannot embed their own hash because the hash is
derived from the committed file contents; the final handoff records that second
exact hash and the command above resolves it reproducibly.

## 3. Release-gate result

**PASS**

- Repository structure policy now permits only the reserved root
  `attached_assets/` for preserved user/task upload staging.
- Runtime state roots such as `data/`, `payload/`, and `upgrade_backups/`
  remain forbidden.
- Regression coverage proves upload staging is allowed while runtime roots and
  generated state reports remain rejected.
- Release hygiene continues scanning source/config for real assignments while
  narrowly recognizing Replit's generated
  `.agents/agent_assets_metadata.toml` `storage_version_token` as object
  metadata, not an authentication secret.
- The exact same assignment outside that generated metadata path still fails.
- Composite deterministic/offline release verification: **PASS**.

## 4. Production persistence inventory

The complete owner/path/durability/backup/reconstruction matrix is:

`docs/operations/PRODUCTION_BACKUP_DEPLOYMENT_RESTART.md`

Registered durable categories:

- episodic/semantic/working memory persistence;
- developed preferences/personality/values;
- governed preference candidates/evidence;
- relationship state/history/milestones;
- creator directives;
- knowledge state;
- goals, intentions, and curiosities;
- growth journal;
- conversation engagement policy state;
- durable node trust;
- response feedback;
- voice-lab state when owned by the shared root;
- Command Center, focus, inbox, study, research, and production shared work;
- grounded persistent pending thoughts.

CharacterSourcebook remains a read-only repository/configuration authority. It
is fingerprinted in the manifest and reconstructed from deployed authored
sources; it is not copied into mutable Mary state.

**Unresolved production fact:** repository code cannot prove the Railway volume
mount or whether production `MARY_DATA_DIR` is inside it. Railway service
settings are authoritative.

## 5. Backup architecture

Task #23 replaces recursive “copy every data file” behavior with a strict v2
allowlist:

`maryv2-state-backup-v2`

Properties:

- canonical files only;
- unknown JSON under durable owner roots fails closed;
- environment/provider credentials and credential-like JSON fields fail closed;
- symlink/path escape is rejected;
- source code and arbitrary workspace files are excluded;
- reservoir/index/cache state is excluded;
- node enrollment state is sanitized to trusted-device digests only;
- grants, grant audit, session generations, live node tokens, and work ownership
  are absent;
- deterministic file/category metadata and durable-state fingerprint;
- CharacterSourcebook version/count/hash;
- archive bytes are rechecked against the initial manifest to detect a write
  race;
- staging failure deletes only temporary output and leaves canonical state
  untouched;
- offline v2 restore only, into an empty target;
- legacy v1 archives are inspection-only.

Core operations:

- `POST /v1/admin/backups`: creator-authenticated backup trigger;
- `GET /v1/admin/durable-state`: creator-authenticated content-free live
  fingerprint, category counts, Core instance ID, and uptime;
- no HTTP restore endpoint;
- no archive download endpoint;
- ordinary responses expose no state values or archive/file paths.

Production `POST /v1/admin/backups` additionally requires `MARY_BACKUP_DIR` to
name protected persistent storage outside `MARY_DATA_DIR`.

## 6. Backup manifest/fingerprint result

A real local backup was created against the configured Mary data root after the
implementation commit and independently inspected.

- Backup ID:
  `MaryV2-state-20260901-014729Z-fcb53636e6ea`
- Format: `maryv2-state-backup-v2`
- Verified: `true`
- File count: `10`
- Total bytes: `21,615`
- Environment secrets included: `false`
- Durable-state fingerprint:
  `fcb53636e6ea2394c3dfb05386890b3d57b3ae9124839432662d2b69b74d4166`
- Sourcebook version: `1.0`
- Sourcebook records: `189`
- Sourcebook hash: `49f3c9963de2b35d108d`

Content-free category summaries:

| Category | Files | Records | Bytes |
|---|---:|---:|---:|
| autonomy | 2 | 0 | 39 |
| developed self | 1 | 5 | 472 |
| engagement | 1 | 6 | 277 |
| growth | 1 | 8 | 6,379 |
| preference candidates | 1 | 0 | 335 |
| relationship | 2 | 0 | 12,732 |
| training | 1 | 1 | 905 |
| voice | 1 | 1 | 476 |

This is local state evidence, not a Railway production backup.

## 7. Restore/reconstruction test result

**PASS — canonical production-equivalent composition**

The test performs:

creator preference observations
→ governed promotion
→ persisted memory/relationship/growth/developed self
→ shared Command Center work
→ grounded pending thought
→ v2 backup
→ verified empty-target restore
→ fresh application construction
→ equal durable fingerprint
→ equal sourcebook
→ active developed preference
→ recovered memory/relationship/growth/shared work/pending thought

Additional recovery results:

- corrupt hash fails safely;
- corrupt durable-state fingerprint fails safely;
- sourcebook mismatch fails reconstruction verification;
- sensitive state field fails backup without modifying source state;
- unclassified durable JSON fails closed;
- nonempty restore target is rejected;
- backup output inside `MARY_DATA_DIR` is rejected;
- canonical identity remains singular through fresh construction.

## 8. Exact deployment/restart procedure

The exact procedure and rollback gate are documented in:

`docs/operations/PRODUCTION_BACKUP_DEPLOYMENT_RESTART.md`

Required sequence:

pre-deployment health
→ current deployment/Core instance/uptime
→ authenticated durable fingerprint
→ CharacterSourcebook fingerprint
→ verified Railway manual volume backup
→ optional verified application v2 backup when available
→ approved commit and rollback target
→ deploy
→ health/new instance
→ durable fingerprint comparison
→ Mobile reconnect
→ normal turn
→ five governed learning observations
→ fresh-conversation retrieval/behavior
→ fresh verified backup
→ deliberate restart
→ new instance/fingerprint/retrieval/behavior
→ expected ephemeral clearing

## 9. Deployed revision

**Not deployed.**

Production read-only evidence:

- `/v1/health`: HTTP 200
- service: `mary-core`
- architecture: `13.2`
- protocol: `1`
- `/v1/admin/durable-state`: HTTP 404

The 404 proves the production process does not contain Task #23.

The deployed Git revision is not exposed by the current Core and cannot be
obtained without Railway deployment metadata. It must not be guessed from
`origin/main`.

## 10. Pre/post Core instance IDs

Content-free pre-deployment production observation:

- Existing Core instance ID:
  `0a23147b-1afc-4e49-b240-4836b9ab1d57`
- Observed uptime: `1,363.22` seconds

Post-deployment instance ID: **not available; no deployment occurred**.  
Post-restart instance ID: **not available; no restart occurred**.

## 11. Pre/post durable-state fingerprints/counts

Production pre-deployment fingerprint: **unavailable on the current revision**;
the authenticated endpoint returns 404.

Production post-deployment fingerprint: **not applicable**.

Production memory/developed-self/growth/relationship/shared-work category
counts: **not collected**, because the safe content-free endpoint is not
deployed and raw/private state must not be inferred or exposed.

The local verified fingerprint/count result is recorded in section 6.

## 12. Expected ephemeral-state clearing

Offline recovery tests prove absence/non-resurrection of:

- surface leases;
- attention queue state;
- provider cooldown state;
- request/turn traces;
- reservoir/rebuildable state;
- node sessions;
- node session generations;
- enrollment grants;
- old node tokens;
- in-flight/claimed work ownership.

Durable node trust is preserved. A restored Core rejects the pre-backup
enrollment grant and old node token, accepts the correct durable device proof,
and issues a new node token at a fresh session generation.

Railway production clearing remains unexecuted.

## 13. Production learning candidate progression

**Not executed.**

No Task #22 preference experiment was repeated against Railway because Task #23
is not deployed and no verified production backup exists.

Required progression after the manual gate:

1 deferred
→ 2 deferred
→ 3 eligible/base gate deferred
→ 4 eligible/base gate deferred
→ 5 automatic promotion if unchanged policy is satisfied.

## 14. Production promotion result

**Not executed.**

No production threshold, candidate, or represented preference was manipulated.

## 15. Fresh-session retrieval result

Production: **not executed**.  
Canonical production-equivalent backup/reconstruction test: **PASS**.

The restored fresh application has one active developed interaction preference
without creator restatement.

## 16. Measured production behavioral influence

Production: **not executed**.

Task #22 canonical production-equivalent evidence remains:

- baseline: `251` characters;
- developed-self influenced output: `40` characters;
- reduction: `84.1%`.

Task #23 proves that promoted state survives v2 backup, offline restore, and
fresh application reconstruction. It does not relabel that evidence as
production.

## 17. Post-restart developed-preference retrieval result

Railway: **not executed**.

Offline fresh-process reconstruction: **PASS**. The active promoted preference
is present after backup/restore/new application construction.

The real Railway restart is intentionally still missing.

## 18. CharacterSourcebook pre/post hash/count

Local pre/post reconstruction:

- version: `1.0` → `1.0`
- records: `189` → `189`
- hash: `49f3c9963de2b35d108d` →
  `49f3c9963de2b35d108d`
- load errors: `0`

Production post-deployment/post-restart: **not applicable**.

## 19. Rollback readiness

**Procedure ready; operator control unverified.**

Documented rollback:

1. stop acceptance and new state writes on mismatch;
2. select the previous known-good Railway deployment and Rollback;
3. restore the verified Railway volume backup if state is wrong;
4. review Railway's staged replacement-volume change before deploying it;
5. reconstruct and compare fingerprints;
6. report the discrepancy;
7. never manually edit Mary's persistent JSON.

The environment has no Railway dashboard/CLI authority to verify or execute
these controls.

## 20. Focused test results

- Task #22 focused lifecycle/persistence/security/sourcebook suite before Task
  #23: **74 passed**
- Task #23 broad persistence/developed-self/lifecycle/security/sourcebook
  matrix: **121 passed**
- Final changed backup/recovery/node-trust set: **34 passed**
- Final release-hygiene/structure/backup set: **29 passed**

Independent architect review:

**PASS — locally release-ready, with production correctly blocked.**

## 21. Full-suite result

**1,469 passed, 1 skipped, 0 failed**

The former `attached_assets/` structure failure is resolved narrowly without
deleting user uploads or allowing runtime state in the source tree.

## 22. Release-verification result

**PASS**

`python -m scripts.run_release_verification`

All listed deterministic/offline gates passed, including:

- compile;
- pytest;
- diagnostics;
- memory restart;
- provider resilience/routing;
- lifecycle/developed-self/preference promotion;
- resource governance;
- persistence recovery/state integrity;
- release hygiene;
- repository structure;
- local safety.

Final output:

`Release verification PASSED (deterministic/offline gate).`

## 23. Creator/manual Railway action required

**Single creator action required:**

In the authoritative Railway Core service, complete the seven
“Railway-native first backup” checks in
`docs/operations/PRODUCTION_BACKUP_DEPLOYMENT_RESTART.md`, create the manual
volume backup, and return only this non-secret evidence:

1. Railway service/environment name;
2. attached volume mount path;
3. confirmation that `MARY_DATA_DIR` resolves inside that volume;
4. `MARY_BACKUP_DIR` path relationship showing it is protected and outside
   `MARY_DATA_DIR`;
5. completed manual volume-backup timestamp/status;
6. current deployment/revision ID;
7. confirmation that deliberate restart and previous-deployment rollback
   controls are available.

Do not provide tokens, credentials, secret values, or state contents.

Once this evidence is supplied, execute the documented sequence beginning with
the verified backup. Do not push first.

# DEPLOYMENT READY — MANUAL ACTION REQUIRED

Task #23 is locally complete and release-clean. Production deployment, live
learning certification, and real restart persistence remain correctly blocked
on one explicit Railway operator action.