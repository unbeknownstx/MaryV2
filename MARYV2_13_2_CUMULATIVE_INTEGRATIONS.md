# MaryV2 13.2 — Cumulative Integration Checkpoint

This checkpoint consolidates the reconciliation work performed on top of the uploaded GitHub/main snapshot while preserving the existing MaryV2 architecture rather than rebuilding it.

## Included integration layers

1. Canonical `MaryApplication` composition and startup integrity checks.
2. Mary subsystem object-identity wiring diagnostics.
3. Bounded device/surface/conversation turn envelope into TurnMind.
4. MaryEcosystem / Companion Pulse workspace context into TurnMind.
5. Research → Evaluation → LearningKnowledge → KnowledgeManager → reservoir integration.
6. Agency priorities / decision preview into cognition without action authorization.
7. Real bounded short-dialogue sessions keyed by `conversation_id`.
8. Canonical Core workspace/runtime gateway for remote clients.
9. Desktop/Mac remote-Core composition: client when `MARY_CORE_URL` is configured, no second authoritative Mary.
10. Distributed device capability registration, heartbeat and routing.
11. Deny-by-default typed device-task broker with `personal_search` as the only executable capability currently allowed by Core.
12. Device-local capability permissions and Windows PersonalSearch execution/sanitization.
13. TurnMind → deterministic dialogue plan → reasoning/reflection → expression/voice/avatar → Dialogue → next-turn expression continuity.
14. Replit/PWA first-class client convergence: conversation selector, Core/node/capability status, TurnMind dialogue diagnostics, remote PersonalSearch, mobile/native bundle synchronization and safe Replit self-check tooling.

## Verified boundaries

- GitHub/main is source-code authority, not live Mary state.
- One Core owns one canonical Mary runtime/state in distributed mode.
- Models/providers are replaceable capabilities, not identity owners.
- Device nodes advertise capabilities but explicitly do not own identity, memory or canonical state.
- Remote capability routing is not execution authorization.
- PersonalSearch execution remains typed, locally permission-gated and path-sanitized.
- TurnMind/dialogue plans are ephemeral derived guidance, not permanent personality or memory.
- Conversation IDs isolate bounded short dialogue only; durable Mary state remains shared.

## Verification

Current consolidated repository suite in the integration workspace:

```text
1190 passed, 1 skipped
```

The skip is the intentionally opt-in live LLM test.
