MaryV2 12.8.1 Windows Cross-Platform Path Test Hotfix

Replace:
  mary/core/config.py

Reason:
  On a Windows host, pytest simulates frozen macOS by monkeypatching sys.platform
  and HOME. pathlib.Path.home() still follows the Windows host environment, so
  the macOS Application Support tests resolve the real Windows home instead of
  the temporary HOME. This hotfix adds a platform-aware home resolver that
  honors HOME for simulated macOS/Linux and USERPROFILE/HOMEDRIVE+HOMEPATH on
  Windows before falling back to Path.home().

Validated in the reference tree:
  tests/core/test_standalone_paths.py -> 7 passed
  full pytest -> 660 passed, 1 skipped
  python -m scripts.run_release_verification --offline -> PASS

After replacing the file on Windows, run:
  python -m pytest tests/core/test_standalone_paths.py -q
  python -m pytest -q
  python -m scripts.run_release_verification --offline

Then resume:
  .\scripts\first_boot_windows.ps1
