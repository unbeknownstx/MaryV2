# START HERE — MaryV2 13.2 Unified Mary Architecture

13.2 does not replace Mary. It creates one authoritative runtime boundary around the existing 13.1.1 system.

## What changed

The new ownership chain is:

```text
clients -> Mary Protocol -> MaryCoreService -> MaryApplication -> one Mary()
```

`MaryApplication` remains the persistence-aware composition root. `MaryCoreService` owns exactly one long-lived application and serializes creator turns through the existing canonical pipeline.

## Safe local verification

The 13.2 tests are state-isolated and do not load creator data:

```bash
python -m pytest tests/protocol -q
```

Then run the existing targeted runtime checks appropriate to the host.

## Start the Core

Set a long private creator token and launch:

```bash
export MARY_CORE_TOKEN='replace-with-a-long-random-secret'
python -m scripts.run_core
```

PowerShell equivalent:

```powershell
$env:MARY_CORE_TOKEN="replace-with-a-long-random-secret"
python -m scripts.run_core
```

Default: `127.0.0.1:8080`.

## Railway

Use one replica and attach persistent storage at `/data`.

Required/recommended environment:

```text
MARY_CORE_HOST=0.0.0.0
MARY_CORE_TOKEN=<long creator token>
MARY_DATA_DIR=/data
GROQ_API_KEY=...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=...
ELEVENLABS_API_KEY=...
```

Start command is already declared in `railway.toml`:

```text
python -m scripts.run_core
```

Do not put the creator token or provider keys in GitHub.

## What not to migrate yet

Do not merge Windows/Mac/Replit state files into one directory by hand. Keep old state archived. First establish one deployed Core and let only that Core own live writes. Meaningful legacy memories can be migrated later under an explicit controlled migration.

## Point the existing Replit/mobile UI at Core

On the Replit frontend deployment, set:

```text
MARY_CORE_URL=https://<core-host>
MARY_CORE_TOKEN=<same private creator token>
MARY_DEVICE_ID=replit-mobile
```

In this mode the Replit mobile server does not construct another Mary. It becomes a compatibility client/proxy for the existing phone UI.
