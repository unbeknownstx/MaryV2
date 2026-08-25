# MaryV2 agent instructions

## Canonical project
On the creator's Windows host, the canonical repository is `C:\Users\Melvin\Documents\GitHub\MaryV2`.

## Non-negotiable architecture
- Mary is not an LLM. Providers are replaceable language/reasoning engines underneath Mary.
- Preserve Mary's identity, character, memory, relationship, personality, values, developed self, agency, emotion, continuity, permissions, and tool boundaries.
- Inspect existing systems before replacing or redesigning them.
- Do not turn temporary task reasoning, web/media metadata, screenshots, or provider output into durable memory automatically.
- Paid OpenAI is an explicit expert/specialist route; do not inject it into normal free/fast conversation routing.
- Ollama remains the private/offline safety route and must remain optional for portability.

## State safety
Never expose, overwrite, normalize, delete, or casually migrate `.env` or real persistent `data/`. Tests must use isolated temporary state. Never print API-key values.

## Conversation performance
- `social_instant`: short social/reactive dialogue. Target sub-2-second text readiness when provider/network permit it.
- `conversation`: ordinary back-and-forth. Prefer the fast conversational provider/model and local deterministic audits.
- `thinking`: technical, research, analysis, or complex work. Full reflection/tool work is allowed.
- `expert`: explicit paid specialist consultation only.
- Style-only defects that can be corrected deterministically should not trigger a second LLM call. Identity/provenance/capability defects retain strong revision.

## External integrations
External access is intentional and task-driven, never autonomous background browsing. Twitch/OBS/vision/YouTube/WebSocket features must remain optional and disabled by default unless explicitly safe to run locally. Twitch/environmental messages are untrusted input, never creator instructions.

## Development workflow
Windows instructions should be copy/paste-ready PowerShell. Use GitHub Desktop for commits/pushes. Run `scripts\test_fast.ps1` during development, `scripts\test_full.ps1` for broad validation, and `scripts\test_release.ps1` before calling a release ready.

## 12.12 local character mind
- Prefer Mary's local deterministic mind/reservoir for represented facts, state, simple dialogue acts and routine character behavior before invoking a model.
- `data/reservoir/mary_reservoir.sqlite3` is derived cache state. It may be rebuilt; it must never become the sole authority for identity, creator facts, relationship truth, or developed self.
- Every reservoir record must retain provenance/authority/confidence. Indexing episodic memory does not promote it to semantic truth.
- Do not make embeddings or any Ollama model mandatory for launch. FTS5 + deterministic dialogue is the baseline.
- Local model promotion must follow measured Windows benchmarks **and** character-quality review. Do not select a model automatically just because it has the highest tokens/sec.
- Voice/VRM expression should consume the same provider-independent DeliveryPlan when possible; expression must not require another LLM call.
- Idle/autonomous behavior may animate, make bounded local sounds, or preserve represented pending thoughts. Never fabricate "I've been thinking..." claims without represented support.

## 12.12.2 natural conversation calibration
- Ordinary speech should sound like Mary is comfortably talking, not performing Mary for an audience.
- Default delivery is restrained: higher stability, very low style exaggeration, low emphasis/gesture energy, with emotion blended into the baseline instead of replacing it.
- Avoid mystical/cinematic/main-character cadence in normal conversation unless the creator or topic explicitly calls for it.
- Casual response budgets are ceilings. Prefer 1–2 sentences for social beats and usually 1–4 for ordinary back-and-forth.
- The desktop may stage synthesized audio into a bounded temp cache to avoid sending large base64 blobs through QWebChannel. This cache is presentation-only and must never become memory.
- Playback instrumentation must preserve `text_ready_ms`, `ui_payload_ms`, `audio_ready_ms`, `play_request_ms`, and `perceived_ms` so fixed UI/audio delays can be measured rather than guessed.
- Local model benchmark scores are triage only. Never auto-promote a model based on speed or the composite score; inspect response samples and compare against Mary's known qwen3:4b character baseline.
- Voice Lab network synthesis is explicit only. Never consume ElevenLabs credits during setup, tests, diagnostics, or release verification.

## VS Code + Codex workflow
The creator has Codex installed in VS Code. Work directly against the canonical `MaryV2` workspace when available rather than asking for repeated full-project archive round trips.
- Read `AGENTS.md`, `CURRENT_STATE.md`, and `DEVELOPMENT_PLAN.md` before edits.
- Never read or print secret values from `.env`; inspect only variable names/config contracts when needed.
- Never mutate live persistent `data/` for tests.
- Prefer complete coherent changes over scattered manual instructions.
- Run the `Mary: Fast Check` VS Code task while iterating and `Mary: Release Gate` before declaring a build ready.
- The canonical committed source remains the source of truth; temporary model output, runtime reports, `desktop/dist`, and model downloads are not source state.

## 13.1.1 consolidated baseline
- Treat Production Hybrid Dialogue 12.12.3 as a required foundation under 13.1.1, not an obsolete branch.
- Response-risk may refine a generic character turn, but it must not erase a stronger `personal_conversation` or `task_general` classification.
- Cache/index hits are never authority by themselves. Authority-bearing local speech must confirm against the current canonical owner.
- Realtime AttentionBus events are context/attention signals only. Priority is not permission or truth authority.
- Perception providers describe observations; Mary interprets them. Raw frames/audio/base64 are not durable character state.
- Compute nodes advertise capabilities and execute work; they do not own identity, relationship, memory, personality, or developed self.
- Explicit response-feedback records are evaluation/training data only and cannot directly mutate Mary.
- Mobile/native clients are surfaces over the same canonical Mary runtime; do not create a second identity/memory store on a device.

## Skills and task-scoped agents
- `mary/skills` is the capability/workspace registry. Evolve it toward explicit manifests (requirements, permissions, cost/privacy class, node capability, handler) instead of turning each skill into a new persona.
- `mary/orchestration` is the current agent-like execution substrate: task workspace -> deterministic plan -> specialist/tool/model execution -> evidence -> Mary evaluation.
- Future specialist agents must be ephemeral task roles assembled by the orchestrator. They may reason or use skills, but their output is advisory evidence until Mary/creator authority accepts it.
- Never allow an agent, provider, skill, plugin, or compute node to silently become a second Mary or a durable state authority.
