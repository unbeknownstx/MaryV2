# MaryV2 current state — 13.2 Unified Core

MaryV2 now runs as one persistent Mary with multiple clients and replaceable capability nodes. GitHub/main is source-code authority; the deployed Mary Core is canonical live runtime/state authority.

## Verified architecture

- One `MaryCoreService` owns one long-lived `MaryApplication`, one Mary, one MaryEcosystem and one RuntimeState.
- Application/subsystem integrity diagnostics protect object-identity wiring.
- Turn envelopes carry bounded device/surface/conversation context without allowing clients to inject character state.
- Ecosystem Companion Pulse is projected into TurnMind as read-only ephemeral workspace context.
- Research learning flows through evaluation → LearningKnowledge → trusted KnowledgeManager → derived reservoir retrieval.
- Agency priorities/decision preview can orient cognition without authorizing action.
- Conversation IDs now select bounded short-dialogue sessions while durable Mary state remains shared.
- TurnMind now drives a deterministic dialogue plan used by reasoning, reflection, expression, voice/avatar delivery and the next session turn's expression continuity.
- Desktop/Mac remote mode uses Mary Protocol/Core rather than silently constructing a second authoritative Mary.
- Device nodes register/heartbeat capabilities while explicitly owning no Mary identity, memory or canonical state.
- Typed device-task execution is deny-by-default; the current executable allow-list contains only `personal_search`, and device-local permission is still required.
- A live Windows node has been verified routing and completing a Core → Windows → PersonalSearch → Core round trip with sanitized relative paths/snippets.
- Replit/mobile is a first-class Core client with persistent conversation selectors, Core/node visibility, TurnMind dialogue diagnostics and remote PersonalSearch routing.

## Latest verification checkpoints

- Current full-suite checkpoint after the web convergence pass: **1190 passed, 1 skipped**.
- Desktop/Core focused integration checkpoint: **113 passed**.
- Device capability-node focused checkpoint: **35 passed**.
- Authorized PersonalSearch focused checkpoint: **43 passed**.
- TurnMind → Dialogue/Expression focused checkpoint: **22 passed**.
- Web/Replit convergence affected integration group: **67 passed** before the final full-suite gate.

The single skip is the intentionally opt-in live LLM test unless explicitly enabled.

## Source / state boundary

Do not commit `.env`, live `data/`, `.venv`, `node_modules`, device permission files, runtime databases containing private state, or credentials. Code moves through GitHub; Mary's live identity/state moves through the canonical Core persistence path.

## Mobile/Replit commands

```text
python -m scripts.run_mobile
python -m scripts.sync_mobile_web --check
python -m scripts.sync_mobile_web --sync
python -m scripts.check_replit_client
```

See `replit.md`, `MOBILE_REPLIT_13_2_CONVERGENCE.md`, and `MARYV2_13_2_UNIFIED_CORE.md`.
