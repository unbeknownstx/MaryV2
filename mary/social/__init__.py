"""Bounded public/social presence for the one canonical Mary.

The social package stores creator-reviewed public artifacts and draft proposals.
It never owns Mary's identity, personality, relationship, memory, or provider
routing, and it never publishes to an external platform by itself.
"""

from .presence import SocialPresenceRuntime, sanitize_social_context

__all__ = [
    "SocialPresenceRuntime",
    "sanitize_social_context",
]
