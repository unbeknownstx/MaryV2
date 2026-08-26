"""Launch the authoritative MaryV2 13.2 Core service."""
import os

# Declare the process role before importing Mary runtime modules.
# Hosting provider is replaceable; the architectural role is not.
os.environ.setdefault("MARY_RUNTIME_ROLE", "core")

from mary.protocol.server import run_server


if __name__ == "__main__":
    run_server()
