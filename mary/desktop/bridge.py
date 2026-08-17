"""Qt WebChannel bridge for MaryV2 Desktop Alpha.

The desktop is a presentation surface over the canonical ``MaryApplication``.
Conversation work runs on a dedicated QThread so Qt/WebEngine stays responsive,
and every turn is guaranteed to leave the busy state through an explicit
success or failure slot on the GUI thread.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from time import monotonic
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from mary.runtime.application import MaryApplication


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


@dataclass(frozen=True)
class DesktopTurnPayload:
    text: str
    avatar: dict[str, Any]
    runtime: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "avatar": dict(self.avatar),
            "runtime": dict(self.runtime),
        }


class _ConversationWorker(QObject):
    """Run one canonical Mary turn in a dedicated Qt worker thread."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, application: MaryApplication, text: str) -> None:
        super().__init__()
        self.application = application
        self.text = text

    @Slot()
    def run(self) -> None:
        started = monotonic()
        print("[MaryDesktop] turn started", flush=True)

        try:
            result = self.application.run(self.text)

            if not result.success:
                raise RuntimeError(
                    result.error or "Mary's pipeline did not complete."
                )

            response_text = str(result.output or "")
            mary = self.application.mary

            # Avatar presentation is best-effort. A visual-state defect must
            # never swallow an otherwise valid conversation response.
            avatar_error: str | None = None
            try:
                mary.avatar.sync_emotion()
                avatar_state = mary.avatar.controller.present(
                    text=response_text,
                    speaking=False,
                    metadata={"surface": "desktop"},
                )
                avatar_payload = avatar_state.to_dict()
            except Exception as exc:
                avatar_error = f"{type(exc).__name__}: {exc}"
                avatar_payload = mary.avatar.state.to_dict()

            payload = DesktopTurnPayload(
                text=response_text,
                avatar=avatar_payload,
                runtime={
                    "turn_id": result.turn_id,
                    "elapsed": result.elapsed,
                    "success": result.success,
                    "avatar_error": avatar_error,
                },
            )

            print(
                f"[MaryDesktop] turn completed in {monotonic() - started:.2f}s",
                flush=True,
            )
            self.finished.emit(payload)

        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            print(
                f"[MaryDesktop] turn failed in {monotonic() - started:.2f}s: {error}",
                flush=True,
            )
            self.failed.emit(error)


class MaryDesktopBridge(QObject):
    """Object exposed to JavaScript through QWebChannel."""

    messageReady = Signal(str)
    avatarStateChanged = Signal(str)
    busyChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self, application: MaryApplication) -> None:
        super().__init__()
        self.application = application
        self._busy = False
        self._active_thread: QThread | None = None
        self._active_worker: _ConversationWorker | None = None
        self.application.mary.avatar.ready()

    @Slot(str)
    def sendMessage(self, text: str) -> None:  # noqa: N802 - JS-facing API
        value = str(text or "").strip()
        if not value:
            return

        if self._busy:
            self.errorOccurred.emit("Mary is already processing a message.")
            return

        self._set_busy(True)

        thread = QThread(self)
        worker = _ConversationWorker(self.application, value)
        worker.moveToThread(thread)

        # Keep both wrappers alive for the full turn.
        self._active_thread = thread
        self._active_worker = worker

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_turn_finished)
        worker.failed.connect(self._on_turn_failed)
        thread.finished.connect(self._on_thread_finished)

        thread.start()

    @Slot(result=str)
    def getStatus(self) -> str:  # noqa: N802 - JS-facing API
        mary = self.application.mary
        status = mary.status()
        cognition = status.get("cognition", {})
        return _json(
            {
                "name": status.get("name", "Mary"),
                "provider": cognition.get("llm", "unknown"),
                "model": cognition.get("model", "unknown"),
                "busy": self._busy,
            }
        )

    @Slot(result=str)
    def getAvatarState(self) -> str:  # noqa: N802 - JS-facing API
        return _json(self.application.mary.avatar.state.to_dict())

    @Slot()
    def save(self) -> None:
        try:
            self.application.save()
        except Exception as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")

    def close(self) -> None:
        thread = self._active_thread
        if thread is not None and thread.isRunning():
            # Ask the pipeline to stop at the next stage boundary, then wait for
            # the in-flight synchronous provider call to return naturally.
            self.application.pipeline.cancel()
            thread.quit()
            thread.wait()
        self.application.close()

    def _set_busy(self, value: bool) -> None:
        self._busy = bool(value)
        self.busyChanged.emit(self._busy)

    @Slot(object)
    def _on_turn_finished(self, payload: object) -> None:
        """Receive a successful turn on the GUI thread and release the UI."""

        if not isinstance(payload, DesktopTurnPayload):
            self._finish_thread()
            self._set_busy(False)
            self.errorOccurred.emit(
                "Mary's desktop worker returned an invalid response payload."
            )
            return

        self._set_busy(False)
        payload_dict = payload.to_dict()
        self.messageReady.emit(_json(payload_dict))
        self.avatarStateChanged.emit(_json(payload.avatar))

        avatar_error = str(
            payload.runtime.get("avatar_error") or ""
        ).strip()
        if avatar_error:
            print(
                f"[MaryDesktop] avatar presentation warning: {avatar_error}",
                flush=True,
            )

        self._finish_thread()

    @Slot(str)
    def _on_turn_failed(self, error: str) -> None:
        """Receive a failed turn on the GUI thread and always release input."""

        self._set_busy(False)
        self.errorOccurred.emit(str(error))
        self._finish_thread()

    @Slot()
    def _on_thread_finished(self) -> None:
        """Guard against a worker thread ending without a terminal signal."""

        if self._busy:
            self._set_busy(False)
            self.errorOccurred.emit(
                "Mary's desktop worker stopped without returning a response."
            )

        self._active_worker = None
        self._active_thread = None

    def _finish_thread(self) -> None:
        thread = self._active_thread
        if thread is not None and thread.isRunning():
            thread.quit()
