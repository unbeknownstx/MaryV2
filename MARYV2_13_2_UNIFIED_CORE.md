# MaryV2 13.2 — Unified Mary Core

13.2 establishes one host-independent authority boundary without replacing Mary's existing cognition or persistence systems.

## Authority

- `MaryCoreService` owns one long-lived `MaryApplication`.
- `MaryApplication` owns the one live `Mary` coordinator and existing persistent stores.
- Clients never instantiate Mary when connected to a Core.
- All state-changing creator turns are serialized through the same Core lock and canonical pipeline.
- LLMs and compute nodes remain replaceable resources, not identity authorities.

## Protocol v1

HTTP:

- `GET /v1/health` — minimal hosting health check (no private state)
- `POST /v1/turn`
- `GET /v1/state`
- `GET /v1/memory/status`
- `GET /v1/conversation`
- `GET /v1/growth`
- `GET /v1/nodes`
- `WS /v1/realtime`

Every private HTTP route requires `Authorization: Bearer <MARY_CORE_TOKEN>`.
WebSocket clients may use that header or send `{\"type\":\"auth\",\"token\":\"...\"}` as the first frame.

## Run locally

```bash
pip install -r requirements.txt
export MARY_CORE_TOKEN='use-a-long-random-secret'
python -m scripts.run_core
```

Default bind is loopback (`127.0.0.1:8080`). Binding to a non-loopback address without `MARY_CORE_TOKEN` fails closed.

## Railway / private cloud

Recommended environment:

```text
MARY_CORE_HOST=0.0.0.0
MARY_CORE_TOKEN=<long random creator token>
MARY_DATA_DIR=/data
```

Attach a persistent Railway volume at `/data`. Keep exactly one Mary Core replica. Provider keys stay server-side. Do not expose Ollama or home-PC services to the public internet.

Start command:

```text
python -m scripts.run_core
```

## Client migration

Existing frontends can migrate incrementally by replacing direct `Mary()`/`create_application()` ownership with `MaryClient`. The desktop can later use an in-process transport for development, but it should retain the same `TurnRequest`/`TurnResponse` contract.

## State migration

13.2 deliberately does not rewrite JSON state or require SQLite. First establish one live state writer. Archive old host-local state, select meaningful memories later, then migrate storage behind the Core boundary when useful.

## Existing Replit/mobile UI as a Core client

The existing `mary.mobile.server` now has a remote-client mode. Set:

```text
MARY_CORE_URL=https://<your-private-core-host>
MARY_CORE_TOKEN=<same creator token>
MARY_DEVICE_ID=replit-mobile
```

When `MARY_CORE_URL` is present, the mobile server uses `MaryRemoteMobileRuntime` and **does not construct a local `MaryApplication`**. `/api/chat` is translated into Mary Protocol turns against the authoritative Core while the existing PWA remains usable. Mobile TTS/STT can remain at the interface layer; closing the frontend never shuts down the Core.

If `MARY_CORE_URL` is absent, the legacy local mobile runtime remains available for development/backward compatibility.
