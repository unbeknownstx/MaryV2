# MaryV2

MaryV2 is a single-user persistent character runtime and personal/creative computing interface centered on **one Mary across many surfaces, nodes, and replaceable models**.

Mary is not an LLM, a cloud process, a desktop window, or a `data/` directory. The repository implements the runtime that composes Mary's authored character, lived continuity, context, capabilities, devices, voice/avatar presentation, and creative/project workflows.

## Start here

1. Read [`MARY_ROOT.md`](MARY_ROOT.md) for the authority hierarchy and non-negotiable invariants.
2. Read [`docs/architecture/SYSTEM_REGISTRY.md`](docs/architecture/SYSTEM_REGISTRY.md) for the subsystem map.
3. Copy `.env.example` to `.env` and configure only the providers/capabilities you actually use.
4. On Windows, run `scripts\setup_windows.ps1` for the Python/desktop environment.
5. Run `python -m scripts.verify_maryv2_convergence` and `python -m pytest -q` before treating a checkout as healthy.

## One Mary, many surfaces

When `MARY_CORE_URL` is configured, Desktop, Mobile, and Terminal are clients of the same remote Mary Core. They must not create a second Mary runtime. A Windows capability node can remain available independently of the Desktop UI and expose approved local capabilities such as Ollama.

Without `MARY_CORE_URL`, explicit standalone development is still supported.

## Runtime state

A source checkout is **code, not Mary's mutable state container**. Unless `MARY_DATA_DIR` is explicitly set or portable mode is requested, Mary stores writable state under the host operating system's application-data directory (for example `%LOCALAPPDATA%\MaryV2\data` on Windows).

Repository-local `data/` from historical development is not part of the canonical source tree.

## Authored Mary

Creator-authored character material lives under `character_sources/`:

- `character_sources/active/` — material Mary may load automatically.
- `character_sources/drafts/` — unfinished creator material; **not automatically loaded**.

The Character Sourcebook preserves `[FC]`, `[DNA]`, `[AI]`, `[PUB]`, `[ALT]`, and `[NEG]` provenance. Fictional canon is never silently promoted into AI Mary's lived history.

## Unbeknownst / creative production

Project source is organized under `projects/unbeknownst/` with separate book, manga, animation, audio, assets, and production areas. Mary Studio and the provider-neutral production planner are intended to coordinate these media without replacing creator authorship.

## Development commands

```powershell
# Fast development gate
powershell -ExecutionPolicy Bypass -File scripts\test_fast.ps1

# Full deterministic suite
python -m pytest -q

# Convergence / authority checks
python -m scripts.verify_maryv2_convergence

# Repository structure check
python -m scripts.verify_repository_structure
```

## Windows headless capability node

```powershell
# Allow Ollama capability once
python -m scripts.node_permissions allow llm.ollama

# Run manually
powershell -ExecutionPolicy Bypass -File scripts\launch_windows_node.ps1

# Or install a per-user scheduled node at logon
powershell -ExecutionPolicy Bypass -File scripts\install_windows_node_task.ps1
```

The headless node is a capability host, not another Mary.

## Repository layout

```text
mary/                 canonical runtime source
tests/                deterministic and integration tests
scripts/              setup, verification, build, node, and maintenance tools
desktop/              desktop web shell assets
mobile_web/           mobile/PWA surface
mobile_native/        native mobile work
docs/                 current documentation + archived project history
character_sources/    authored Mary sources (active vs drafts)
projects/              creator project workspaces/reference source
```

Historical 1.x–15.x development documents are preserved under `docs/history/`, but they are not current authority. Git history remains the recovery record for deleted duplicate payloads/backups.

## Current boundary

This repository is **MaryV2 itself**. Generic Instance Platform, Everwork, marketplace, multi-tenant SaaS, and other later productization work are out of scope until MaryV2 is complete.
