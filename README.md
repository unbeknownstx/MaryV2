# MaryV2

MaryV2 is a persistent AI character/runtime built around a single coordinated Mary instance. It connects identity, personality, memory, cognition, learning, knowledge, agency, bounded autonomy, conversation, expression, avatar/audio interfaces, web research, and approval-gated development tools.

Creator identity in Mary-facing project logic: **Unbe**.

## Run Mary

```powershell
python main.py
```

Equivalent entry points:

```powershell
python -m scripts.run_mary
python -m mary.runtime.interactive
```

All three use the canonical `MaryApplication` runtime.

## Verify the release

Run the complete local verification from the repository root:

```powershell
python -m scripts.run_release_verification
```

For deterministic/offline verification that skips the configured live LLM test:

```powershell
python -m scripts.run_release_verification --offline
```

To explicitly include one live public web-search smoke test:

```powershell
python -m scripts.run_release_verification --live-web
```

See [`docs/verification.md`](docs/verification.md) for the important difference between the PowerShell prompt and Mary's interactive `You:` prompt.

## Tool safety model

- Read-only project/file inspection is bounded to Mary's configured workspace.
- Public web access is intentional and approval-scoped according to the request path.
- Filesystem writes/deletes/moves require a separate creator approval turn.
- Code changes are proposed as exact diffs, syntax-checked, and remain unchanged until approval.
- Stale code proposals are rejected if the source changed after the proposal was created.
- Static code analysis does not execute source code.
- Arbitrary shell/Python execution is not provided through Mary's normal tool path.

## Interactive help

While Mary is running:

```text
/help
```

shows which commands belong in Mary versus PowerShell.

```text
/pending
```

shows pending tool requests. If exactly one request is pending, `approve` or `reject` is enough; Mary will not guess when multiple requests are pending.
