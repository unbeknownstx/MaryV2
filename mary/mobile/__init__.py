"""MaryV2 mobile/web companion surface.

The mobile surface is a transport and presentation layer over the canonical
MaryApplication. It does not own identity, memory, personality, cognition, or
provider routing.

Server symbols are imported lazily so ``python -m mary.mobile.server`` can run
without pre-importing the server module through this package.
"""

from .audio import MobileSpeechAudio, MobileSpeechService

__all__ = [
    "MaryMobileRuntime",
    "MaryMobileServer",
    "MobileSpeechAudio",
    "MobileSpeechService",
    "run_mobile_server",
]


def __getattr__(name: str):
    if name in {
        "MaryMobileRuntime",
        "MaryMobileServer",
        "run_mobile_server",
    }:
        from .server import (
            MaryMobileRuntime,
            MaryMobileServer,
            run_mobile_server,
        )

        exports = {
            "MaryMobileRuntime": MaryMobileRuntime,
            "MaryMobileServer": MaryMobileServer,
            "run_mobile_server": run_mobile_server,
        }
        return exports[name]

    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )
