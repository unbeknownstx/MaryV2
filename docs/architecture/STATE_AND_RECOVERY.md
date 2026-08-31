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
