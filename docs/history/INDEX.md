# MaryV2 Historical Archive

Historical 1.x–15.x development material is preserved here for provenance and archaeology. It is **not current runtime authority**.

Current authority lives in `README.md`, `MARY_ROOT.md`, `docs/architecture/SYSTEM_REGISTRY.md`, current code, and current tests.

## Archive groups

- `root-archive/release-notes/` — old release notes, migrations, convergence reports, start-here/checkpoint files.
- `root-archive/stages/` — stage/breakthrough documents and manifests.
- `root-archive/patches/` — historical patch/hotfix/diff artifacts.
- `root-archive/installers/` — superseded installers/setup/rollback/verification wrappers.
- `root-archive/manifests/` — old package manifests/checksums.
- `root-archive/mobile-desktop/` — versioned surface notes.
- `development-prompts/` — historical development prompts imported with the repo.
- `architecture/` and `releases/` — older docs moved from formerly active documentation folders.

## Deliberately removed from the active source tree

Duplicate code payloads, upgrade backups, tracked dependency output (`desktop/node_modules`), repo-local development `data/`, and `*.pre_*` source backup copies were not re-archived as duplicate code. Git history is the recovery record for those items; the live migration tool separately backs up repo-local `data/` outside the repository before removal.

## Restructure record

- Archived/moved paths: 161
- Removed duplicate/generated/state paths from active tree: 21

See `restructure_manifest.json` for the exact move/removal record.
