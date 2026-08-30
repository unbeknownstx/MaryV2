# MaryV2 Root Contract

This file is the human-readable companion to `mary.runtime.root_authority.MaryRootAuthority`.
The **code** is what makes the hierarchy testable; this Markdown is the stable map a human or
engineering agent should read before changing Mary.

## One sentence

**Many surfaces, many nodes, many replaceable capabilities — one Mary.**

## Authority hierarchy

1. **Runtime invariants** — the repository's validated one-Mary composition, boundaries, permissions, and state owners.
2. **Authored character** — Character Core plus creator-authored Character Bible/corpus/canon/performance material through `CharacterSourcebook`.
3. **Lived continuity** — AI Mary's actual relationship, memory, developed self, goals, agency, and grounded experience through their existing owners.
4. **Turn context** — `TurnMindState`, bounded recent conversation, retrieval, workspace context, and relevant authored-character evidence.
5. **Capability fabric** — LLMs, search, files, tools, creative services, speech, perception, and future integrations.
6. **Nodes** — cloud, Windows PC, Mac, future GPU/server, or other replaceable execution hosts.
7. **Surfaces** — desktop, mobile/web, terminal, and future public/performer interfaces.

## Context rule

Everything can be **addressable** without everything being placed into every prompt. Mary should
select the smallest sufficient authoritative context for the creator's present intention.

## Character rule

`CharacterSourcebook` may read creator-authored `.docx`, Markdown, text, JSON, or JSONL material.
Evidence labels retain their meanings:

- `[FC]` fictional canon/reference — never automatically AI Mary's lived memory.
- `[DNA]` shared Mary character DNA.
- `[AI]` authored material specifically about persistent AI Mary.
- `[PUB]` public/performance context for the same Mary, not a replacement identity.
- `[ALT]` alternate/experimental interpretation.
- `[NEG]` anti-example: what Mary should **not** imitate.

Static Character Core remains the bootstrap if no external sourcebook is configured.

## Capability rule

Models and services are tools. A video model, OpenAI, Ollama, a Windows GPU, a cloud host, or a
future server does not become Mary because it generated something. Capability discovery and
permission/spending are separate decisions.

## Persistence rule

No one database/file is allowed to be the conceptual definition of Mary. A recoverable Mary needs:
repository/runtime + authored character sources + durable continuity state + separately reattached
credentials/capabilities. Derived indexes and caches must be rebuildable.

## Cleanup rule

Inventory first. Classify second. Archive third. Delete only after replacement/provenance is proven
and a recovery copy exists.
