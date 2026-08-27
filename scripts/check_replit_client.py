"""Safe MaryV2 Replit/mobile deployment self-check.

No secret values are printed.  With ``MARY_CORE_URL`` and ``MARY_CORE_TOKEN``
configured the script also performs authenticated read-only Core checks.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from mary.protocol.client import MaryClient, MaryProtocolError
from scripts.sync_mobile_web import in_sync

ROOT = Path(__file__).resolve().parents[1]


def flag(name: str) -> bool:
    return bool(str(os.getenv(name, "")).strip())


def main() -> int:
    load_dotenv()
    core_url = str(os.getenv("MARY_CORE_URL", "")).strip().rstrip("/")
    token = str(os.getenv("MARY_CORE_TOKEN", "")).strip()
    mobile_token = str(os.getenv("MARY_MOBILE_TOKEN", "")).strip()

    print("MARYV2 REPLIT / WEB CLIENT CHECK")
    print("=" * 64)
    print(f"mobile_web:       {'READY' if (ROOT / 'mobile_web' / 'index.html').is_file() else 'MISSING'}")
    print(f"native bundle:    {'SYNCED' if in_sync() else 'DRIFT'}")
    print(f"MARY_CORE_URL:    {'CONFIGURED' if core_url else 'NOT CONFIGURED'}")
    print(f"MARY_CORE_TOKEN:  {'CONFIGURED' if token else 'NOT CONFIGURED'}")
    print(f"MARY_MOBILE_TOKEN:{' CONFIGURED' if mobile_token else ' AUTO/NOT SET'}")

    if not core_url:
        print("authority:        local development mode")
        return 0
    if not token:
        print("authority:        remote Core requested but token is missing")
        return 2

    try:
        client = MaryClient(core_url, token=token, device_id="replit-self-check", surface="diagnostic", timeout=8.0)
        health = client.health()
        state = client.state()
        nodes = client.nodes()
    except (MaryProtocolError, OSError, ValueError) as exc:
        print(f"Core live check:  FAIL · {type(exc).__name__}: {exc}")
        return 3

    print("Core live check:  PASS")
    print(f"architecture:     {health.get('architecture', 'unknown')}")
    print(f"core ok:          {health.get('ok', False)}")
    print(f"Mary:             {(state.get('mary') or {}).get('name', 'Mary')}")
    print(f"connected nodes:  {nodes.get('connected', 0)}")
    print("secrets printed:  no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
