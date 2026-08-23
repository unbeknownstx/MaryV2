"""Display-safe local mind/reservoir status for MaryV2."""
from __future__ import annotations
import json
from mary.runtime.application import create_application


def main() -> int:
    app = create_application(name="mind-status")
    try:
        print(json.dumps(app.mary.mind.status(), indent=2, default=str))
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
