"""Native MaryV2 desktop window hosting the local web/VRM frontend."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from mary.desktop.bridge import MaryDesktopBridge
from mary.runtime.application import MaryApplication, create_application


class MaryWebEnginePage(QWebEnginePage):
    """WebEngine page that preserves useful frontend console diagnostics."""

    def javaScriptConsoleMessage(  # noqa: N802 - Qt virtual method
        self,
        level,
        message: str,
        line_number: int,
        source_id: str,
    ) -> None:
        source = source_id or "<inline>"
        print(
            f"[MaryDesktop][JS] {source}:{line_number} {message}",
            flush=True,
        )



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
        self.resize(1600, 960)
        # The web shell now has responsive breakpoints down to this size. Keep
        # the minimum above tablet-like layouts while allowing 1366x768 and
        # smaller laptop work areas to remain usable.
        self.setMinimumSize(960, 620)
        self._settings = QSettings("Unbe", "MaryV2")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self._was_maximized_before_fullscreen = True

        self.web = QWebEngineView(self)
        self.web.setPage(MaryWebEnginePage(self.web))
        self.setCentralWidget(self.web)

        settings = self.web.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            True,
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture,
            False,
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            True,
        )

        self.channel = QWebChannel(self.web.page())
        self.channel.registerObject("maryBridge", self.bridge)
        self.web.page().setWebChannel(self.channel)

        self.bridge.errorOccurred.connect(self._show_error)
        self.bridge.minimizeRequested.connect(self.showMinimized)
        self.bridge.maximizeRequested.connect(self._toggle_maximized)
        self.bridge.closeRequested.connect(self.close)
        self.bridge.windowMoveRequested.connect(self._start_system_move)
        self.web.setUrl(QUrl.fromLocalFile(str(frontend_path.resolve())))

        # Game-style display controls. F11 or Alt+Enter enters true fullscreen;
        # Escape returns to the previous maximized/windowed state.
        QShortcut(QKeySequence("F11"), self, activated=self._toggle_fullscreen)
        QShortcut(QKeySequence("Alt+Return"), self, activated=self._toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self, activated=self._leave_fullscreen)

    def show_for_startup(self) -> None:
        mode = os.getenv("MARY_DESKTOP_START_MODE", "maximized").strip().lower()
        if mode == "fullscreen":
            self.showFullScreen()
            return
        if mode == "windowed":
            screen = self.screen() or QApplication.primaryScreen()
            restored = False
            remember = os.getenv("MARY_DESKTOP_REMEMBER_WINDOW", "1").strip().lower() not in {
                "0", "false", "no", "off"
            }
            if remember:
                geometry = self._settings.value("desktop/window_geometry")
                if geometry is not None:
                    try:
                        restored = bool(self.restoreGeometry(geometry))
                    except Exception:
                        restored = False
            if screen is not None:
                available = screen.availableGeometry()
                if restored and not available.contains(self.frameGeometry().center()):
                    restored = False
                if not restored:
                    width = min(1600, max(self.minimumWidth(), int(available.width() * 0.90)))
                    height = min(960, max(self.minimumHeight(), int(available.height() * 0.90)))
                    self.resize(width, height)
                    self.move(
                        available.x() + max(0, (available.width() - width) // 2),
                        available.y() + max(0, (available.height() - height) // 2),
                    )
            self.show()
            return
        self.showMaximized()

    def _toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self._leave_fullscreen()
            return
        self._was_maximized_before_fullscreen = self.isMaximized()
        self.showFullScreen()

    def _leave_fullscreen(self) -> None:
        if not self.isFullScreen():
            return
        if self._was_maximized_before_fullscreen:
            self.showMaximized()
        else:
            self.showNormal()

    def _start_system_move(self) -> None:
        handle = self.windowHandle()
        if handle is not None:
            try:
                handle.startSystemMove()
            except Exception:
                pass

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            if not self.isFullScreen() and not self.isMaximized():
                try:
                    self._settings.setValue("desktop/window_geometry", self.saveGeometry())
                    self._settings.sync()
                except Exception:
                    pass
            self.bridge.close()
        finally:
            event.accept()

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "MaryV2", message)


def _default_frontend_path(root: Path) -> Path:
    return root / "desktop" / "dist" / "index.html"


def run_desktop(application: MaryApplication | None = None) -> int:
    mary_app = application or create_application(name="mary-desktop")
    project_root = mary_app.mary.config.paths.root
    frontend_path = _default_frontend_path(project_root)

    if not frontend_path.exists():
        raise FileNotFoundError(
            "Desktop frontend has not been built yet. Run `cd desktop`, "
            "`npm install`, then `npm run build`."
        )

    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.setApplicationName("MaryV2")
    qt_app.setOrganizationName("Unbe")

    window = MaryDesktopWindow(mary_app, frontend_path=frontend_path)
    window.show_for_startup()

    return int(qt_app.exec())
