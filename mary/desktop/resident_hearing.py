'''Controlled local resident hearing for MaryV2 Desktop.

Resident Hearing is OFF by default. When explicitly enabled, this module keeps
raw microphone PCM local, performs lightweight energy VAD, and emits a bounded
WAV utterance only after confirmed speech and trailing silence.
'''

from __future__ import annotations

import math
import os
import shutil
import sys
import tempfile
import wave
from array import array
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices


SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2


@dataclass(frozen=True)
class VadEvent:
    kind: str
    confidence: float = 0.0


class EnergyVadDetector:
    '''Dependency-free candidate/confirmation/end gate over PCM frame energy.'''

    def __init__(
        self,
        *,
        calibration_ms: int = 1800,
        confirm_ms: int = 180,
        end_silence_ms: int = 650,
        max_utterance_ms: int = 15000,
        start_multiplier: float = 3.2,
        min_start_rms: float = 350.0,
        min_end_rms: float = 250.0,
    ) -> None:
        self.calibration_frames = max(1, int(calibration_ms) // FRAME_MS)
        self.confirm_frames = max(1, int(confirm_ms) // FRAME_MS)
        self.end_silence_frames = max(1, int(end_silence_ms) // FRAME_MS)
        self.max_utterance_frames = max(1, int(max_utterance_ms) // FRAME_MS)
        self.start_multiplier = max(1.2, float(start_multiplier))
        self.min_start_rms = max(1.0, float(min_start_rms))
        self.min_end_rms = max(1.0, float(min_end_rms))

        self.calibrated = False
        self.noise_floor = 0.0
        self.start_threshold = self.min_start_rms
        self.end_threshold = self.min_end_rms
        self._calibration: list[float] = []
        self.state = 'idle'
        self.hot_frames = 0
        self.silent_frames = 0
        self.utterance_frames = 0

    def reset_detection(self, *, preserve_calibration: bool = True) -> None:
        if not preserve_calibration:
            self.calibrated = False
            self.noise_floor = 0.0
            self.start_threshold = self.min_start_rms
            self.end_threshold = self.min_end_rms
            self._calibration = []
        self.state = 'idle'
        self.hot_frames = 0
        self.silent_frames = 0
        self.utterance_frames = 0

    def _confidence(self, level: float) -> float:
        denom = max(self.start_threshold * 2.0, 1.0)
        return min(0.99, max(0.05, float(level) / denom))

    def observe(self, level: float) -> list[VadEvent]:
        level = max(0.0, float(level))
        events: list[VadEvent] = []

        if not self.calibrated:
            self._calibration.append(level)
            if len(self._calibration) >= self.calibration_frames:
                self.noise_floor = max(1.0, float(median(self._calibration)))
                self.start_threshold = max(
                    self.min_start_rms,
                    self.noise_floor * self.start_multiplier,
                )
                self.end_threshold = max(
                    self.min_end_rms,
                    self.start_threshold * 0.58,
                )
                self.calibrated = True
                events.append(VadEvent('calibrated'))
            return events

        if self.state == 'idle':
            if level < self.start_threshold * 0.70:
                self.noise_floor = self.noise_floor * 0.995 + level * 0.005
                adaptive = max(
                    self.min_start_rms,
                    self.noise_floor * self.start_multiplier,
                )
                self.start_threshold = max(
                    self.start_threshold * 0.999,
                    adaptive,
                )
                self.end_threshold = max(
                    self.min_end_rms,
                    self.start_threshold * 0.58,
                )

            if level >= self.start_threshold:
                self.state = 'candidate'
                self.hot_frames = 1
                self.silent_frames = 0
                self.utterance_frames = 1
                events.append(VadEvent('candidate', self._confidence(level)))
            return events

        self.utterance_frames += 1

        if self.state == 'candidate':
            if level >= self.start_threshold:
                self.hot_frames += 1
            else:
                self.hot_frames = max(0, self.hot_frames - 1)

            if self.hot_frames >= self.confirm_frames:
                self.state = 'confirmed'
                self.silent_frames = 0
                events.append(
                    VadEvent('confirmed', max(0.50, self._confidence(level)))
                )
            elif self.utterance_frames > self.confirm_frames * 3:
                self.reset_detection(preserve_calibration=True)
                events.append(VadEvent('false_start'))
            return events

        if level <= self.end_threshold:
            self.silent_frames += 1
        else:
            self.silent_frames = 0

        if (
            self.silent_frames >= self.end_silence_frames
            or self.utterance_frames >= self.max_utterance_frames
        ):
            self.reset_detection(preserve_calibration=True)
            events.append(VadEvent('end'))

        return events


def rms_pcm16(data: bytes) -> float:
    if not data:
        return 0.0
    usable = data[: len(data) - (len(data) % 2)]
    samples = array('h')
    samples.frombytes(usable)
    if sys.byteorder != 'little':
        samples.byteswap()
    if not samples:
        return 0.0
    total = sum(int(value) * int(value) for value in samples)
    return math.sqrt(total / len(samples))


def _resolve_input_device():
    inputs = list(QMediaDevices.audioInputs())
    if not inputs:
        raise RuntimeError('No microphone input device is available.')

    preferred = os.getenv('MARY_AUDIO_INPUT_DEVICE', '').strip()
    if preferred:
        folded = preferred.casefold()
        exact = [
            item
            for item in inputs
            if str(item.description() or '').strip().casefold() == folded
        ]
        partial = [
            item
            for item in inputs
            if folded in str(item.description() or '').strip().casefold()
        ]
        if exact:
            return exact[0]
        if len(partial) == 1:
            return partial[0]

        available = ', '.join(
            str(item.description() or '').strip() or 'unnamed'
            for item in inputs
        )
        reason = 'ambiguous' if partial else 'not found'
        raise RuntimeError(
            f'MARY_AUDIO_INPUT_DEVICE is {reason}: {preferred}. '
            f'Available inputs: {available}'
        )

    device = QMediaDevices.defaultAudioInput()
    if str(device.description() or '').strip():
        return device
    return inputs[0]


class DesktopResidentHearing(QObject):
    '''Explicitly armed local continuous capture; never enabled at startup.'''

    stateChanged = Signal(str)
    voiceActivity = Signal(bool, bool, float)
    recordingReady = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._enabled = False
        self._state = 'off'
        self._device = None
        self._source: QAudioSource | None = None
        self._io = None
        self._byte_buffer = bytearray()
        self._preroll: deque[bytes] = deque(maxlen=10)
        self._utterance: list[bytes] = []
        self._segment_dir: Path | None = None

        self.detector = EnergyVadDetector(
            start_multiplier=float(
                os.getenv('MARY_RESIDENT_VAD_START_MULTIPLIER', '3.2')
            ),
            min_start_rms=float(
                os.getenv('MARY_RESIDENT_VAD_MIN_START_RMS', '350')
            ),
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def active(self) -> bool:
        return self._source is not None and self._io is not None

    def status(self) -> dict[str, object]:
        return {
            'enabled': self._enabled,
            'active': self.active,
            'state': self._state,
            'input_device': (
                str(self._device.description() or '').strip()
                if self._device is not None
                else ''
            ),
            'sample_rate': SAMPLE_RATE,
            'channels': CHANNELS,
            'frame_ms': FRAME_MS,
            'calibrated': self.detector.calibrated,
            'noise_rms': round(self.detector.noise_floor, 2),
            'start_rms': round(self.detector.start_threshold, 2),
            'end_rms': round(self.detector.end_threshold, 2),
            'privacy': 'raw audio local only',
        }

    def _emit_state(self, state: str) -> None:
        self._state = str(state)
        self.stateChanged.emit(self._state)

    @Slot()
    def enable(self) -> None:
        if self._enabled:
            self.resume()
            return

        try:
            self._device = _resolve_input_device()
            audio_format = QAudioFormat()
            audio_format.setSampleRate(SAMPLE_RATE)
            audio_format.setChannelCount(CHANNELS)
            audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

            if not self._device.isFormatSupported(audio_format):
                raise RuntimeError(
                    f'{self._device.description()} does not support '
                    f'{SAMPLE_RATE} Hz mono Int16 resident capture.'
                )

            self._source = QAudioSource(self._device, audio_format, self)
            self._enabled = True
            self.detector.reset_detection(preserve_calibration=False)
            self._begin_capture()
        except Exception as exc:
            self._enabled = False
            self._source = None
            self._io = None
            self._emit_state('off')
            self.errorOccurred.emit(f'{type(exc).__name__}: {exc}')

    @Slot()
    def disable(self) -> None:
        self._enabled = False
        if self._source is not None:
            self._source.stop()
        self._io = None
        self._byte_buffer.clear()
        self._preroll.clear()
        self._utterance = []
        self.detector.reset_detection(preserve_calibration=False)
        self._cleanup_segment()
        self._emit_state('off')

    def pause(self, state: str = 'paused') -> None:
        if not self._enabled:
            return
        if self._source is not None:
            self._source.stop()
        self._io = None
        self._byte_buffer.clear()
        self._preroll.clear()
        self._utterance = []
        self.detector.reset_detection(preserve_calibration=True)
        self._emit_state(state or 'paused')

    def resume(self) -> None:
        if not self._enabled or self.active or self._source is None:
            return
        self._cleanup_segment()
        self.detector.reset_detection(preserve_calibration=True)
        try:
            self._begin_capture()
        except Exception as exc:
            self.errorOccurred.emit(f'{type(exc).__name__}: {exc}')

    def _begin_capture(self) -> None:
        if self._source is None:
            raise RuntimeError('Resident microphone source is unavailable.')
        self._io = self._source.start()
        if self._io is None:
            raise RuntimeError('Resident microphone capture failed to start.')
        self._io.readyRead.connect(self._on_ready_read)
        self._emit_state(
            'listening' if self.detector.calibrated else 'calibrating'
        )

    @Slot()
    def _on_ready_read(self) -> None:
        if not self.active:
            return
        self._byte_buffer.extend(bytes(self._io.readAll()))
        while len(self._byte_buffer) >= FRAME_BYTES and self.active:
            frame = bytes(self._byte_buffer[:FRAME_BYTES])
            del self._byte_buffer[:FRAME_BYTES]
            self._process_frame(frame)

    def _process_frame(self, frame: bytes) -> None:
        level = rms_pcm16(frame)
        before = self.detector.state

        if self.detector.calibrated and before == 'idle':
            self._preroll.append(frame)
        elif before in {'candidate', 'confirmed'}:
            self._utterance.append(frame)

        events = self.detector.observe(level)
        for event in events:
            if event.kind == 'calibrated':
                self._emit_state('listening')
            elif event.kind == 'candidate':
                self._utterance = list(self._preroll)
                self.voiceActivity.emit(True, False, event.confidence)
            elif event.kind == 'confirmed':
                self._emit_state('speech')
                self.voiceActivity.emit(True, True, event.confidence)
            elif event.kind == 'false_start':
                self._utterance = []
                self._preroll.clear()
                self.voiceActivity.emit(False, False, 0.0)
                self._emit_state('listening')
            elif event.kind == 'end':
                self.voiceActivity.emit(False, False, 0.0)
                self._finish_segment()

    def _finish_segment(self) -> None:
        pcm = b''.join(self._utterance)
        self.pause('paused')
        if not pcm:
            self.errorOccurred.emit('Resident hearing produced an empty segment.')
            return

        self._cleanup_segment()
        self._segment_dir = Path(tempfile.mkdtemp(prefix='maryv2_resident_'))
        path = self._segment_dir / 'resident_utterance.wav'
        with wave.open(str(path), 'wb') as output:
            output.setnchannels(CHANNELS)
            output.setsampwidth(2)
            output.setframerate(SAMPLE_RATE)
            output.writeframes(pcm)
        self.recordingReady.emit(str(path))

    def _cleanup_segment(self) -> None:
        directory = self._segment_dir
        self._segment_dir = None
        if directory and directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
