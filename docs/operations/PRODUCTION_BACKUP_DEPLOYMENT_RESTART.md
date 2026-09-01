# MaryV2 Production Backup, Deployment, and Restart Runbook

## Safety boundary

Railway is the hosting provider for the authoritative Core. Authorized
production inspection on 2026-08-31 established project `outstanding-charm`,
service `MaryV2`, environment `production`, branch `main`, volume
`maryv2-volume`, mount `/data`, and canonical `MARY_DATA_DIR`
`/data/production-v1`. A GitHub push triggers a deployment. Therefore **do not
push, deploy, restart, or run live acceptance** until the backup and creator
authorization gates in this runbook are complete.

`MARY_DATA_DIR` is the canonical application state root. `MARY_BACKUP_DIR` is a
separate protected artifact destination. A configured path alone is not proof
that either directory is durable: the Railway service settings and attached
volume are authoritative.

## Production persistence inventory

Paths below are relative to `MARY_DATA_DIR`. Current state files use atomic JSON
writes and recovery generations where their owning store supports them. The
Task #23 archive includes only registered files that exist; an unknown JSON file
under a durable owner root fails the backup rather than being silently omitted.

| State | Storage owner | Physical/backend location | Durability mechanism | Backup mechanism | Reconstruction path |
|---|---|---|---|---|---|
| Episodic, semantic, and working-memory persistence | `MemoryManager` | `memory/memory.json` on the authoritative Railway volume | Atomic JSON and bounded recovery copies | Task #23 v2 archive plus Railway volume backup | `create_application()` configures and loads `MemoryManager` |
| Developed preferences, personality, and values | `DevelopedSelfStateStore` | `personality/developed_self.json` | Atomic JSON | v2 archive + volume backup | Developed-self store loads before turn context compilation |
| Governed preference candidates/evidence | `PreferencePromotionManager` | `personality/preference_promotion.json` | Atomic JSON | v2 archive + volume backup | Promotion ledger loads separately from represented preferences |
| Relationship model/history/milestones | `RelationshipManager` | `relationship/relationship.json` | Atomic JSON | v2 archive + volume backup | `Mary` constructs and loads the relationship manager |
| Creator directives | `CreatorDirectiveStore` | `relationship/creator_directives.json` | Atomic JSON | v2 archive + volume backup | Directive store loads with the canonical relationship system |
| Knowledge learning state | `KnowledgeStateStore` | `knowledge/knowledge.json` | Atomic JSON | v2 archive + volume backup | `create_application()` configures and loads knowledge state |
| Goals | `GoalManager` | `goals/goals.json` | Atomic JSON | v2 archive + volume backup | Canonical agency manager loads from the goals root |
| Intentions | `IntentionManager` | `goals/intentions.json` | Atomic JSON | v2 archive + volume backup | Canonical agency manager loads from the goals root |
| Curiosities | `CuriosityManager` | `goals/curiosities.json` | Atomic JSON | v2 archive + volume backup | Canonical agency manager loads from the goals root |
| Growth journal | `ExperienceJournal` | `development/experience_journal.json` | Atomic JSON | v2 archive + volume backup | Growth system loads the experience journal |
| Conversation engagement policy state | `ConversationEngagement` | `runtime/conversation_engagement.json` | Atomic JSON | v2 archive + volume backup | `create_application()` loads the engagement store |
| Durable device trust | `MaryCoreService` | `runtime/node_enrollment.json` | Atomic JSON | Sanitized v2 export retains trusted-device digests only | New Core loads trust; devices reconnect and receive new sessions |
| Explicit response feedback | `ResponseFeedbackStore` | `training/response_feedback.json` | Atomic JSON | v2 archive + volume backup | Training feedback store loads when present |
| Voice-lab selections | `VoiceLabStore` | `voice/voice_lab.json` when Core and Mobile share this root | Atomic JSON | v2 archive + volume backup | Voice-lab store loads on the owning surface |
| Command Center shared work | `CommandCenter` | `ecosystem/command_center.json` | Atomic JSON | v2 archive + volume backup | `MaryEcosystem` reconstructs around the same Mary |
| Focus state/history | `FocusManager` | `ecosystem/focus.json` | Atomic JSON | v2 archive + volume backup | `MaryEcosystem` reconstructs the focus manager |
| Inbox | `MaryInbox` | `ecosystem/inbox.json` | Atomic JSON | v2 archive + volume backup | `MaryEcosystem` reconstructs the inbox |
| Study projects/cards | `StudyManager` | `ecosystem/study.json` | Atomic JSON | v2 archive + volume backup | `MaryEcosystem` reconstructs the study manager |
| Research threads/notes | `ResearchNotebook` | `ecosystem/research.json` | Atomic JSON | v2 archive + volume backup | `MaryEcosystem` reconstructs the research notebook |
| Production/shared artifacts metadata | `ProductionStudio` | `ecosystem/production.json` | Atomic JSON | v2 archive + volume backup | `MaryEcosystem` reconstructs the production studio |
| Grounded pending thoughts | `PendingThoughtStore` | `ecosystem/presence/pending_thoughts.json` | Atomic JSON with expiry pruning | v2 archive + volume backup | Presence manager reloads unexpired grounded thoughts |
| CharacterSourcebook | `CharacterSourcebook` | Read-only repository/configured authored sources, not mutable Mary state | Versioned authored inputs | Count/version/hash in manifest; source is deployed code/config | Fresh Core rebuilds it and must match the manifest fingerprint |

