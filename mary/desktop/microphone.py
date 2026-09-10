"""Native microphone capture for MaryV2 Desktop push-to-talk."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtMultimedia import (
    QAudioInput,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaFormat,
    QMediaRecorder,
)


class DesktopMicrophoneRecorder(QObject):
    """Record a short creator utterance as Whisper-compatible PCM WAV."""

    stateChanged = Signal(str)
    recordingReady = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._session = QMediaCaptureSession()
        self._audio_input: QAudioInput | None = None
        self._recorder = QMediaRecorder()
        self._session.setRecorder(self._recorder)

        self._temp_dir: Path | None = None
        self._requested_path: Path | None = None
        self._actual_path: Path | None = None
        self._stop_requested = False

        self._recorder.actualLocationChanged.connect(self._on_actual_location)
        self._recorder.recorderStateChanged.connect(self._on_state_changed)
        self._recorder.errorOccurred.connect(self._on_error)

    @property
    def is_recording(self) -> bool:
        return (
            self._recorder.recorderState()
            == QMediaRecorder.RecorderState.RecordingState
        )

    @property
    def input_device_name(self) -> str:
        if self._audio_input is not None:
            return str(self._audio_input.device().description() or "").strip()
        return str(QMediaDevices.defaultAudioInput().description() or "").strip()

    @Slot()
    def start(self) -> None:
        if self.is_recording:
            return

        inputs = list(QMediaDevices.audioInputs())
        if not inputs:
            self.errorOccurred.emit("No microphone input device is available.")
            return

        preferred = os.getenv("MARY_AUDIO_INPUT_DEVICE", "").strip()
        device = QMediaDevices.defaultAudioInput()

        if preferred:
            folded = preferred.casefold()
            exact = [
                item
                for item in inputs
                if str(item.description() or "").strip().casefold() == folded
            ]
            partial = [
                item
                for item in inputs
                if folded in str(item.description() or "").strip().casefold()
            ]
            if exact:
                device = exact[0]
            elif len(partial) == 1:
                device = partial[0]
            else:
                available = ", ".join(
                    str(item.description() or "").strip() or "unnamed"
                    for item in inputs
                )
                reason = "ambiguous" if partial else "not found"
                self.errorOccurred.emit(
                    f"MARY_AUDIO_INPUT_DEVICE is {reason}: {preferred}. "
                    f"Available inputs: {available}"
                )
                return
        elif not str(device.description() or "").strip():
            device = inputs[0]

        self.cleanup()
        self._audio_input = QAudioInput(device)
        self._audio_input.setVolume(1.0)
        self._session.setAudioInput(self._audio_input)

        media_format = QMediaFormat()
        media_format.setFileFormat(QMediaFormat.FileFormat.Wave)
        media_format.setAudioCodec(QMediaFormat.AudioCodec.Wave)
        self._recorder.setMediaFormat(media_format)
        self._recorder.setAudioSampleRate(16000)
        self._recorder.setAudioChannelCount(1)

        self._temp_dir = Path(tempfile.mkdtemp(prefix="maryv2_mic_"))
        self._requested_path = self._temp_dir / "unbe_input.wav"
        self._actual_path = None
        self._stop_requested = False

        self._recorder.setOutputLocation(
            QUrl.fromLocalFile(str(self._requested_path))
        )
        self._recorder.record()

    @Slot()
    def stop(self) -> None:
        if not self.is_recording:
            return
        self._stop_requested = True
        self.stateChanged.emit("transcribing")
        self._recorder.stop()

    def cleanup(self) -> None:
        directory = self._temp_dir
        self._temp_dir = None
        self._requested_path = None
        self._actual_path = None
        self._stop_requested = False
        if directory and directory.exists():
            shutil.rmtree(directory, ignore_errors=True)

    @Slot(QUrl)
    def _on_actual_location(self, location: QUrl) -> None:
        local = location.toLocalFile()
        if local:
            self._actual_path = Path(local)

    @Slot(QMediaRecorder.RecorderState)
    def _on_state_changed(self, state: QMediaRecorder.RecorderState) -> None:
        if state == QMediaRecorder.RecorderState.RecordingState:
            self.stateChanged.emit("listening")
            return

        if (
            state == QMediaRecorder.RecorderState.StoppedState
            and self._stop_requested
        ):
            self._stop_requested = False
            path = self._actual_path or self._requested_path
            if path is None or not path.exists() or path.stat().st_size <= 0:
                self.errorOccurred.emit("Microphone recording did not produce audio.")
                self.cleanup()
                return
            self.recordingReady.emit(str(path))

    @Slot(QMediaRecorder.Error, str)
    def _on_error(self, _error: QMediaRecorder.Error, message: str) -> None:
        text = str(message or self._recorder.errorString() or "Microphone error")
        self.errorOccurred.emit(text)
        self.cleanup()
