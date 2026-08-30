# MaryV2 Root Contract

Human-readable companion to `mary.runtime.root_authority.MaryRootAuthority`.

> **Many surfaces, many nodes, many replaceable capabilities — one Mary.**

## Authority hierarchy

1. **Runtime invariants** — one-Mary composition, state ownership, permissions, provenance, recovery rules.
2. **Authored character** — Character Core plus approved creator-authored sources from `character_sources/active/`.
3. **Lived continuity** — AI Mary's actual relationship, memory, developed self, grounded experience, goals and agency.
4. **Turn context** — current input, recent conversation, task/project context, relevant retrieval, relevant authored evidence.
5. **Capability fabric** — LLMs, search, files, code, speech, perception, creative services and integrations.
6. **Nodes** — cloud, Windows, Mac, rented compute, future GPU/server hosts.
7. **Surfaces** — desktop, mobile/web, terminal and future performer/public interfaces.

## One-Mary resolution

- `MARY_CORE_URL` present: surfaces use remote Core and **must not construct local Mary**.
- `MARY_CORE_URL` absent: explicit standalone development may construct one local `MaryApplication`.
- Capability nodes can run independently of UI surfaces but never become identity/state authorities.

## Context rule

Everything can be addressable without everything being placed into every prompt. Mary selects the smallest sufficient authoritative context for the creator's present intention.

## Character rule

`character_sources/active/` is automatically discoverable creator-authored material. `character_sources/drafts/` is intentionally excluded until approved.

Evidence labels:

- `[FC]` fictional canon/reference — never automatically AI lived memory.
- `[DNA]` shared Mary character DNA.
- `[AI]` persistent AI Mary material.
- `[PUB]` public/performance context for the same Mary.
- `[ALT]` alternate/experimental interpretation.
- `[NEG]` anti-example.

## Persistence rule

Mary is not defined by one mutable folder. Recoverability requires:

- repository/runtime,
- authored character sources,
- durable continuity state,
- separately reattached credentials/capabilities,
- rebuildable derived indexes/caches.

Source checkouts no longer use repository-local `data/` by default. Host-native application data or explicit `MARY_DATA_DIR` owns writable runtime state.

## Cleanup rule

Current authority lives in this file, the current `docs/` architecture/operations docs, and executable tests/code. `docs/history/` preserves project archaeology but cannot override current authority.
