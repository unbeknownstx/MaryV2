# MaryV2 Final Runtime Architecture

MaryV2 is a private, persistent character runtime for Mary Cosma. Mary is the
character and continuity layer; language models, tools, web search, voice, and
the avatar are replaceable capabilities.

## Non-negotiable V2 invariants

1. **Mary remains Mary across providers.** Model output cannot directly mutate
   character canon, creator facts, durable developed-self state, or authority.
2. **Persistence is selective, not photographic.** Active context, working
   memory, durable memories, relationship records, task workspaces, learning
   ledgers, logs, provider attempts, and backup chains must all be bounded.
3. **Storage and context are separate.** Years of durable state may exist on
   disk while each generation receives only a bounded relevant slice.
4. **Temporary work is temporary.** Task hypotheses, consultations, tool output,
   and failed reasoning are task-local unless an existing explicit persistence
   path promotes something valuable.
5. **Capability is not permission.** Tools, paid experts, consequential changes,
   and creator-authority decisions remain gated.
6. **Paid OpenAI is advisory and opt-in.** Ordinary character conversation is
   local-first (Ollama -> Groq -> Gemini -> OpenRouter). Task/general free-first
   remains Groq -> Gemini -> OpenRouter -> Ollama and excludes paid OpenAI;
   private/offline remains Ollama-only.
7. **Failure degrades capability, not identity.** Avatar, voice, cloud models,
   web access, and individual tools may fail without taking the Mary core down.
8. **Persistent writes are recoverable.** Critical JSON state is written
   atomically with a finite backup chain; corrupted primary state can recover
   from recent valid backups.
9. **The running system is observable without exposing private content.** Live
   state exposes counts, represented mood, runtime state, provider/resource
   counters, privacy policy, and task status—not raw memories or API keys.
10. **A standalone build keeps writable state outside bundled resources.**
    Frozen Windows builds default to `%LOCALAPPDATA%\MaryV2\data`; portable mode
    can be selected explicitly.

## Runtime loop

```
creator input
  -> conservative natural-input matching
  -> Mary cognition / deterministic local state
  -> TurnPolicyEngine
       personal/relational conversation -> local-first Ollama
       detached task/general work -> free-first cloud pool
  -> bounded task workspace when needed
  -> orchestration plan (privacy + cost + capability + authority)
  -> controlled executor
       local / free-first / private Ollama / research / tool / verify / expert
  -> output quality + evidence + provenance + capability-truth reflection
  -> Mary continuity / emotion / expression
  -> explicit selective persistence paths only
```

## Memory lifecycle

```
interaction
  -> bounded recent/working context
  -> candidate durable information only when appropriate
  -> episodic / semantic / relationship / developed-self path
  -> hard collection capacity + deduplication/retention policy
  -> selective retrieval (top-N) for future turns
```

For a persistent character, forgetting/compaction is a reliability feature.
MaryV2 does not attempt to preserve or re-inject every detail forever.

## Standalone modes

- Development: project-root resources and project `data/`.
- Installed/frozen: bundled read-only resources + writable LocalAppData state.
- Portable: set `MARY_PORTABLE=1`; writable `data/` lives beside `MaryV2.exe`.
- Custom: set `MARY_DATA_DIR`, `MARY_WORKSPACE_ROOT`, or `MARY_ENV_FILE`.


## Breakthrough 11 conversation-supervision boundary

Breakthrough 10 established the local-conversation / specialist-task routing
boundary. Breakthrough 11 adds a bounded process-local supervision layer above
it: pending relationship-question reasons, rejected-hypothesis suppression,
grounded shared-history/self-development views, emotion-to-language grounding,
and semantic style-loop auditing. None of this creates a second durable memory
authority. See `docs/architecture/V2_BREAKTHROUGH_11.md`.

Test/probe creator or memory residue may remain durably auditable, but normal
model-facing context uses a provenance-safe projection that excludes obvious
development probes.
