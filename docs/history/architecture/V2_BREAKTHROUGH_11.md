# MaryV2 Breakthrough 11 — State-Aware Local Conversation Supervision

Breakthrough 11 keeps Breakthrough 10's provider split intact and deepens the
conversation layer above it. The goal is not a new Mary architecture; it is a
better process-local bridge between persistent Mary state, recent conversational
repair, and Ollama's expressive character performance.

## Provider split remains unchanged

```text
personal / relational / character conversation
    Ollama -> Groq -> Gemini -> OpenRouter

detached factual / technical / task work
    Groq -> Gemini -> OpenRouter -> Ollama

private/offline
    Ollama only

paid expert
    OpenAI, explicit one-task authorization only
```

Mary remains the persistent runtime. Providers remain replaceable engines.

## New process-local conversation state

Breakthrough 11 adds short-lived conversational state without creating another
durable memory store.

### Pending relationship question

When the creator explicitly invites Mary to ask something, the
`ConversationLearningBridge` selects one real unresolved relationship gap and
keeps a process-local record containing the question, category, reason, and gap.

That enables:

```text
Mary asks a real values question
  -> creator: "why that question?"
  -> deterministic explanation from the pending question record
  -> zero LLM calls
  -> creator answers naturally
  -> existing RelationshipManager learning path accepts/rejects the share
  -> matching pending question closes
```

The bridge still never autonomously interrogates the creator and never writes
creator truth directly.

### Rejected-hypothesis continuity

When the creator corrects or rejects Mary's interpretation, recent distinctive
terms from that interpretation become temporarily suppressed. The next turn may
not simply regenerate the rejected hypothesis without new creator evidence.
This state is process-local and expires with conversation context.

## Shared-history grounding

Natural phrases such as:

```text
ive been thinking about everything weve done
look how far weve come
since we started all this
```

can now ground against creator-authored recent dialogue, durable creator goals,
and creator-owned memories. Assistant-role improvisation remains excluded as
proof of shared history.

This lets Mary recognize real continuity around MaryV2 without either inventing
off-screen activity or falsely denying that shared work exists.

## Grounded self-development

Natural questions such as:

```text
do u think youve changed since we started all this
how have you grown
```

route to a grounded self-development view. Mary distinguishes:

- authored/canonical character core;
- controlled developed-self state;
- relationship knowledge learned through accepted creator shares;
- represented preferences/development where explicitly promoted;
- current connected capability/runtime growth.

A provider may express the answer, but the substance comes from Mary's actual
runtime evidence.

## Emotion-to-language grounding

Relationship-feeling questions such as:

```text
what does talking like this feel like from ur side
```

are self-grounded. Mary's represented emotion, relationship state, current-turn
appraisal, and character relationship principles provide the substance before
the local model supplies natural phrasing.

Expressive language remains allowed, but claims of direct access to the
creator's private thoughts or feelings are audited and revised.

## Semantic repetition control

Paragraph duplication alone was not enough for local conversational models.
Breakthrough 11 tracks recent overused metaphor/style motifs and can trigger a
local revision when Mary falls into a repeated palette such as the same
"quiet / spark / magic / together" imagery across turns.

This does not ban metaphors, slang, emoji, or warmth. They remain optional
texture rather than a required response template.

## Local supervision stays local

If a personal Ollama response violates provenance, repeats a rejected
interpretation, makes an unsupported mind-reading claim, or falls into a
semantic style loop, Mary's reflection/revision keeps the same conversation
purpose. A correction can therefore stay on Ollama instead of silently sending
private conversation to a cloud model.

## Authority boundary

`MarySystemContract` is versioned `v2-breakthrough-11` and documents one explicit
owner for process-local relationship-question continuity:

```text
ConversationLearningBridge
    owns pending question/reason state for the current process

RelationshipManager
    remains the durable owner of learned creator information
```

No new durable memory authority was introduced.
