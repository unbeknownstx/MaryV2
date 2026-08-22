"""Native frameless window for the MaryV2 launcher frontend."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from mary.core.config import PathConfig
from mary.launcher.bridge import MaryLauncherBridge


class MaryLauncherWindow(QMainWindow):
    def __init__(self, *, frontend_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("Mary Launcher")
        self.resize(1180, 720)
        self.setMinimumSize(900, 560)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

        self.web = QWebEngineView(self)
        self.setCentralWidget(self.web)
        settings = self.web.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        self.bridge = MaryLauncherBridge()
        self.channel = QWebChannel(self.web.page())
        self.channel.registerObject("launcherBridge", self.bridge)
        self.web.page().setWebChannel(self.channel)

        self.bridge.errorOccurred.connect(self._show_error)
        self.bridge.closeRequested.connect(self.close)
        self.bridge.minimizeRequested.connect(self.showMinimized)
        self.bridge.windowMoveRequested.connect(self._start_system_move)

        self.web.setUrl(QUrl.fromLocalFile(str(frontend_path.resolve())))

    def _start_system_move(self) -> None:
        handle = self.windowHandle()
        if handle is not None:
            try:
                handle.startSystemMove()
            except Exception:
                pass

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Mary Launcher", str(message))


def run_launcher() -> int:
    root = PathConfig().root
    frontend_path = root / "desktop" / "dist" / "launcher.html"
    if not frontend_path.exists():
        raise FileNotFoundError(
            "Launcher frontend has not been built yet. Run `cd desktop`, `npm ci`, then `npm run build`."
        )

    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.setApplicationName("Mary Launcher")
    qt_app.setOrganizationName("Unbe")
    window = MaryLauncherWindow(frontend_path=frontend_path)
    window.show()
    return int(qt_app.exec())
