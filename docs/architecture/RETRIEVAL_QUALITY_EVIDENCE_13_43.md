# Retrieval Quality Evidence 13.43

MaryV2 13.43 adds deterministic retrieval evaluation for the existing lexical, vector, and future hybrid retrieval lanes. It does **not** add another memory store or RAG framework.

Mary already has canonical memory owners, a PostgreSQL/FTS derived projection, pgvector search, and embedding-space fingerprints. The missing piece was evidence answering whether a derived retrieval lane is actually better enough to promote.

## Metrics

`mary.mind.retrieval_benchmark` evaluates stable benchmark cases using only expected record IDs and ranked returned record IDs. It computes:

- hit rate at K;
- mean reciprocal rank (MRR);
- precision at K;
- recall at K;
- result coverage.

Benchmark scorecards contain case IDs and metrics, not query prose, memory content, retrieved snippets, embeddings, or private creator data.

## Promotion policy

`promotion_decision()` compares a candidate lane with a baseline. By default, a candidate is held unless it has:

- at least 8 measured cases;
- at least 90% coverage;
- hit rate at K of at least 0.75;
- MRR of at least 0.60;
- no material hit-rate or MRR regression against the baseline.

The thresholds are deliberately conservative and advisory. A strong latency benchmark cannot compensate for retrieving the wrong memory.

## Architectural boundaries

- Canonical episodic/semantic memory remains unchanged.
- PostgreSQL/pgvector remains a derived projection only.
- Embedding vectors remain rebuildable derived state.
- Embedding identity/fingerprint checks remain mandatory for comparing vectors.
- A scorecard does not silently switch retrieval policy.
- Promotion evidence never grants tool/model execution permission.

## Intended workflow

1. Define deterministic cases with stable expected record IDs.
2. Run the same cases through lexical FTS and a candidate vector/hybrid lane.
3. Strip results down to ranked record IDs with `result_ids()`.
4. Build scorecards with `evaluate_lane()`.
5. Compare candidate vs baseline with `promotion_decision()`.
6. Promote only through Mary's explicit retrieval-policy/configuration path after the measured evidence is acceptable.

This follows the same Mary-wide rule used for compute and model routing: capability claims are useful, but measured correctness outranks advertising and speed.
