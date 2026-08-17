"""Native MaryV2 desktop window hosting the local web/VRM frontend."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from mary.desktop.bridge import MaryDesktopBridge
from mary.runtime.application import MaryApplication, create_application


class MaryDesktopWindow(QMainWindow):
    def __init__(
        self,
        application: MaryApplication,
        *,
        frontend_path: Path,
    ) -> None:
        super().__init__()
        self.application = application
        self.bridge = MaryDesktopBridge(application)

        self.setWindowTitle("MaryV2 — Mary Cosma")
        self.resize(1440, 900)
        self.setMinimumSize(1000, 680)

        self.web = QWebEngineView(self)
        self.setCentralWidget(self.web)

        settings = self.web.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            True,
        )

        self.channel = QWebChannel(self.web.page())
        self.channel.registerObject("maryBridge", self.bridge)
        self.web.page().setWebChannel(self.channel)

        self.bridge.errorOccurred.connect(self._show_error)
        self.web.setUrl(QUrl.fromLocalFile(str(frontend_path.resolve())))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            self.bridge.close()
        finally:
            event.accept()

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "MaryV2", message)


def _default_frontend_path(root: Path) -> Path:
    return root / "desktop" / "dist" / "index.html"


def run_desktop(application: MaryApplication | None = None) -> int:
    project_root = Path(__file__).resolve().parents[2]
    frontend_path = _default_frontend_path(project_root)

    if not frontend_path.exists():
        raise FileNotFoundError(
            "Desktop frontend has not been built yet. Run `cd desktop`, "
            "`npm install`, then `npm run build`."
        )

    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.setApplicationName("MaryV2")
    qt_app.setOrganizationName("Unbe")

    mary_app = application or create_application(name="mary-desktop")
    window = MaryDesktopWindow(mary_app, frontend_path=frontend_path)
    window.show()

    return int(qt_app.exec())
