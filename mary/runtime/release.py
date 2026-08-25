"""MaryV2 application-release metadata.

This is intentionally separate from Mary's character/identity version.  The
launcher uses APP_VERSION to reason about software updates without changing who
Mary is or mutating her persistent personal state.
"""

from __future__ import annotations

APP_NAME = "MaryV2"
APP_VERSION = "13.1.1"
RELEASE_CHANNEL = "private-v2"
DESKTOP_PHASE = "realtime-cognitive-infrastructure"
