# MaryV2 12.12.2 Test Results

Final source verification in the build environment:

- Canonical Python suite: **740 passed, 1 skipped**
- 12.12.2 focused regression set: **9 passed**
- System diagnostics: **54 / 54 PASS**, Healthy `True`
- `scripts.verify_natural_conversation_12_12_2`: **PASS**
- `scripts.verify_performance_pass_install`: **PASS** under the natural-conversation policy
- Complete deterministic/offline release gate: **PASS**
- Desktop JavaScript source syntax (`npm run check`): **PASS**
- Voice Lab plan-only smoke: **PASS**, zero network calls
- Local Model Lab CLI smoke: **PASS**

A production Vite bundle is not claimed from this build environment because the
local `desktop/node_modules` dependency tree is intentionally absent.
`SETUP_WINDOWS.ps1` performs `npm ci`, `npm run check`, and `npm run build` on the
canonical Windows host before launch/release verification.

No live provider, paid TTS, or local Ollama inference benchmark was executed by
the deterministic release gate. Those measurements are intentionally host/live
lab work.
