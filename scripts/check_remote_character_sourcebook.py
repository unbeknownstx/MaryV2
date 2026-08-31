"""Verify the deployed Core sees the authored character sourcebook."""
from __future__ import annotations

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from mary.protocol.client import MaryClient

required = ("MARY_CORE_URL", "MARY_CORE_TOKEN")
missing = [name for name in required if not os.getenv(name)]
if missing:
    raise SystemExit("Missing environment variables: " + ", ".join(missing))

client = MaryClient(
    os.environ["MARY_CORE_URL"],
    token=os.environ["MARY_CORE_TOKEN"],
    device_id="character-sourcebook-check",
    surface="diagnostic",
    timeout=20,
)
state = client.state()
core = state.get("core") or {}
sourcebook = ((state.get("character") or {}).get("sourcebook") or {})

print("instance:", core.get("instance_id"))
print("character_enabled:", sourcebook.get("enabled"))
print("character_records:", sourcebook.get("records"))
print("character_sources:", sourcebook.get("source_names"))
print("character_errors:", sourcebook.get("errors"))
print("character_hash:", sourcebook.get("sourcebook_hash"))
