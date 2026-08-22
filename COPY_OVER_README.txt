MARYV2 12.9 FULL SANITIZED SOURCE

This folder contains the complete 12.9 source/assets/tests snapshot needed to merge over the
existing MaryV2 repo. It intentionally excludes .env, data/, .git, .venv, node_modules,
pytest caches, and desktop/dist so it cannot replace creator secrets/state or stale host builds.

Recommended: use MaryV2_12_9_Uplift_PATCH.zip + INSTALL_12_9.ps1 instead because that installer
backs up every replaced file and verifies hashes.

If you use this full source snapshot manually:
1. Close Mary.
2. Back up your repo and %LOCALAPPDATA%\MaryV2\data.
3. Copy/merge the CONTENTS of this folder into C:\Users\Melvin\Documents\GitHub\MaryV2.
4. Do not delete your existing .env or data folders.
5. Run VERIFY_12_9_WINDOWS.ps1 from the MaryV2 repo root.
