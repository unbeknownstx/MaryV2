# MaryV2 development plan after 13.1.1 consolidation

1. Install the 13.1.1 full overlay on the canonical Windows repo while preserving `.env` and `data/`.
2. Run `python -m scripts.check_mary_13_1`, then the fast/full/release tiers on the real PC. Do not rebuild vectors until canonical state and routing are verified.
3. Run the desktop frontend host build (`npm ci`, `npm run check`, `npm run build`) and live desktop conversation/voice tests.
4. Test the merged mobile protocol 4 surface from the Windows host, then pull the same committed code on the MacBook and run parity checks.
5. Build/sign the native iPhone project in Xcode and point it at the same canonical Mary host.
6. Explicitly build the semantic vector index only after Ollama `nomic-embed-text` is available; keep lexical/FTS as the safe baseline and vectors as derived retrieval.
7. Continue realtime conversation work: true streaming STT/VAD, barge-in, token/sentence TTS pipelining, and interruption-safe audio transport.
8. Add perception providers behind `PerceptionDirector` (screen/image/camera snapshots first, no always-on capture by default).
9. Evolve Skills into explicit capability manifests and use the existing Task Orchestrator/Executor as the basis for task-scoped specialist agents. Agents must remain temporary workers for Mary, never separate owners of Mary's identity/memory.
10. Build the cloud-core/home-node transport on top of NodeRegistry: centralized state/control, distributed compute, outbound private node connections, no duplicate Mary data roots.
11. Continue collecting only explicit Mary-fit feedback so future GPU/LoRA work starts with a clean evaluation/training corpus.
12. When the 24 GB GPU arrives, benchmark larger local dialogue/VLM/STT/TTS/embedding/reranker models behind existing interfaces instead of redesigning Mary's identity architecture around one GPU.
