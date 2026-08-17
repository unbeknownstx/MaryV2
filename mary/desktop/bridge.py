"""Qt WebChannel bridge for MaryV2 Desktop Alpha.

This module keeps the GUI as a presentation layer over the canonical
``MaryApplication``.  It never creates a second Mary object, and it does not
reimplement cognition or persistence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

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


class _WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class _ConversationWorker(QRunnable):
    def __init__(self, application: MaryApplication, text: str) -> None:
        super().__init__()
        self.application = application
        self.text = text
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = self.application.run(self.text)
            if not result.success:
                raise RuntimeError(result.error or "Mary's pipeline did not complete.")

            response_text = str(result.output or "")
            mary = self.application.mary

            # The core already owns provider-independent avatar state.  The
            # desktop only asks that state to reflect this response.
            # sync_emotion() updates the controller and returns an AvatarState.
            # Do not pass that state back as ``expression``: present() expects
            # an AvatarExpression there.  Keep the synchronized expression on
            # the controller and only add the response text/presentation data.
            mary.avatar.sync_emotion()
            avatar_state = mary.avatar.controller.present(
                text=response_text,
                speaking=False,
                metadata={"surface": "desktop"},
            )

            payload = DesktopTurnPayload(
                text=response_text,
                avatar=avatar_state.to_dict(),
                runtime={
                    "turn_id": result.turn_id,
                    "elapsed": result.elapsed,
                    "success": result.success,
                },
            )
            self.signals.finished.emit(payload)
        except Exception as exc:  # Qt worker boundary: report instead of crash UI.
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")


class MaryDesktopBridge(QObject):
    """Object exposed to JavaScript through QWebChannel."""

    messageReady = Signal(str)
    avatarStateChanged = Signal(str)
    busyChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self, application: MaryApplication) -> None:
        super().__init__()
        self.application = application
        self._pool = QThreadPool.globalInstance()
        self._busy = False
        # Keep a strong Python reference to the active QRunnable until one of
        # its completion signals reaches the bridge. Without this, bindings
        # can collect the Python wrapper while the C++ thread-pool task is
        # still running, leaving the web UI stuck in its busy state.
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
        worker = _ConversationWorker(self.application, value)
        worker.signals.finished.connect(self._on_turn_finished)
        worker.signals.failed.connect(self._on_turn_failed)
        self._active_worker = worker
        self._pool.start(worker)

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
        self._pool.waitForDone()
        self.application.close()

    def _set_busy(self, value: bool) -> None:
        self._busy = bool(value)
        self.busyChanged.emit(self._busy)

    def _on_turn_finished(self, payload: DesktopTurnPayload) -> None:
        self._active_worker = None
        self._set_busy(False)
        payload_dict = payload.to_dict()
        self.messageReady.emit(_json(payload_dict))
        self.avatarStateChanged.emit(_json(payload.avatar))

    def _on_turn_failed(self, error: str) -> None:
        self._active_worker = None
        self._set_busy(False)
        self.errorOccurred.emit(error)
