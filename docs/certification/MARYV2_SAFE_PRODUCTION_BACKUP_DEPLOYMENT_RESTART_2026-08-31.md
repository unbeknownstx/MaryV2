# MaryV2 Safe Production Backup, Deployment, Restart & Live Learning Certification

**Certification date:** 2026-08-31 America/Los_Angeles  
**Task:** #23  
**Final verdict:** **PRE-DEPLOYMENT BACKUP VERIFIED — DEPLOYMENT AUTHORIZATION REQUIRED**

Task #23 implementation is locally committed and independently reviewed. This
certification document is committed separately after the implementation so it
can record the implementation's immutable Git hash. The exact certification
commit is recorded in the final handoff and is recoverable with:

`git log -1 --format=%H -- docs/certification/MARYV2_SAFE_PRODUCTION_BACKUP_DEPLOYMENT_RESTART_2026-08-31.md`

The reviewed Task #23 history is release-clean.
No GitHub push, Railway deployment, Railway restart, or production learning
experiment was performed. Railway project, service, environment, canonical
volume, active deployment, restart authority, and rollback history are now
verified. Because GitHub `main` triggers Railway deployment, stopping before
push remains required until explicit creator authorization.

The production Core remains healthy on the prior deployment. Its authenticated
Task #23 durable-state endpoint returns HTTP 404, independently confirming that
the new code is not live.

## 1. Task #22 commit hash

`4f21b7b81cbaf0c5fb79cbd44d98623d2b9fcc7f`

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

Authorized Railway inspection established:

- project: `outstanding-charm`;
- service/environment: `MaryV2` / `production`;
- volume: `maryv2-volume`, Ready, 500 MB;
- volume mount: `/data`;
- canonical `MARY_DATA_DIR`: `/data/production-v1`;
- active source: `unbeknownstx/MaryV2`, branch `main`;
- active deployment status: `SUCCESS`;
- active instance status: `RUNNING`.

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

A real production pre-deployment backup was exported from Railway without
deploying or restarting Core. Creator lifecycle was offline, active surfaces and
nodes were zero, and all 12 remote JSON generations had identical SHA-256 values
before and after transfer.

- Backup ID:
  `MaryV2-state-20260901-021008Z-1cf6c48d29a4`
- Format: `maryv2-state-backup-v2`
- Verified: `true`
- File count: `12`
- Total bytes: `72,291`
- Environment secrets included: `false`
- Durable-state fingerprint:
  `1cf6c48d29a41a36ca14fdb36aa884139935c08dc55ca744d74f9b4270b64af6`
- Archive SHA-256:
  `2b064dfa990919a5fa684b7c4cc9ab8505ed50297cc85870574cc4960b237581`
- Remote before/after JSON-set SHA-256:
  `ac22a3dc8380ff70e40c5487514b252660c1d9f997fe8a2ebdf8377c1e394005`
- Sourcebook version: `1.0`
- Sourcebook records: `189`
- Sourcebook hash: `49f3c9963de2b35d108d`

Content-free category summaries:

| Category | Files | Records | Bytes |
|---|---:|---:|---:|
| autonomy | 3 | 0 | 62 |
| developed self | 1 | 5 | 472 |
| engagement | 1 | 6 | 635 |
| growth | 1 | 61 | 58,328 |
| knowledge | 1 | 0 | 114 |
| memory | 1 | 0 | 99 |
| preference candidates | 1 | 0 | 1,391 |
| relationship | 2 | 0 | 2,958 |
| training | 1 | 5 | 8,232 |

The archive and content-free attestation are gitignored, permission mode 0600,
and retained under `backups/production/`. Raw export and restore staging trees
were securely erased after verification. The temporary Railway SSH key was
removed from Railway and the local environment.

## 7. Restore/reconstruction test result

**PASS — real production export and canonical reconstruction**

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
→ quiesced no-deploy production export and verified v2 fingerprint
→ CharacterSourcebook fingerprint
→ verified off-volume backup
→ stage `MARY_BACKUP_DIR` without deploying
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

Authorized Railway deployment metadata proves the deployed revision is:

`4f21b7b81cbaf0c5fb79cbd44d98623d2b9fcc7f`

Active Railway deployment:
`76cc5e90-5f44-4ab9-acf7-de231f521faa`

Active Railway container instance:
`d160b4b5-bb86-415a-9142-5839cda3fe76`

## 10. Pre/post Core instance IDs

Content-free pre-deployment production observation:

- Existing Core instance ID:
  `0a23147b-1afc-4e49-b240-4836b9ab1d57`
- Observed uptime: `1,363.22` seconds
- Railway container instance:
  `d160b4b5-bb86-415a-9142-5839cda3fe76`

Post-deployment instance ID: **not available; no deployment occurred**.  
Post-restart instance ID: **not available; no restart occurred**.

## 11. Pre/post durable-state fingerprints/counts

Production pre-deployment durable fingerprint from the stable, strict v2
off-volume export:

`1cf6c48d29a41a36ca14fdb36aa884139935c08dc55ca744d74f9b4270b64af6`

Production post-deployment fingerprint: **not applicable**.

Production content-free category counts are recorded in section 6. The current
HTTP fingerprint endpoint remains unavailable because Task #23 is not deployed.

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
is not deployed. The verified production backup now exists.

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

**Backup and operator controls verified; deployment authorization pending.**

Documented rollback:

1. stop acceptance and new state writes on mismatch;
2. select the prior known-good Railway deployment and Rollback;
3. restore the verified v2 archive into an empty recovery directory if state is
   wrong;
4. point `MARY_DATA_DIR` to that verified reconstruction before known-good
   deployment;
5. reconstruct and compare fingerprints;
6. report the discrepancy;
7. never manually edit Mary's persistent JSON.

Authorized Railway CLI access verified deployment history, including the active
Task #22 deployment and prior rollback candidates. Railway native volume backup
is unavailable on the current plan, so the off-volume v2 archive is the state
rollback authority.

## 20. Focused test results

- Task #22 focused lifecycle/persistence/security/sourcebook suite before Task
  #23: **74 passed**
- Task #23 broad persistence/developed-self/lifecycle/security/sourcebook
  matrix: **121 passed**
- Final changed backup/recovery/node-trust set: **34 passed**
- Final release-hygiene/structure/backup set: **29 passed**

Independent architect review:

**PASS — the verified no-deploy Railway backup closes the infrastructure/backup
gate; production is correctly blocked solely on explicit creator authorization.**

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

## 23. Creator deployment authorization required

The required production location, backup, manifest/fingerprint, offline
reconstruction, deployment identity, and rollback checks are complete.

**Single creator action required:** authorize execution of the documented
production sequence. That authorization permits:

1. staging `MARY_BACKUP_DIR=/data/production-backups` with
   `--skip-deploys`;
2. pushing the reviewed Task #23 commits to `main`;
3. observing the automatic Railway deployment;
4. running the post-deploy fingerprint, Mobile, live-learning, backup, and
   controlled-restart certification.

Until explicit authorization is received, do not push, deploy, or restart.

# PRE-DEPLOYMENT BACKUP VERIFIED — DEPLOYMENT AUTHORIZATION REQUIRED

Task #23 is release-clean and now has a verified real production pre-deployment
backup. Production deployment, live learning certification, and real restart
persistence remain correctly blocked on explicit creator authorization.