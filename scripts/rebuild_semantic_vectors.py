"""Explicit MaryV2 13.1 semantic-vector rebuild helper.

This command is intentionally opt-in. It never downloads a model, never calls a
cloud embedding provider, and never changes canonical memory. It embeds the
rebuildable cognitive reservoir using the configured local Ollama embedding
model and stores a derived SQLite vector index beside the reservoir.
"""
from __future__ import annotations

import argparse
import json

from mary.runtime.application import create_application


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Mary's optional local semantic vector index.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum authoritative reservoir records to embed.")
    parser.add_argument("--status", action="store_true", help="Show retrieval status only; do not embed anything.")
    args = parser.parse_args()

    app = create_application(name="mary_vector_rebuild")
    try:
        retriever = app.mary.mind.retrieval
        state = retriever.status()
        print("MARYV2 13.1 HYBRID MEMORY RETRIEVAL")
        print("=" * 72)
        print(f"Mode: {state.get('mode')}")
        print(f"Embedding model: {state.get('embedding_model')}")
        print(f"Vector records: {dict(state.get('vector_index', {}) or {}).get('records', 0)}")
        print("Authority: vectors retrieve candidates only; canonical memory/provenance stays authoritative.")

        if args.status:
            return 0

        client = retriever.embedding_client
        try:
            ollama_up = bool(client.available())
        except Exception:
            ollama_up = False
        if not ollama_up:
            print("\nOllama is not reachable. Start Ollama first, then rerun this command.")
            return 2
        try:
            model_ready = bool(client.model_available())
        except Exception:
            model_ready = False
        if not model_ready:
            print(f"\nEmbedding model is not installed: {client.model}")
            print(f"Install it explicitly with: ollama pull {client.model}")
            print("Mary will keep using lexical retrieval until you do; nothing is broken.")
            return 3

        # Refresh the derived lexical reservoir first, then derive vectors from
        # the same authoritative sources. Neither operation mutates canonical
        # identity/memory/relationship state.
        app.mary.mind.maintenance(force=True)
        result = app.mary.mind.rebuild_vectors(limit=args.limit)
        print("\nRESULT")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 4
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
