# MaryV2 Convergence Upgrade — 2026-08-30

This package is **actual MaryV2 source code**, built against the user-provided Copy(4) snapshot. It matures V2 without replacing the existing one-Mary runtime.

## Install from PowerShell

With the MaryV2 virtual environment active, extract this package and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\INSTALL_CONVERGENCE.ps1
```

The wrapper defaults to:
`C:\Users\Melvin\Documents\GitHub\MaryV2`

For a different clone:

```powershell
powershell -ExecutionPolicy Bypass -File .\INSTALL_CONVERGENCE.ps1 -RepoPath "C:\path\to\MaryV2"
```

For the full suite after the focused gate:

```powershell
powershell -ExecutionPolicy Bypass -File .\INSTALL_CONVERGENCE.ps1 -FullSuite
```

## Safety

The installer:
- refuses to target `.env`, `data/`, `.git`, `.venv`, or `node_modules`;
- backs up every file it replaces under `%LOCALAPPDATA%\MaryV2\upgrade_backups`;
- auto-rolls back if verification fails (unless `--keep-on-failure` is used directly with the Python installer);
- never packages the real `.env` or Mary data/state.

## What becomes real code in this upgrade

- Authored Character Sourcebook with direct DOCX/Markdown/text/JSON ingestion and `[FC]/[DNA]/[AI]/[PUB]/[ALT]/[NEG]` provenance.
- Bounded per-turn authored-character retrieval wired into the canonical TurnMind and reasoning projection.
- Mary-specific evaluation set separated from memory/self-state.
- Executable root authority hierarchy and one-Mary validation.
- Emotional momentum/decay so emotion does not snap mechanically to neutral after every turn.
- Read-only local/cloud state reconciliation reports.
- Secret-free recovery manifests/snapshots with SHA-256 verification.
- Cross-media Studio production plans for book, manga, animation/video, audio drama, and mixed media.
- Secret-free creative service/cost registry for provider/model/capability/cost discovery without spending authority.
- Read-only repository-layer archaeology classifier.
- Core state visibility for character authority/root authority/creative services.
- Release verifier coverage for the convergence layer.

## Deliberately not faked

- Your filled Character Bible/corpus are not inside this package; point `MARY_CHARACTER_SOURCES` at them when ready.
- Real third-party image/video/music provider execution adapters are not invented. The orchestration/service/cost contract is ready; actual providers are connected explicitly.
- Local/cloud Mary state is not auto-merged. Run the reconciliation audit first and review conflicts.
- Old repository files are not automatically deleted. The classifier reports archive candidates first.
- This does not create the final expressive 3D Mary model or finish the Command Center UI.

## Character source configuration

Example only (do not put secrets here):

```text
MARY_CHARACTER_SOURCES=C:\MarySources\Mary_Definitive_Character_Bible.docx;C:\MarySources\Mary_Corpus.md
MARY_CHARACTER_EVALS=C:\MarySources\mary_evaluation.json
MARY_CREATIVE_SERVICE_CATALOG=C:\MarySources\creative_services.json
```

## Useful checks after install

```powershell
python -m scripts.verify_maryv2_convergence
python -m scripts.check_mary_character_authority
```

Repository cleanup report:

```powershell
python -m scripts.audit_repository_layers
```

Recovery manifest (read-only/default):

```powershell
python -m scripts.create_mary_recovery_snapshot
```

See `payload/MARYV2_CONVERGENCE_UPGRADE.md`, `payload/MARY_ROOT.md`, and the docs in `payload/docs/` for architecture details.
