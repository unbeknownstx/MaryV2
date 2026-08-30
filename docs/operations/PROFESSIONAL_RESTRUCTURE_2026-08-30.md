# Professional Repository Restructure — 2026-08-30

This pass turns the accumulated 1.x–15.x development repository into a clean current source tree without discarding the project archaeology.

## Structural changes

- Root reduced from ~185 mixed entries to a small canonical project surface.
- Historical release/migration/stage/hotfix/installer/manifests moved under `docs/history/`.
- Duplicate `payload/` and `upgrade_backups/` removed from active source; Git history remains their recovery record.
- Tracked `desktop/node_modules/` removed; recreate locally with `npm ci` only after committing the deletion.
- Repo-local development/test `data/` removed from source; migration backs it up externally and source runs default to host-native MaryV2 application data.
- `*.pre_*` source/test backup copies removed from active source.
- Unfinished Character Bible moved to `character_sources/drafts/` and excluded from automatic runtime loading.
- Approved authored character sources belong in `character_sources/active/`.
- Unbeknownst source organized under `projects/unbeknownst/`.

## Runtime fixes

- Terminal now obeys `MARY_CORE_URL` and uses canonical remote Core instead of constructing a local second Mary.
- State reconciliation labels one-root runs `single_root_inventory`; comparison requires at least two roots.
- Windows headless node can be installed as a per-user logon task and can start local Ollama server if needed.
- `python -m pytest -q` is a clean canonical test command and ignores generated/scratch/history paths.

## Verification

- Full pytest after restructure: **1324 passed, 1 skipped**.
- MaryV2 convergence verifier: PASS.
- Repository structure verifier: PASS.
- Deterministic/offline release verification: PASS.
