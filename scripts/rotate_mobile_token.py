"""Rotate the generated Mary Mobile bearer token safely."""

from __future__ import annotations

import os
from pathlib import Path
import secrets

from dotenv import load_dotenv

from mary.core.config import Config


def main() -> None:
    load_dotenv()
    configured = os.getenv("MARY_MOBILE_TOKEN", "").strip()
    if configured:
        print("MARY_MOBILE_TOKEN is set in the environment.")
        print("Change that secret in your host/Replit Secrets instead of rotating the persisted file.")
        return

    config = Config.from_environment()
    token_path = Path(config.paths.data).expanduser().resolve() / "mobile" / "access_token.txt"
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    token_path.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(token_path, 0o600)
    except OSError:
        pass

    print("Mary Mobile token rotated.")
    print(f"Token file: {token_path}")
    print()
    print("NEW MOBILE ACCESS TOKEN")
    print(token)
    print()
    print("Restart scripts.run_mobile, then replace the saved token on your phone.")


if __name__ == "__main__":
    main()
