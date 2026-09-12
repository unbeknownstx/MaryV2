"""Print safe readiness for optional research-derived specialist backends."""
from __future__ import annotations

import json

from mary.distributed.specialist_catalog import specialist_status


def main() -> int:
    status = specialist_status()
    print("MARYV2 13.14 SPECIALIST BACKENDS")
    print("=" * 64)
    for item in status["backends"]:
        print(f"{item['backend_id']:<22} {item['state']:<16} {item['role']}")
    print("\nJSON")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
