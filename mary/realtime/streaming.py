"""Provider-neutral incremental text streaming primitives for MaryV2.

These objects coordinate partial model output with sentence-oriented speech
without making any provider, TTS engine, or external service a Mary Core
startup dependency. Cancellation is cooperative and scoped to one turn.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import Event, RLock
from typing import Iterable, Iterator
import re


@dataclass(frozen=True)
class GenerationDelta:
    text: str
    sequence: int
    final: bool = False


@dataclass(frozen=True)
class SentenceSegment:
    text: str
    sequence: int
    final: bool = False


class TurnCancellation:
    """Cooperative per-turn cancellation shared by generation and speech."""

    def __init__(self) -> None:
        self._event = Event()
        self._lock = RLock()
        self._reason = ""
        self._generation = 0

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def cancel(self, reason: str = "cancelled") -> int:
        with self._lock:
            if not self._event.is_set():
                self._reason = " ".join(str(reason or "cancelled").split())[:160]
                self._generation += 1
                self._event.set()
            return self._generation

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise StreamCancelled(self.reason or "cancelled")


class StreamCancelled(RuntimeError):
    pass


class SentenceStreamAssembler:
    """Turn arbitrary text deltas into lossless, speech-sized segments."""

    _ABBREVIATIONS = {
        "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "vs.",
        "etc.", "e.g.", "i.e.", "a.m.", "p.m.", "u.s.", "u.k.",
    }
    _BOUNDARY = re.compile(r"[.!?](?:[\"'”’)]*)\s+|\n+")

    def __init__(self, *, max_chars: int = 320) -> None:
        self.max_chars = max(40, min(2000, int(max_chars)))
        self._buffer = ""
        self._sequence = 0
        self._reconstructed: list[str] = []

    @staticmethod
    def _looks_decimal(text: str, punctuation_index: int) -> bool:
        return (
            punctuation_index > 0
            and punctuation_index + 1 < len(text)
            and text[punctuation_index - 1].isdigit()
            and text[punctuation_index + 1].isdigit()
        )

    def _safe_boundary(self) -> int | None:
        for match in self._BOUNDARY.finditer(self._buffer):
            end = match.end()
            candidate = self._buffer[:end]
            punct_index = max(candidate.rfind("."), candidate.rfind("!"), candidate.rfind("?"))
            if punct_index >= 0 and self._looks_decimal(candidate, punct_index):
                continue
            tail = candidate[: punct_index + 1].strip().casefold() if punct_index >= 0 else ""
            last_token = tail.rsplit(maxsplit=1)[-1] if tail else ""
            if last_token in self._ABBREVIATIONS:
                continue
            return end
        if len(self._buffer) > self.max_chars:
            split = self._buffer.rfind(" ", 0, self.max_chars + 1)
            return split + 1 if split >= 20 else self.max_chars
        return None

    def feed(self, text: str) -> list[SentenceSegment]:
        value = str(text or "")
        if not value:
            return []
        self._buffer += value
        emitted: list[SentenceSegment] = []
        while True:
            boundary = self._safe_boundary()
            if boundary is None:
                break
            raw = self._buffer[:boundary]
            self._buffer = self._buffer[boundary:]
            if raw:
                segment = SentenceSegment(raw, self._sequence, False)
                self._sequence += 1
                self._reconstructed.append(raw)
                emitted.append(segment)
        return emitted

    def finish(self) -> list[SentenceSegment]:
        if not self._buffer:
            return []
        raw = self._buffer
        self._buffer = ""
        segment = SentenceSegment(raw, self._sequence, True)
        self._sequence += 1
        self._reconstructed.append(raw)
        return [segment]

    @property
    def reconstructed_text(self) -> str:
        return "".join(self._reconstructed) + self._buffer


def segment_deltas(
    deltas: Iterable[str | GenerationDelta],
    *,
    cancellation: TurnCancellation | None = None,
    max_chars: int = 320,
) -> Iterator[SentenceSegment]:
    """Adapt streaming or one-shot provider text into sentence segments."""
    assembler = SentenceStreamAssembler(max_chars=max_chars)
    for item in deltas:
        if cancellation is not None and cancellation.cancelled:
            return
        text = item.text if isinstance(item, GenerationDelta) else str(item or "")
        for segment in assembler.feed(text):
            yield segment
    if cancellation is None or not cancellation.cancelled:
        yield from assembler.finish()
