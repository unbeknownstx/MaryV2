"""Natural-input normalization for MaryV2 intent matching.

Mary should understand Unbe's ordinary typing without requiring benchmark-style
punctuation or perfect grammar.  This module is deliberately conservative: it
normalizes only a small set of high-confidence chat shorthands for *matching*.
The original user text is never rewritten before it reaches memory, dialogue,
or the language model.
"""

from __future__ import annotations

import re
import unicodedata


_TOKEN_REPLACEMENTS = {
    "u": "you",
    "ur": "your",
    "r": "are",
    "im": "i'm",
    "ive": "i've",
    "id": "i'd",
    "ill": "i'll",
    "dont": "don't",
    "doesnt": "doesn't",
    "didnt": "didn't",
    "cant": "can't",
    "couldnt": "couldn't",
    "wouldnt": "wouldn't",
    "shouldnt": "shouldn't",
    "wont": "won't",
    "isnt": "isn't",
    "arent": "aren't",
    "wasnt": "wasn't",
    "werent": "weren't",
    "havent": "haven't",
    "hasnt": "hasn't",
    "thats": "that's",
    "whats": "what's",
    "youre": "you're",
    "youve": "you've",
    "weve": "we've",
    "theyre": "they're",
    "alot": "a lot",
    "kinda": "kind of",
    "sorta": "sort of",
}


def normalize_for_matching(text: str) -> str:
    """Return a punctuation-light, chat-tolerant form for intent matching only."""

    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.replace("’", "'").replace("‘", "'").lower().strip()
    value = re.sub(r"[^\w'/:+.-]+", " ", value, flags=re.UNICODE)
    tokens = value.split()
    normalized: list[str] = []
    for token in tokens:
        replacement = _TOKEN_REPLACEMENTS.get(token, token)
        normalized.extend(replacement.split())
    value = " ".join(normalized)
    value = re.sub(r"\s+", " ", value).strip(" .?!,;:")
    return value


def looks_like_question(text: str) -> bool:
    """Recognize natural questions even when the user omits ``?`` punctuation."""

    raw = str(text or "").strip()
    if not raw:
        return False
    if raw.endswith("?"):
        return True

    value = normalize_for_matching(raw)
    if not value:
        return False

    words = value.split()
    first = words[0]
    if first in {"what", "why", "how", "when", "where", "who", "which"}:
        return True
    if first in {"can", "could", "would", "should", "will", "are", "is", "was", "were", "have", "has"}:
        return len(words) >= 2
    if first in {"do", "does", "did"}:
        return len(words) >= 2 and words[1] in {
            "you", "i", "we", "they", "he", "she", "it", "your", "my", "our",
        }
    return False
