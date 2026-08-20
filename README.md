# MaryV2

MaryV2 is a private persistent character runtime for **Mary**. Mary existed as a character before this software; the runtime is the machinery that lets the same character converse, remember selectively, learn through controlled paths, use tools/models, speak through the desktop, survive restarts, and remain independent from any one LLM provider.

## V2 invariants

- Mary is not the provider. Groq, Gemini, OpenRouter, Ollama, and optional paid OpenAI are replaceable capabilities.
- Persistent state is bounded. Persistence means continuity, not perfect recall or infinite storage.
- Active LLM context is selective and bounded; stored history is never dumped wholesale into prompts.
- Temporary task reasoning does not automatically become durable memory, relationship state, or developed self.
- Model output is advisory evidence. Tests, local state, authoritative sources, and explicit creator statements can outrank it.
- Paid OpenAI is excluded from `free_first` and requires explicit task-level authorization.
- Private/offline generation uses Ollama only.
- Tool capability and permission are separate. Consequential writes/actions remain approval-gated.
- Persistent JSON state is atomically replaced with a finite backup chain and recovery support.
- Every long-lived collection, task ledger, provider route, context path, and backup chain has a hard ceiling.

## Normal provider policy

```text
character conversation: Ollama -> Groq -> Gemini -> OpenRouter
task/general free_first: Groq -> Gemini -> OpenRouter -> Ollama
private/offline: Ollama only
paid expert: OpenAI (explicit task authorization only)
```

Ordinary personal/relational conversation is local-first by default. This keeps Mary's everyday voice close to her persistent local runtime and private machine while preserving free cloud fallback if Ollama is unavailable. Detached factual/technical/task work is classified separately by the authoritative TurnPolicyEngine so stronger external capabilities can be used intentionally without making cloud models Mary's default conversational voice.

## Run Mary in the terminal

From the repository root with the virtual environment active:

```powershell
python -m scripts.run_mary
```

A developer convenience shim reaches the exact same runtime:

```powershell
python run_mary.py
```

Useful commands while Mary is running:

```text
/help       command help
/state      display-safe live character/runtime state
/resources  provider/token/paid-resource counters
/route      conversation/task route policy + last actual provider
/contract   display-safe architecture/authority contract
/last       last-turn provider, turn-policy, and reasoning metadata
/pending    approval-gated tool requests
/audit      read-only audit for obvious development/test creator-state residue
```

## Run the desktop

Install/build once on Windows:

```powershell
python -m pip install -r requirements-desktop.txt
cd desktop
npm ci
npm run build
cd ..
```

Then:

```powershell
python -m scripts.run_desktop
```

The desktop is a presentation layer over the same canonical `MaryApplication`; it does not own a second Mary.

## Verify V2

The canonical no-spend release gate is:

```powershell
python -m scripts.run_release_verification --offline
```

This explicitly disables live LLM/OpenAI pytest flags in child processes. A normal test or release run must not spend paid OpenAI credits.

For the full local hard-test sequence:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\hard_test_v2.ps1
```

## Standalone Windows build

After the hard-test gate is green:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

The packaged app uses writable user state outside the frozen bundle by default. Set `MARY_PORTABLE=1` only when a portable side-by-side `data/` directory is intentionally desired.

See:

- `docs/architecture/V2_BREAKTHROUGH_10.md`
- `docs/architecture/V2_FINAL_RUNTIME.md`
- `docs/V2_HARD_TEST.md`
- `desktop/README.md`
