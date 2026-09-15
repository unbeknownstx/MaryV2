# PostgreSQL + pgvector Projection

MaryV2 can optionally project approved durable memory into PostgreSQL and use
PostgreSQL full-text search plus pgvector as an additional retrieval source.

This layer is deliberately downstream of the canonical Mary Core. It does not
own identity, relationship state, developed self, memory truth, agency,
permissions, or continuity.

## Authority boundary

```text
canonical Mary Core
      |
      | approved durable memory only
      v
PostgreSQL projection
      |\
      | \-- full-text candidates
      \---- pgvector candidates
               |
               v
       evidence returned to Mary
```

Working memory is intentionally excluded. A database connection must never turn
ephemeral context into durable memory.

The database is also not a startup dependency. If PostgreSQL, psycopg, or the
pgvector extension is unavailable, Mary Core, Desktop, Mobile, Ollama,
llama.cpp, and the existing local memory/retrieval path continue to work.

## Optional dependency

```bash
python -m pip install -r requirements-postgres.txt
```

The dependency is intentionally separate from `requirements.txt`.

## Configuration

A connection string alone does not enable the projection. Explicit opt-in is
required because platforms such as Railway may inject `DATABASE_URL` for other
reasons.

```bash
export MARY_POSTGRES_URL="postgresql://USER:PASSWORD@HOST:5432/DATABASE"
export MARY_POSTGRES_ENABLED=1
```

`DATABASE_URL` is accepted as a fallback if `MARY_POSTGRES_URL` is absent.
Credentials and query parameters are omitted from status output.

Optional controls:

```bash
export MARY_POSTGRES_RETRIEVAL=1
export MARY_POSTGRES_AUTO_SYNC=0
export MARY_POSTGRES_CONNECT_TIMEOUT=5
export MARY_POSTGRES_STATEMENT_TIMEOUT_MS=4000
export MARY_POSTGRES_MAX_SYNC_RECORDS=10000
```

`MARY_POSTGRES_RETRIEVAL` is a separate gate from storage. Enabling durable
projection does not silently add database candidates to ordinary recall.

`MARY_POSTGRES_AUTO_SYNC` is reserved for runtime wiring after production
backup/recovery acceptance. The initial implementation uses explicit sync so a
new external database cannot unexpectedly become part of Mary's write path.

## Commands

Safe local status; does not contact the database:

```bash
python -m scripts.postgres_projection status
```

Create the base schema and attempt to enable pgvector:

```bash
python -m scripts.postgres_projection init
```

Synchronize the current approved episodic + semantic memory projection:

```bash
python -m scripts.postgres_projection sync
```

Query PostgreSQL full-text retrieval candidates:

```bash
python -m scripts.postgres_projection search "streaming plans"
```

Build pgvector rows with Mary's existing local Ollama embedding client:

```bash
python -m scripts.postgres_projection embed --limit 1000
```

The embedding command is intended to run on a machine that can actually reach
the configured Ollama embedding model. It records the embedding identity along
with every vector so incompatible embedding spaces are never compared.

## Schema

`mary_projection_records` stores the durable projection:

- `record_id`
- `record_type` (`episodic` or `semantic`)
- `content`
- `confidence`
- `source`
- bounded JSON metadata
- content hash
- update timestamp

`mary_projection_vectors` exists only when the PostgreSQL `vector` extension is
available. It stores:

- record id
- embedding model
- embedding identity fingerprint
- content hash
- vector

The content hash prevents a stale vector from matching a changed record.

## Why this is a projection first

Mary already has a working canonical persistence path and a rebuildable local
SQLite/FTS/vector reservoir. Replacing that in one migration would combine two
separate risks: moving canonical state and introducing a network dependency.

The safer sequence is:

1. create the PostgreSQL projection;
2. sync and compare it against canonical memory;
3. exercise full-text and pgvector retrieval;
4. verify backup/restore and outage behavior;
5. benchmark cloud retrieval versus local retrieval;
6. only then consider promoting selected durable storage responsibilities
   behind the existing Core-owned memory interface.

At every stage, retrieval results remain candidates rather than automatic Mary
truth.

## Future MCP/database connections

If a database is later exposed through MCP, expose narrowly typed tools such as
`lookup_project`, `search_assets`, or `get_chapter_metadata`. Do not expose raw
unrestricted SQL to the model. MCP discovery remains separate from permission,
and the existing Mary capability/tool allowlists remain authoritative.
