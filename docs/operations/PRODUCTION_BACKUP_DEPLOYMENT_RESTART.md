# MaryV2 Production Backup, Deployment, and Restart Runbook

## Safety boundary

Railway is the hosting provider for the authoritative Core, but repository
configuration does not identify the Railway project, service, environment,
branch binding, attached volume, or volume mount path. A GitHub push may trigger
a deployment. Therefore **do not push, deploy, restart, or run live acceptance**
until the Railway checks in this runbook are complete.

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

### Railway-native first backup

The first safe deployment must be protected by a Railway manual volume backup,
because the application endpoint cannot exist in production before the code
containing it is deployed. Railway documents that a mounted volume can be
manually backed up and restored from the service **Backups** tab.

Creator/operator must verify:

1. the authoritative Core service and environment;
2. an attached Railway volume;
3. the volume mount path;
4. `MARY_DATA_DIR` resolves inside that mount;
5. a manual volume backup completes successfully and its timestamp is recorded;
6. the prior deployment can be selected for rollback;
7. the operator can deliberately restart the Core service.

If any item is unknown, stop.

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
5. Create and verify a Railway manual volume backup.
6. Create and verify an application v2 backup if Task #23 is already deployed.
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
3. if state itself is wrong, restore the verified Railway volume backup and
   review the staged volume change before deploying it;
4. reconstruct and compare fingerprints again;
5. report the discrepancy;
6. never repair Mary by editing persistent JSON manually.

Railway documents that a code rollback restores a previous deployment image and
variables as a new active deployment. Railway volume restore stages a replacement
volume and redeploys the service; the previous volume remains retained but
unmounted.

## Current manual gate

This environment has no Railway project/service/environment identifiers, linked
CLI context, or restart/rollback authority. GitHub `main` may be bound to
automatic Railway deployment, so even a push is unsafe before that is known.

**Single creator action required:** in the authoritative Railway Core service,
complete the seven “Railway-native first backup” checks above, create the manual
volume backup, and return the non-secret evidence (service/environment name,
volume mount path, `MARY_DATA_DIR` and `MARY_BACKUP_DIR` path relationship,
backup completion timestamp, current deployment/revision ID, and confirmation
that restart and rollback controls are available).

Do not provide tokens, credentials, secret values, or state contents.

## Railway references

- Volume backups: <https://docs.railway.com/volumes/backups>
- Volumes and mount paths: <https://docs.railway.com/volumes>
- Rollback/restart operations:
  <https://docs.railway.com/guides/roll-back-bad-deploy>