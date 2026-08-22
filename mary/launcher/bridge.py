"""Qt WebChannel bridge for the MaryV2 game-style launcher."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from mary.core.config import PathConfig
from mary.launcher.update import UpdateService
from mary.runtime.release import APP_NAME, APP_VERSION, DESKTOP_PHASE, RELEASE_CHANNEL


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class MaryLauncherBridge(QObject):
    stateChanged = Signal(str)
    errorOccurred = Signal(str)
    appLaunched = Signal()
    closeRequested = Signal()
    minimizeRequested = Signal()
    windowMoveRequested = Signal()

    def __init__(self, *, update_service: UpdateService | None = None) -> None:
        super().__init__()
        self.update_service = update_service or UpdateService()

    @Slot(result=str)
    def getState(self) -> str:  # noqa: N802 - JS-facing API
        paths = PathConfig()
        return _json(
            {
                "app": APP_NAME,
                "version": APP_VERSION,
                "channel": RELEASE_CHANNEL,
                "desktop_phase": DESKTOP_PHASE,
                "data_root": str(paths.data),
                "update": self.update_service.status(),
            }
        )

    @Slot()
    def checkForUpdates(self) -> None:  # noqa: N802
        try:
            self.update_service.check()
            self.stateChanged.emit(self.getState())
        except Exception as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")
            self.stateChanged.emit(self.getState())

    @Slot()
    def stageUpdate(self) -> None:  # noqa: N802
        try:
            path = self.update_service.download_and_stage()
            payload = json.loads(self.getState())
            payload["update"]["staged_package"] = str(path)
            payload["update"]["staged"] = True
            payload["update"]["apply_policy"] = (
                "Verified package staged. Automatic replacement stays disabled "
                "until the versioned-install/rollback flow is validated on the personal PC."
            )
            self.stateChanged.emit(_json(payload))
        except Exception as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")

    @Slot()
    def play(self) -> None:
        try:
            command, cwd = self._desktop_command()
            subprocess.Popen(command, cwd=str(cwd) if cwd else None, close_fds=(sys.platform != "win32"))
            self.appLaunched.emit()
            self.closeRequested.emit()
        except Exception as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")

    @Slot()
    def closeWindow(self) -> None:  # noqa: N802
        self.closeRequested.emit()

    @Slot()
    def minimizeWindow(self) -> None:  # noqa: N802
        self.minimizeRequested.emit()

    @Slot()
    def startWindowMove(self) -> None:  # noqa: N802
        self.windowMoveRequested.emit()

    def _desktop_command(self) -> tuple[list[str], Path | None]:
        if getattr(sys, "frozen", False):
            here = Path(sys.executable).resolve().parent
            names = ["MaryV2.exe", "MaryV2"]
            candidates: list[Path] = []
            for name in names:
                candidates.extend(
                    [
                        here / name,
                        here.parent / "MaryV2" / name,
                        here.parent / name,
                    ]
                )
            for candidate in candidates:
                if candidate.exists() and candidate.is_file():
                    return [str(candidate)], candidate.parent
            raise FileNotFoundError(
                "MaryV2 executable was not found beside the launcher. Rebuild the desktop bundle."
            )

        root = PathConfig().root
        return [sys.executable, "-m", "scripts.run_desktop"], root
