MARYV2 13.1.1 MEMORY HOTFIX

Fixes:
- embedded "remember this / core memory" authorization;
- accidental word collapse such as "memoryto";
- false storage for recall/ordinary memory phrases;
- mixed-perspective confirmation mangling such as "you and you";
- keeps simple fact confirmation behavior;
- adds regression tests and runs the cognition test file.

Use:
Put MARYV2_13_1_1_MEMORY_HOTFIX.ps1 in the MaryV2 repository root, then run:

powershell -ExecutionPolicy Bypass -File .\MARYV2_13_1_1_MEMORY_HOTFIX.ps1

The script creates timestamped backups first.
It does not intentionally modify .env, data/, or Mary's live memory files.