Shared-work conversational history is also represented by canonical memory and
relationship records. Arbitrary files under `MARY_WORKSPACE_ROOT` are not a
Mary-owned persistence database and are not copied by the state archive.

## Intentionally ephemeral or rebuildable state

The following must be absent after reconstruction:

- creator-surface leases and visibility ownership;
- realtime attention queue/claims;
- provider cooldowns and availability caches;
- raw node tokens, node sessions, session generations, enrollment grants, and
  in-flight/claimed node work;
- request/turn traces and process uptime;
- dialogue-session context where not promoted into a durable owner;
- foreground-window and machine-local capability state;
- runtime metrics;
- the cognitive reservoir and other rebuildable indexes/caches.

The node enrollment file mixes durable and ephemeral fields during normal
operation. Task #23 backup sanitizes it to version and trusted-device digests
with empty grants, audit, and session generations. Raw device credentials and
node tokens are never persisted or exported.

## Backup architecture

### Pre-deployment bootstrap backup

The first safe deployment must be protected before the application endpoint
exists in production. A Railway manual volume backup is preferred. On the
current plan Railway reports **No Backups** and requires a higher plan for
native Backups/PITR, so Task #23 used the no-deploy export fallback below.

Creator/operator must verify:

1. the authoritative Core service and environment;
2. an attached Railway volume;
3. the volume mount path;
4. `MARY_DATA_DIR` resolves inside that mount;
5. either a manual volume backup completes or a no-deploy export is completed
   and transferred off the Railway volume;
6. the prior deployment can be selected for rollback;
7. the operator can deliberately restart the Core service.

If any item is unknown, stop.

#### No-deploy export fallback

When Railway-native backup is unavailable:

1. authenticate Railway CLI without placing a token in source or chat;
2. verify the exact project, service, environment, active deployment, volume,
   mount, and configured `MARY_DATA_DIR`;
3. disconnect creator surfaces, set creator lifecycle offline, and require zero
   connected nodes;
4. record SHA-256 for every JSON generation below `MARY_DATA_DIR`;
5. use Railway's volume file channel to download only the canonical data root to
   a permission-restricted off-Railway staging directory;
6. recompute the remote SHA-256 set and require exact equality;
7. run the Task #23 strict v2 allowlist/secret scan against the stable copy;
8. verify ZIP CRC, manifest hashes, whole-state fingerprint, and sourcebook;
9. restore into an empty offline root and construct a fresh Mary application;
10. retain only the mode-0600 v2 archive and content-free attestation in a
    gitignored, access-controlled backup directory;
11. securely erase raw and restored staging trees;
12. remove temporary SSH authority and return creator lifecycle online.

This fallback occurred on 2026-08-31 without a push, deployment, or Core
restart. The retained archive is off the Railway volume at
`backups/production/MaryV2-state-20260901-021008Z-1cf6c48d29a4.zip`;
it is gitignored and mode 0600.

### Application-level verified backup

After Task #23 code is running:

- `POST /v1/admin/backups` requires the creator bearer token;
- `MARY_BACKUP_DIR` must be configured as protected persistent storage outside
  `MARY_DATA_DIR`;
- the Core holds turn, creator-lifecycle, and node-lifecycle locks while reading;
- the v2 archive contains only registered durable files;
- the manifest records format, file/category counts, bytes, owner/schema
  metadata, per-file SHA-256, a deterministic durable-state fingerprint,
  CharacterSourcebook count/version/hash, and explicit exclusions;
