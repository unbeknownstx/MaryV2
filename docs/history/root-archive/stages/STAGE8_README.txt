MaryV2 13.2 Stage 8 — low-latency capability node + Core Ollama provider

Drop this package into the MaryV2 repository root. It contains source/tests/scripts only and intentionally contains NO /data files.

Key changes:
- long-poll capability delivery replaces the fixed 2-second polling gap
- device task broker runs independently from the canonical Mary turn lock
- remote Core can use a connected device as the existing ollama provider
- Core requests bounded model roles; the device owns concrete model selection
- existing local role contract is preserved: conversation_fast uses MARY_OLLAMA_CONVERSATION_MODEL; engaged/general uses MARY_OLLAMA_MODEL; utility uses MARY_OLLAMA_UTILITY_MODEL
- no arbitrary model IDs, shell commands, filesystem paths, or raw provider payloads cross the task boundary
