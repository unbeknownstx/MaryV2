# State, Development History, and Recovery

## Source vs runtime state

The repository contains code and authored project material. Mutable Mary state belongs outside the source tree by default.

Resolution order:

1. explicit `MARY_DATA_DIR`, if configured;
2. portable application-local data when `MARY_PORTABLE=1`;
3. host-native MaryV2 application-data directory.

On Windows the normal default is `%LOCALAPPDATA%\MaryV2\data`.

## Historical development state

Repository-local `data/` accumulated during 1.x–15.x development was test/development conversation state. It is intentionally excluded from the professional source tree. The migration tool backs any existing repo-local `data/` up outside the repository before removal.

Historical state must never be promoted into production continuity merely because it exists or has a newer timestamp.

## Recovery layers

A recoverable Mary consists of:

- Git/source repository,
- approved creator-authored character sources,
- durable continuity state,
- separately stored secrets/credentials,
- recoverable project assets,
- rebuildable caches/indexes.

Use `mary.runtime.recovery` and the recovery scripts for secret-free manifests/snapshots. Keep off-device backups for any future continuity state that becomes meaningful.