- mixed node state is sanitized to durable trust only;
- archive bytes are rechecked against the manifest before atomic promotion;
- the HTTP response returns only content-free metadata and never an archive
  path, file path, or state values;
- failure removes staging output and leaves canonical state untouched.

`GET /v1/admin/durable-state` returns the current content-free fingerprint,
counts, Core instance ID, and uptime for pre/post comparisons.

For this service, stage `MARY_BACKUP_DIR=/data/production-backups` with
Railway's `--skip-deploys` option before pushing. It is outside canonical
`/data/production-v1` but on the attached volume. Every application backup
needed for disaster recovery must then be exported off that volume and
validated; a same-volume copy alone is not sufficient.

## Offline restore and recovery validation

There is no HTTP restore endpoint.

1. Validate the v2 archive with `python -m scripts.restore_state ARCHIVE`.
2. Restore only into a missing/empty directory:
   `python -m scripts.restore_state ARCHIVE --data-dir NEW_ROOT --apply`.
3. Start a fresh application against `NEW_ROOT`.
4. Run reconstruction verification against the manifest.
5. Confirm developed preferences, relationship, memories, growth, shared work,
   pending thoughts, and durable node trust.
6. Confirm old surface leases, attention, grants, sessions, node tokens,
   in-flight work, provider cooldowns, and traces are absent.
7. Confirm CharacterSourcebook count/version/hash exactly match.

Legacy v1 archives are inspection-only and cannot be applied.

## Controlled production sequence

Record only content-free operational evidence.

1. Record current deployed revision and deployment ID in Railway.
2. Call `/v1/health`; record old Core instance ID and uptime.
3. Call authenticated `/v1/admin/durable-state`; record counts/fingerprints.
4. Record CharacterSourcebook count/version/hash.
5. Require the verified pre-deployment native backup or no-deploy v2 export.
6. Stage `MARY_BACKUP_DIR` without triggering a deployment.
7. Confirm the approved commit and rollback target.
8. Deploy the approved commit through the known Railway deployment control.
9. Wait for `/v1/health` to pass; record new deployment/Core instance and uptime.
10. Call `/v1/admin/durable-state`; require the expected reconstruction
    fingerprint and category counts.
11. Reconnect Mobile and verify one normal creator turn reaches the same Core.
12. Run the five governed production preference observations.
13. Open a fresh conversation and verify retrieval/context/behavior without
    restatement.
14. Create another verified backup.
15. Deliberately restart the Core.
16. Require another new instance ID, matching durable fingerprint, cleared
    ephemeral state, Mobile reconnection, preference retrieval, and measurable
    behavioral influence.

## Rollback

If health, reconstruction, fingerprints, counts, or sourcebook checks disagree:

1. stop acceptance testing and avoid further canonical writes;
2. use Railway **Deployments → last known-good deployment → Rollback**;
3. if native backup exists and state itself is wrong, restore the verified
   Railway volume backup and review the staged volume change before deploying
   it;
4. if native backup is unavailable, restore the verified v2 archive offline
   into a new empty directory on the volume, point `MARY_DATA_DIR` to that
   reconstruction, and deploy only the known-good code;
5. reconstruct and compare fingerprints again;
6. report the discrepancy;
7. never repair Mary by editing persistent JSON manually.

Railway documents that a code rollback restores a previous deployment image and
variables as a new active deployment. Railway volume restore stages a replacement
volume and redeploys the service; the previous volume remains retained but
unmounted.

## Current manual gate

The authoritative production location, restart control, and rollback history
are now verified. A stable off-volume v2 backup and offline reconstruction proof
are complete. Production still runs Task #22 commit
`4f21b7b81cbaf0c5fb79cbd44d98623d2b9fcc7f`; Task #23 is not deployed.

**Single creator action required:** explicitly authorize execution of the
controlled production sequence beginning with staging `MARY_BACKUP_DIR` using
`--skip-deploys`, then pushing the reviewed Task #23 commits. Until that
authorization is received, do not push, deploy, or restart.

## Railway references

- Volume backups: <https://docs.railway.com/volumes/backups>
- Volumes and mount paths: <https://docs.railway.com/volumes>
- Rollback/restart operations:
  <https://docs.railway.com/guides/roll-back-bad-deploy>