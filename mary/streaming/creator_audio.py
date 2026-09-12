"""Optional local creator microphone capture for Mary stream cohost.

This is transport-side capture only. Raw PCM stays in the stream-host process
until one bounded utterance is emitted; the caller may dispatch that WAV to an
authorized STT capability node. Nothing here owns Mary state or memory.
"""
from __future__ import annotations

import io
import os
from threading import RLock
from typing import Callable
import wave

from mary.desktop.resident_hearing import (
    CHANNELS,
    FRAME_BYTES,
    FRAME_MS,
    SAMPLE_RATE,
    EnergyVadDetector,
    rms_pcm16,
)


class StreamCreatorMicrophone:
    """VAD-gated raw microphone capture using optional sounddevice."""

    def __init__(self, on_utterance: Callable[[bytes], None]) -> None:
        self.on_utterance = on_utterance
        self._stream = None
        self._lock = RLock()
        self._byte_buffer = bytearray()
        self._preroll: list[bytes] = []
        self._utterance: list[bytes] = []
        self._enabled = False
        self.detector = EnergyVadDetector(
            start_multiplier=float(os.getenv("MARY_STREAM_VAD_START_MULTIPLIER", "3.2")),
            min_start_rms=float(os.getenv("MARY_STREAM_VAD_MIN_START_RMS", "350")),
            end_silence_ms=int(os.getenv("MARY_STREAM_VAD_END_SILENCE_MS", "650")),
            max_utterance_ms=int(os.getenv("MARY_STREAM_MAX_UTTERANCE_MS", "15000")),
        )
        self._max_preroll_frames = max(1, 300 // FRAME_MS)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("Install requirements-streaming-audio.txt to enable creator microphone capture.") from exc
        with self._lock:
            if self._stream is not None:
                return
            device = os.getenv("MARY_AUDIO_INPUT_DEVICE", "").strip() or None
            self.detector.reset_detection(preserve_calibration=False)
            self._byte_buffer.clear()
            self._preroll.clear()
            self._utterance.clear()
            self._stream = sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=SAMPLE_RATE * FRAME_MS // 1000,
                device=device,
                callback=self._callback,
            )
            self._stream.start()
            self._enabled = True

    def stop(self) -> None:
        with self._lock:
            stream = self._stream
            self._stream = None
            self._enabled = False
            self._byte_buffer.clear()
            self._preroll.clear()
            self._utterance.clear()
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        del frames, time_info, status
        raw = bytes(indata)
        if not raw:
            return
        with self._lock:
            self._byte_buffer.extend(raw)
            while len(self._byte_buffer) >= FRAME_BYTES:
                frame = bytes(self._byte_buffer[:FRAME_BYTES])
                del self._byte_buffer[:FRAME_BYTES]
                self._process_frame(frame)

    def _process_frame(self, frame: bytes) -> None:
        before = self.detector.state
        if self.detector.calibrated and before == "idle":
            self._preroll.append(frame)
            if len(self._preroll) > self._max_preroll_frames:
                del self._preroll[:-self._max_preroll_frames]
        elif before in {"candidate", "confirmed"}:
            self._utterance.append(frame)

        events = self.detector.observe(rms_pcm16(frame))
        for event in events:
            if event.kind == "candidate":
                self._utterance = list(self._preroll)
            elif event.kind == "false_start":
                self._utterance.clear()
                self._preroll.clear()
            elif event.kind == "end":
                pcm = b"".join(self._utterance)
                self._utterance.clear()
                self._preroll.clear()
                if pcm:
                    self.on_utterance(self._wav_bytes(pcm))

    @staticmethod
    def _wav_bytes(pcm: bytes) -> bytes:
        output = io.BytesIO()
        with wave.open(output, "wb") as handle:
            handle.setnchannels(CHANNELS)
            handle.setsampwidth(2)
            handle.setframerate(SAMPLE_RATE)
            handle.writeframes(pcm)
        return output.getvalue()
