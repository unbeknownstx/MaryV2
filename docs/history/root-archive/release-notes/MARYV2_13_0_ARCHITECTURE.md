# MaryV2 13.0 Architecture

## Design goal

13.0 separates **fast reaction**, **intentional conversation**, and **durable development** instead of forcing every turn through one latency/quality compromise.

```text
Creator / client
      │
      ▼
Canonical MaryApplication
      │
      ├── Turn Policy + Conversation Lane
      │       ├── adaptive/quick → fast conversation route
      │       └── engaged/deep  → full conversation route
      │
      ├── TurnMindState
      │       ├── identity / character / values
      │       ├── relationship + memory
      │       ├── agency / curiosity / emotion
      │       ├── continuity
      │       └── ConversationEngagement
      │
      ├── LLMRouter (generation engine, not identity)
      │
      ├── response / expression / voice
      │
      └── post-turn GrowthEngine
              ├── ExperienceJournal
              ├── safe semantic consolidation
              ├── strict preference maturation
              └── grounded milestones
```

## ConversationEngagement

`mary/conversation/engagement.py` owns only conversational depth/initiative policy. It cannot mutate identity or invent facts. Its active thread is persisted under the configured data root so a short restart does not erase an intentional conversation.

Modes:

- `adaptive`: normal Mary, latency-aware;
- `quick`: deliberately terse;
- `engaged`: multi-turn intentional conversation with balanced initiative;
- `deep`: more reasoning/output room for reflective conversation.

The compact prompt includes only a tiny engagement marker during ordinary adaptive turns, preserving the previous prompt-efficiency guard.

## GrowthEngine

`mary/development/growth.py` runs after a completed turn. It records observable experience and can use already-existing development pathways. It does not expose hidden reasoning and it does not treat assistant/model prose as self-fact evidence.

Autonomous preference promotion is deliberately stricter than ordinary eligibility:

- at least 5 observations;
- mean confidence ≥ 0.85;
- consistency ≥ 0.90;
- mean magnitude ≥ 0.60;
- no blocked/model-authored evidence.

This creates room for real development without allowing a single generated sentence to rewrite Mary.

## ExperienceJournal

`mary/development/experience.py` persists a bounded record of display-safe turn outcomes and development signals. It is not a chain-of-thought log.

## Existing autonomy/presence retained

13.0 keeps the prior Agency, Autonomy, Presence, pending-thought, idle-behavior and initiative systems. The new conversation engine connects intentional user-facing dialogue to real relationship-curiosity state instead of replacing those systems.

## Voice Lab

`mary/mobile/voice_lab.py` persists private voice profiles server-side. Public dashboard state exposes labels/settings but not ElevenLabs voice IDs. Selecting a profile updates the active mobile speech service and clears its synthesis cache.

Dynamic delivery shaping remains available, but the default is now the unlayered voice baseline. This makes voice selection happen before performance tuning.

## Provider routing

The router remains lazy and portable. Provider-specific model settings are authoritative when present. Replit can run without Ollama; local machines can still use Ollama as an optional character/conversation engine. Paid OpenAI remains explicit specialist authorization only.

## State ownership

13.0 intentionally preserves one-state ownership:

- identity/canon → existing Mary identity/character systems;
- creator relationship → RelationshipManager/UserModel;
- memory → MemoryManager;
- emotions → EmotionManager;
- agency → Agency;
- provider routing → LLMRouter;
- conversational depth → ConversationEngagement;
- experience development → GrowthEngine/ExperienceJournal;
- final consequential/durable authority → creator + existing approval boundaries.
