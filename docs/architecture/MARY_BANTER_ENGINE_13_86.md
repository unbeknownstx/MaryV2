# MaryV2 13.86 — Banter / Wit Engine

## Goal

Make Mary's authored wit operational without creating a second personality, memory,
dialogue generator, or avatar authority.

The runtime path is:

```text
current turn + bounded recent session context
  -> deterministic banter opportunity brief
  -> existing TurnMind character_expression
  -> existing DialoguePlanner
  -> existing one-pass language realization
  -> existing ExpressionDirector / DeliveryPlan
  -> canonical PerformancePacket / renderer
```

There is no mandatory extra LLM call and no autonomous joke loop.

## Runtime owner

`mary.personality.banter` is a projection/helper layer only.

It may:
- decide whether this turn has a concrete playful opening;
- propose up to three comedic angles;
- expose a deterministic structural scorer for evaluation;
- expose a bounded session-only callback cue;
- give the existing performance path timing metadata.

It may not:
- persist memory;
- mutate personality or relationship state;
- create durable facts from a joke;
- override serious character context;
- create avatar state;
- call a model;
- auto-train or auto-promote an adapter.

## Opportunity selection

Banter can activate from:
- an explicit roast / trash-talk invitation;
- competitive overconfidence;
- a harmless self-own;
- shared laughter;
- familiar casual game/stream language;
- the existing `tease` continuity drive.

It is deliberately not a global "sass percentage." If there is no specific angle,
normal conversation wins.

Serious character patterns suppress optional banter before generation:
- grief / hurt;
- moral boundaries;
- vulnerable-person context;
- pressure;
- anger.

## Candidate angles

The engine proposes strategies, not prewritten jokes:

- `callback` — twist a safe recent session cue;
- `dry_reversal` — invert the current framing;
- `affectionate_roast` — tease the behavior/moment rather than identity;
- `absurd_escalation` — take the situation to one ridiculous implication;
- `specific_observation` — land on a concrete contradiction or tiny failure.

At most three are projected into the dialogue contract. The provider is told to use
at most one strong shot and to skip the joke entirely if none lands naturally.

## Callback boundary

Callbacks currently use only already-projected recent conversation.

They are:
- bounded;
- session-only;
- filtered away from obvious grief, trauma, medical, financial-crisis and similar
  sensitive contexts;
- never written into durable memory by this subsystem;
- never represented as proof of a durable fact.

Long-term running bits should later use the existing governed memory/experience
pipeline rather than a new banter database.

## Wit scoring

`score_banter_candidate()` is deterministic and model-free. It rewards:
- specificity to the current beat;
- brevity;
- an earned callback when one exists;
- Mary character match.

It penalizes:
- canned generic insults;
- repeated recent lines;
- assistant boilerplate;
- explaining the joke after the punchline.

The scorer is an evaluation aid. A low score is permission to omit banter, not
permission to rewrite Mary's semantic answer or add another model pass.

## Embodiment

The existing `ExpressionDirector` remains authoritative for delivery.

When the same TurnMind turn contains active banter, DeliveryPlan metadata now carries:
- banter active/inactive;
- intensity;
- target;
- opportunity type;
- candidate technique names;
- callback scope (never raw callback text).

High-intensity banter can project a dry pause, direct gaze, head tilt and smirk while
the existing performance-beat system still owns timing. Live2D, 2.5D and VRM renderers
can all consume the same canonical acting score.

## Training boundary

Banter does not create a new dataset pipeline.

Creator-approved banter examples, corrections and preference pairs belong in the
existing Mary Dataset v1 / sourcebook / feedback pipeline. Ordinary chats and runtime
callbacks are not silently harvested for training.

## Acceptance

13.86 is accepted when:

1. a light competitive/self-own turn can activate banter without literal "roast me";
2. serious context suppresses it;
3. safe recent context can produce a session-only callback angle;
4. generic insults score below specific compact lines;
5. DialoguePlanner receives bounded candidate angles without another LLM call;
6. ExpressionDirector projects banter timing/embodiment metadata through the existing
   DeliveryPlan;
7. no new memory, identity, relationship, model, or avatar owner is introduced.
