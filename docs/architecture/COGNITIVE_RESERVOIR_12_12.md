# Cognitive Reservoir Architecture — 12.12

## Purpose

The reservoir reduces the number of turns where Mary has to ask a language
model to rediscover information she already represents locally.

It is **not** a new authority system and it is **not** a replacement memory
store.

```text
Authoritative Mary state
        │
        ├── identity
        ├── relationship / creator model
        ├── episodic + semantic memory
        ├── preferences / developed self
        ├── verified knowledge
        └── current character state
                │
                ▼
      rebuildable projections
                │
                ▼
      Cognitive Reservoir (SQLite/FTS5)
                │
        ┌───────┴────────┐
        ▼                ▼
 local dialogue     model prompt retrieval
        │                │
        └──── escalation ┘
```

## Safety invariants

1. Reservoir corruption cannot redefine Mary.
2. Reservoir deletion cannot delete canonical Mary state.
3. Every indexed record preserves source/authority/confidence metadata.
4. Test-probe residue is excluded from normal projections.
5. Episodic history remains episodic; indexing it does not promote it to truth.
6. External/search/YouTube text is never automatically durable creator truth.
7. Storage is bounded and derived low-authority entries are pruned before
   authoritative projections.

## Thread model

Mary Desktop runs a conversation pipeline on a Qt worker thread while dashboard
status may be read from the GUI thread.  The SQLite reservoir therefore uses a
single `check_same_thread=False` connection protected by an `RLock`.  No
unprotected concurrent use of the connection is permitted.

## Retrieval tiers

FTS5 is always sufficient for baseline operation.  Optional local embeddings
may improve semantic matching later, but embeddings are never required for
launch or basic conversation.
