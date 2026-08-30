# MaryV2 Development Workflow

## Normal loop

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_fast.ps1
python -m scripts.verify_repository_structure
```

## Full gate

```powershell
python -m pytest -q
python -m scripts.verify_maryv2_convergence
```

## Source hygiene

Do not add temporary patch payloads, installer backups, repo-local Mary state, node_modules, runtime reports or `*.pre_*` source copies to the canonical tree. Use Git history and `docs/history/` for archaeology.

## Historical material

`docs/history/` is searchable provenance. If an old document conflicts with `MARY_ROOT.md`, `README.md`, `SYSTEM_REGISTRY.md`, current code or current tests, the old document does not win automatically.
