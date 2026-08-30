MARYV2 13.1.1 COMPLETE VALIDATION V2

This replaces the first COMPLETE_VALIDATION script, whose memory-preflight
Python quoting was not compatible with Windows PowerShell.

V2 uses a PowerShell-native read-only memory preflight and then runs:
- Mary 13.1 doctor (when present)
- scripts/test_fast.ps1
- scripts/test_full.ps1
- scripts/test_release.ps1
- Production Hybrid 12.12.3 verifier (when present)
- .env + data/ hash integrity checks
- desktop npm ci
- desktop npm run check
- desktop npm run build
- semantic vector status only (no rebuild)

Run from the MaryV2 repository root:

powershell -ExecutionPolicy Bypass -File .\MARYV2_13_1_1_COMPLETE_VALIDATION_V2.ps1

If the memory preflight reports memoryto or duplicate promise memories,
run MARYV2_13_1_1_MEMORY_INTEGRITY_HOTFIX_V2.ps1 first.
