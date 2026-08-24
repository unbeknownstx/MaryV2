"""MaryV2 mobile/web companion surface.

The mobile surface is a transport and presentation layer over the canonical
MaryApplication.  It does not own identity, memory, personality, cognition, or
provider routing.
"""

from .server import MaryMobileRuntime, MaryMobileServer, run_mobile_server

__all__ = ["MaryMobileRuntime", "MaryMobileServer", "run_mobile_server"]
