"""Bounded sentence-level speech scheduling for incremental Mary responses."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar, Generic

from mary.realtime.streaming import SentenceSegment, TurnCancellation

T = TypeVar("T")


@dataclass(frozen=True)
class SynthesizedSegment(Generic[T]):
    sequence: int
    text: str
    payload: T


class SentenceSpeechScheduler(Generic[T]):
    """Synthesize ahead in parallel while always playing segments in order.

    The scheduler owns no audio device and imports no TTS provider. Callers inject
    synthesis and playback functions, keeping cloud/local engines replaceable.
    """

    def __init__(self, *, max_workers: int = 2, max_pending: int = 3) -> None:
        self.max_workers = max(1, min(4, int(max_workers)))
        self.max_pending = max(1, min(8, int(max_pending)))

    def run(
        self,
        segments: Iterable[SentenceSegment],
        *,
        synthesize: Callable[[str], T],
        play: Callable[[T], None],
        cancellation: TurnCancellation | None = None,
    ) -> list[SynthesizedSegment[T]]:
        completed: list[SynthesizedSegment[T]] = []
        pending: dict[int, tuple[SentenceSegment, Future[T]]] = {}
        next_play = 0

        def cancelled() -> bool:
            return bool(cancellation is not None and cancellation.cancelled)

        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="mary-tts") as pool:
            for segment in segments:
                if cancelled():
                    break
                pending[segment.sequence] = (segment, pool.submit(synthesize, segment.text))
                while len(pending) >= self.max_pending and next_play in pending:
                    current, future = pending.pop(next_play)
                    payload = future.result()
                    if cancelled():
                        break
                    play(payload)
                    completed.append(SynthesizedSegment(current.sequence, current.text, payload))
                    next_play += 1
                if cancelled():
                    break

            while not cancelled() and pending:
                if next_play not in pending:
                    next_play = min(pending)
                current, future = pending.pop(next_play)
                payload = future.result()
                if cancelled():
                    break
                play(payload)
                completed.append(SynthesizedSegment(current.sequence, current.text, payload))
                next_play += 1

            if cancelled():
                for _, future in pending.values():
                    future.cancel()
        return completed
