# MaryV2 — Replit / Web Client Guide

MaryV2 13.2 is a distributed persistent-character runtime. Replit is a real development environment and web/PWA host, but **GitHub/main is the source-code authority** and the deployed **Mary Core is the canonical live character/state authority**.

## Current architecture

```text
GitHub/main                         source-code authority
    │
    ├── Replit IDE + mobile/PWA    development + web client
    ├── Windows / Mac IDEs         development + native/desktop clients
    │
    └── Mary Core                  one canonical runtime/state authority
           │
           ├── identity / relationship / memory / growth
           ├── TurnMind / cognition / reflection / expression
           ├── Command / Focus / Study / Research / Inbox
           ├── conversation sessions
           └── device-node registry + typed task broker
                  │
                  └── Windows/Mac capability nodes
                      (files, PersonalSearch, Ollama, audio, apps, GPU later)
```

Providers such as Groq, Gemini, OpenRouter, Ollama, OpenAI, ElevenLabs and STT services are replaceable capabilities. They do not own Mary's identity.

## Replit mode

For the normal distributed setup, configure these as Replit Secrets/environment variables:

```text
MARY_CORE_URL=https://<your-core-deployment>
MARY_CORE_TOKEN=<private core token>
MARY_MOBILE_TOKEN=<private browser/PWA token>
MARY_DEVICE_ID=replit-mobile
MARY_CONVERSATION_ID=creator-primary
```

Never commit `.env`, tokens, provider API keys, live `data/`, device-permission files, or private runtime state.

Start the web client/server with:

```bash
python -m mary.mobile.server
```

or:

```bash
python -m scripts.run_mobile
```

When `MARY_CORE_URL` is present, the mobile runtime is a **remote Core client** and must not construct a second `MaryApplication`.

## Web/PWA capabilities in 13.2

The canonical `mobile_web/` client supports:

- persistent conversation/thread IDs (`Main`, `MaryV2`, `Unbeknownst`, `Study`, plus custom threads);
- adaptive / engaged / deep conversation controls;
- canonical Core status and runtime provenance;
- connected device-node/capability visibility;
- bounded TurnMind → Dialogue developer diagnostics for the latest turn;
- remote typed `personal_search` tasks routed through Core to an authorized device node;
- Command, Focus, Study, Research, Inbox/Presence and Companion Pulse views;
- server TTS with device fallback, server STT with browser/native fallback, interruption reporting;
- explicit response-quality feedback;
- installable PWA shell and the same bundled web source inside the native iOS project.

A conversation ID changes only bounded short-dialogue context. Mary's identity, relationship, durable memory, growth, knowledge, agency and ecosystem remain shared.

## Mobile source-of-truth rule

`mobile_web/` is the canonical browser source. `mobile_native/MaryMobile/www/` is a generated copy for Xcode.

Check for drift:

```bash
python -m scripts.sync_mobile_web --check
```

Synchronize after changing the web client:

```bash
python -m scripts.sync_mobile_web --sync
```

The macOS helper `mobile_native/SYNC_WEB_FROM_PROJECT.command` now calls the same Python sync implementation.

## Replit self-check

Run:

```bash
python -m scripts.check_replit_client
```

The check reports configuration presence, mobile/native bundle parity, Core architecture/health and connected-node count. It never prints secret values.

## Useful verification

Fast mobile/Core integration check:

```bash
python -m pytest tests/mobile tests/protocol/test_core_service.py tests/protocol/test_server_contract.py tests/runtime/test_runtime_gateway_13_2.py -q
```

Full repository gate:

```bash
python -m pytest tests -q
```

Live LLM tests remain opt-in and should not be enabled merely to validate the web client.

## Device tasks

Core may route a typed capability task to a connected device, but routing does not grant execution. The current executable device task allow-list is intentionally narrow: `personal_search` only. The selected device must also have local permission for that capability.

There is no generic remote shell task and no inbound remote-control socket opened on the Windows PC.

## Development rule

Preserve the existing MaryV2 architecture. Add or reconnect functionality through the canonical composition and protocol boundaries rather than creating another Mary, another memory authority, or a second ecosystem owner.
