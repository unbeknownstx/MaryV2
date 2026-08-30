MARYV2 13.1.1 COMPLETE VALIDATION

Run this from the MaryV2 repository root after applying the Memory Integrity
Hotfix V2.

Command:
    powershell -ExecutionPolicy Bypass -File .\MARYV2_13_1_1_COMPLETE_VALIDATION.ps1

What it validates:
- live memory integrity preflight (read-only);
- Mary 13.1 doctor;
- canonical fast test tier;
- canonical full test tier;
- canonical release test tier;
- Production Hybrid 12.12.3 verifier when present;
- .env + entire data/ tree are hash-checked before/after automated testing;
- desktop host-native npm ci;
- desktop npm run check;
- desktop npm run build;
- semantic-vector status only (NO vector rebuild).

It stops immediately on the first failure and writes a timestamped log in the
repository root.

What remains after this passes:
- manual terminal conversation/recall smoke;
- manual desktop text UI smoke;
- microphone/STT/TTS/interruption/anti-echo smoke;
- mobile/native-iPhone connectivity and voice smoke;
- then commit via GitHub Desktop.

The complete gate intentionally does not rebuild semantic vectors.
