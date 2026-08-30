# MaryV2 13.2 Release Notes — Unified Mary Core

## Architectural objective

One core, one state authority, one turn pipeline, one protocol, multiple clients, replaceable models, optional compute nodes, zero intentional duplicate Mary identities.

## Added

- `mary/core/service.py`: authoritative `MaryCoreService` owning one persistent `MaryApplication`.
- `mary/protocol/models.py`: transport-neutral v1 turn contract.
- `mary/protocol/client.py`: dependency-light Python client for future desktop/Replit/Mac/native adapters.
- `mary/protocol/server.py`: authenticated FastAPI HTTP + WebSocket transport.
- `scripts/run_core.py`: canonical Core launcher.
- `railway.toml`: simple Railway start + health-check configuration.
- Isolated protocol/service/server tests.

## Preserved

No rewrite of cognition, identity, relationship, memory, growth, realtime, routing, local mind, retrieval, or compute-node internals. Existing `MaryApplication` persistence configuration remains authoritative beneath the Core service.

## Security

- `/v1/health` exposes only minimal service health for hosting checks.
- Every state/turn endpoint requires `MARY_CORE_TOKEN`.
- Non-loopback launch without a token fails closed.
- Provider keys remain on the Core host.
- Home Ollama/PC services are not exposed by this release.

## Persistence

13.2 deliberately keeps existing JSON/state persistence. Configure `MARY_DATA_DIR` to a durable mounted directory on an always-on host. SQLite/event-ledger migration remains a later storage-layer improvement, not a prerequisite for core centralization.
