# State, Development History, and Recovery

## Source vs runtime state

The repository contains code and authored project material. Mutable Mary state belongs outside the source tree by default.

Resolution order:

1. explicit `MARY_DATA_DIR`, if configured;
2. portable application-local data when `MARY_PORTABLE=1`;
3. host-native MaryV2 application-data directory.

On Windows the normal default is `%LOCALAPPDATA%\MaryV2\data`.

## Historical development state

Repository-local `data/` accumulated during 1.x–15.x development was test/development conversation state. It is intentionally excluded from the professional source tree. Historical state must be reviewed deliberately rather than promoted based only on location or timestamp.

Historical state must never be promoted into production continuity merely because it exists or has a newer timestamp.

## Migrating legacy repository state

Use the cross-platform migration command from the repository root:

```text
python -m scripts.migrate_repo_state
```

Dry-run is the default. It resolves the canonical destination through
`MARY_DATA_DIR`, portable mode, or the host-native default and reports file
counts and path conflicts without changing either location.

After closing Mary, apply the verified migration explicitly:

```text
python -m scripts.migrate_repo_state --apply
```

Apply mode creates a staged copy, uses SQLite's backup API for WAL-mode
databases, verifies exact file hashes and SQLite integrity, and only then
installs the result. A non-empty existing destination is preserved beside the
canonical data directory as `data.before_repo_migration_<timestamp>`. The
repository source remains in place unless `--remove-source` is also explicitly
requested after review. Explicit cleanup begins only after the canonical copy
passes final verification. It first retires the legacy directory by an atomic
same-parent rename, takes a fresh snapshot, and compares that snapshot with the
installed manifest. It never physically deletes the retired state
automatically. If a late write is detected, the command returns a warning and
retains that write in the reported hidden quarantine. Review and delete the
reported retired directory manually only after confirming Mary uses the
canonical destination and no newer state needs reconciliation.

Windows users may continue using
`scripts\migrate_repo_state_windows.ps1`; it delegates to the same Python
safety implementation.

## Recovery layers

A recoverable Mary consists of:

- Git/source repository,
- approved creator-authored character sources,
- durable continuity state,
- separately stored secrets/credentials,
- recoverable project assets,
- rebuildable caches/indexes.

Use `mary.runtime.recovery` and the recovery scripts for secret-free manifests/snapshots. Keep off-device backups for any future continuity state that becomes meaningful.


## Selective local-continuity reconciliation

When Desktop has moved to a remote canonical Mary Core, older creator-owned
Windows/macOS application data may contain valid continuity that was never
migrated to Core. Do **not** copy that old data directory over the live Core
root.

First run the content-free audit:

\`\`\`text
python -m scripts.audit_local_continuity
\`\`\`

If a recoverable candidate exists, preview the deterministic merge:

\`\`\`text
python -m scripts.recover_local_continuity
\`\`\`

Preview is authenticated but non-mutating. It sends only the registered
MemoryManager and RelationshipManager durable owners to Core and returns counts
for additions, duplicates, ID collisions and creator-profile conflicts. It
never imports working memory, cognitive-reservoir indexes, provider/runtime
state, node leases, credentials, traces or workspace caches.

The canonical merge policy is:

- current Core state wins conflicting current scalar creator facts/preferences;
- older conflicting values may survive only as historical source-aware profile
  evidence;
- exact duplicates are skipped;
- unique episodic, semantic, relationship-history, profile, milestone and
  relationship-understanding records can be added;
- IDs are preserved when unique and deterministically renamed only for a real
  ID collision;
- the local source root remains unchanged.

Apply is deliberately two-step. Core returns the current durable-state
fingerprint during preview. Mutation is accepted only when that same
fingerprint is still current, the exact creator confirmation is supplied, and
Core can create/verify a normal protected durable backup first.

After reviewing the preview:

\`\`\`text
python -m scripts.recover_local_continuity --apply --confirm MERGE_LOCAL_CONTINUITY
\`\`\`

If \`MARY_BACKUP_DIR\` is not configured on canonical Core, apply is refused.
Configure the protected Core backup destination, redeploy, and preview again.
A changed Core fingerprint also refuses apply and requires a fresh preview.
