"""Report content-free recoverable Mary continuity roots on this host.

This command is intentionally read-only. It never merges local state into the
canonical remote Core. Use it to answer the first recovery question: is there
older Mary state on this PC that is worth explicitly restoring/importing?
"""

from __future__ import annotations

import json

from mary.core.config import PathConfig
from mary.desktop.continuity_recovery import discover_local_continuity


def main() -> int:
    root = PathConfig().root
    rows = discover_local_continuity(root)
    print(json.dumps({"roots": rows}, indent=2, ensure_ascii=False))
    candidates = [row for row in rows if row.get("recoverable_candidate")]
    if candidates:
        print(f"\nRecoverable local continuity candidates: {len(candidates)}")
        print("No state was changed. Review before any explicit recovery/import.")
    else:
        print("\nNo recoverable local continuity was found in the bounded conventional roots.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
