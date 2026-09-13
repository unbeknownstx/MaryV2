# MaryV2 13.17 — Cognitive Character Runtime

## Purpose

Mary is one computational character with access to many cognitive resources. She is not a collection of model personas and she is not defined by whichever LLM happens to answer a turn.

13.17 adds a provider-independent coordination layer that answers three questions after Mary's authoritative per-turn state has been assembled:

1. How much cognition does this turn deserve?
2. How should that cognition be explained to this creator, given represented communication preferences?
3. What presentation/embodiment intents should accompany the response without claiming an action occurred?

It does **not** create a new identity, personality, memory, relationship store, tool authority, or provider authorization path.

## Architectural rule

> One intelligent Mary, many computational resources.

The language model is a cognitive worker. Mary Core remains the identity and continuity authority.

## Current flow

```text
creator input
    |
    v
canonical Mary Core
    |
    +-- identity / authored character
    +-- relationship + creator profile
    +-- memory + knowledge
    +-- emotion + continuity
    +-- agency + tools
    |
    v
TurnMindState
    |
    v
CognitiveCharacterRuntime
    |
    +-- cognitive mode
    +-- reasoning depth
    +-- latency priority
    +-- knowledge breadth
    +-- communication register
    +-- local-compute preference
    +-- escalation hint
    +-- embodiment intents
    +-- continuity intents
    |
    v
LLM / capability routing under existing hard governance
```

## Modes

The initial deterministic policy intentionally stays simple:

- `direct`: quick factual/look-up style work; prioritize responsiveness and small sufficient compute.
- `relational`: ordinary personal conversation; strongly prefer responsive/local presence when sufficient.
- `balanced`: normal general-purpose work.
- `deliberate`: architecture, research, planning, debugging, story analysis, implementation and other work that benefits from broader/deeper reasoning.

These modes are not provider names. They describe cognitive need.

## Local-first interpretation

`local_preference` is a planning signal, not an authorization rule. It exists because presence and ordinary conversation benefit from low latency, privacy and continuity on the Mac/Windows capability fabric. A difficult turn can express lower local preference so downstream routing may consider stronger remote cognition when policy allows it.

Hard boundaries remain elsewhere:

- private/local-only requests cannot escape to cloud because of this layer;
- paid use is never granted here;
- tool/device actions are never granted here;
- provider/model identity is not exposed to the character unless runtime details are explicitly requested.

## Creator adaptation

The runtime consumes only represented, provenance-filtered creator communication state from the existing relationship user model. Examples include preferred response length, explanation style, technical register and conversational register.

This is deliberately different from guessing a psychological profile from prose. Mary adapts to what she has actually learned or been told, while uncertainty remains uncertainty.

## Embodiment contract

The runtime can emit intents such as:

- `attend_to_user`
- `brighten_expression`
- `soften_expression`
- `increase_gesture_energy`
- `reduce_gesture_energy`
- `controlled_emphasis`
- `brief_thinking_beat`
- `slower_delivery`
- `lively_delivery`

These are presentation intents only. A surface may map them to a 2.5D rig, VRM/Unity avatar, voice prosody, or ignore them entirely. Their presence never means an action actually happened.

## Distributed character direction

The intended compute shape is cooperative rather than model-monolithic:

```text
Mac presence node
  small/fast local inference, retrieval, embeddings, continuity support

Windows embodiment/work node
  avatar/Unity/OBS, audio, Kokoro, larger CPU/RAM jobs, creative services

Railway canonical Core
  identity/state authority and coordination

Cloud/open-model fabric
  optional deeper reasoning and specialist cognition
```

There is still only one Mary. Nodes advertise capabilities; they never own identity.

## 13.16 relationship

13.16 measures provider/model reliability, latency, quality and token efficiency after hard eligibility policy. 13.17 describes what kind of cognition and delivery a Mary turn needs. The safe future connection is:

```text
TurnMind -> 13.17 cognitive need -> hard route eligibility -> 13.16 adaptive ranking -> inference
```

The order is important. Adaptive model intelligence must never bypass privacy, cost, permission, or capability constraints.

## Implementation status

Implemented now:

- `mary/cognition/cognitive_character.py`
- provider-independent `CognitiveCharacterPlan`
- deterministic direct/relational/balanced/deliberate planning
- represented communication-style adaptation
- local-vs-escalation planning hints
- non-action-claiming embodiment intents
- continuity intents
- adapter that consumes the existing `TurnMindState` or a compatible mapping
- deterministic tests including a real `Mary()` + `TurnMindState` compatibility test

Native inclusion as a serialized field inside `TurnMindState` is intentionally deferred until the next whole-file reconciliation pass so the cloud editor does not risk replacing unrelated current work. The adapter already lets current Mary state drive the runtime without creating a second state authority.

## Design target

Mary should be able to answer a recipe question, help reason through a life or project decision, analyze a chapter, debug software, talk casually, and eventually operate authorized digital-world tools while still feeling like the same persistent character.

Intelligence is a capability of Mary, not a costume placed on top of an assistant and not a personality trait that forces her to act like a stereotypical genius.
