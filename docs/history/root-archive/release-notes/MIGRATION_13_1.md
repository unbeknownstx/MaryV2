# MaryV2 13.1 Migration

13.1 is a safe overlay over 13.0.

## Before overlay

Make a normal backup of your current MaryV2 folder or at minimum your private `data/` and `.env`.

## Overlay

Extract the **13.1 Full Overlay** directly into the existing MaryV2 project root and replace matching source files.

The release does not contain `.env` or `data/`, so it cannot intentionally replace API secrets, memory, relationship state, developed state, Voice Lab profiles or existing persistent data.

## Verify first

```powershell
python -m scripts.check_mary_13_1
python -m pytest tests -q
python -m scripts.run_release_verification
```

Only after these pass should you commit/push 13.1.

## Optional semantic vectors

Vectors are not required for first boot. Verify Mary normally first.

Later:

```powershell
ollama pull nomic-embed-text
python -m scripts.rebuild_semantic_vectors --limit 1000
python -m scripts.rebuild_semantic_vectors --status
```

The vector SQLite file is derived local state. It can be deleted/rebuilt without deleting Mary memories.

## Mobile/PWA

The service-worker cache is generation `v13-1`. Close/reopen the installed PWA after the new server is running. If Safari holds an old shell, refresh the server page once before removing/re-adding the PWA.

## Mac

Pull the exact same Git commit after Windows verification. Rebuild host-local Python/frontend dependencies on macOS; do not copy the Windows virtual environment.
