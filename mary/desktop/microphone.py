"""Native microphone capture for MaryV2 Desktop push-to-talk."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtMultimedia import (
    QAudioInput,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaRecorder,
)


class DesktopMicrophoneRecorder(QObject):
    """Record a short user utterance with Qt Multimedia."""

    stateChanged = Signal(str)
    recordingReady = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._session = QMediaCaptureSession()
        self._audio_input = QAudioInput()
        self._recorder = QMediaRecorder()
        self._session.setAudioInput(self._audio_input)
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

    @Slot()
    def start(self) -> None:
        if self.is_recording:
            return
        if not QMediaDevices.audioInputs():
            self.errorOccurred.emit("No microphone input device is available.")
            return

        self.cleanup()
        self._temp_dir = Path(tempfile.mkdtemp(prefix="maryv2_mic_"))
        self._requested_path = self._temp_dir / "unbe_input.m4a"
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
