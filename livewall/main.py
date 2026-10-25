"""LiveWall settings window, tray menu, and application startup."""

from __future__ import annotations

import argparse
import sys
import winreg
from pathlib import Path

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .player import WallpaperPlayer

APP_NAME = "LiveWall"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
SUPPORTED_VIDEO_FILTER = "Video files (*.mp4 *.mkv *.avi *.mov *.webm);;All files (*)"
STYLESHEET = """
QWidget { background: #17191f; color: #e7e9ee; font-size: 10pt; }
QMainWindow { background: #17191f; }
QLabel#title { font-size: 20pt; font-weight: 600; color: #ffffff; }
QLabel#muted { color: #a1a7b3; }
QPushButton, QComboBox {
    background: #252934; border: 1px solid #383e4b; border-radius: 7px;
    padding: 8px 10px; min-height: 18px;
}
QPushButton:hover, QComboBox:hover { background: #303644; }
QPushButton#accent { background: #6c63ff; border: 0; font-weight: 600; }
QPushButton#accent:hover { background: #8179ff; }
QSlider::groove:horizontal { height: 5px; background: #383e4b; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #8179ff; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #ffffff; width: 14px; margin: -5px 0; border-radius: 7px;
}
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QComboBox QAbstractItemView { background: #252934; selection-background-color: #6c63ff; }
"""


def _startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    return f'"{sys.executable}" "{Path(sys.argv[0]).resolve()}" --minimized'


def startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except FileNotFoundError:
        return False


def set_startup_enabled(enabled: bool) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _startup_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def tray_icon() -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#6c63ff"))
    painter.drawRoundedRect(1, 1, 30, 30, 8, 8)
    painter.setBrush(QColor("#ffffff"))
    painter.drawPolygon(
        QPolygon([
            QPoint(12, 8),
            QPoint(12, 24),
            QPoint(24, 16),
        ])
    )
    painter.end()
    return QIcon(pixmap)


class ControlPanel(QMainWindow):
    def __init__(self, player: WallpaperPlayer) -> None:
        super().__init__()
        self.player = player
        self.settings = QSettings("LiveWall", "LiveWall")
        self.setWindowTitle(f"{APP_NAME} Settings")
        self.setMinimumWidth(440)
        self.setWindowIcon(QIcon())
        self.setStyleSheet(STYLESHEET)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(16)

        title = QLabel("LiveWall")
        title.setObjectName("title")
        subtitle = QLabel("Bring your desktop to life.")
        subtitle.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addWidget(QLabel("Wallpaper video"))
        file_row = QHBoxLayout()
        self.file_label = QLabel("No video selected")
        self.file_label.setObjectName("muted")
        self.file_label.setMinimumWidth(0)
        self.file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.choose_button = QPushButton("Choose video...")
        self.choose_button.setObjectName("accent")
        self.choose_button.clicked.connect(self.choose_video)
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(self.choose_button)
        layout.addLayout(file_row)

        controls_row = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_playback)
        self.mute_button = QPushButton("Mute")
        self.mute_button.clicked.connect(self.toggle_mute)
        controls_row.addWidget(self.play_button)
        controls_row.addWidget(self.mute_button)
        layout.addLayout(controls_row)

        layout.addWidget(QLabel("Volume"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.player.volume())
        self.volume_slider.valueChanged.connect(self._set_volume)
        layout.addWidget(self.volume_slider)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Playback speed"))
        self.speed_combo = QComboBox()
        for speed in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0):
            self.speed_combo.addItem(f"{speed:g}x", speed)
        self.speed_combo.setCurrentIndex(3)
        self.speed_combo.currentIndexChanged.connect(self._set_speed)
        saved_speed = float(self.settings.value("playback/speed", 1.0))
        speed_index = self.speed_combo.findData(saved_speed)
        if speed_index >= 0:
            self.speed_combo.setCurrentIndex(speed_index)
        speed_row.addWidget(self.speed_combo)
        layout.addLayout(speed_row)

        self.startup_checkbox = QCheckBox("Launch LiveWall when I sign in")
        self.startup_checkbox.setChecked(startup_enabled())
        self.startup_checkbox.toggled.connect(self._set_startup)
        layout.addWidget(self.startup_checkbox)

        self.status_label = QLabel("Fullscreen apps automatically pause playback.")
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.setCentralWidget(central)

        self.player.fullscreenChanged.connect(self._fullscreen_status)
        self.player.playbackError.connect(self._show_playback_error)
        self.player.player.playbackStateChanged.connect(self._refresh_play_button)
        self._refresh_mute_button()

    def choose_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a wallpaper video", "", SUPPORTED_VIDEO_FILTER
        )
        if not path:
            return
        try:
            self.player.load(path)
        except (FileNotFoundError, OSError, RuntimeError) as error:
            QMessageBox.critical(self, "Could not load video", str(error))
            return
        self.settings.setValue("wallpaper/path", str(Path(path).resolve()))
        self.file_label.setText(Path(path).name)
        self.file_label.setToolTip(path)
        self._refresh_play_button()

    def toggle_playback(self) -> None:
        self.player.toggle_playback()
        self._refresh_play_button()

    def toggle_mute(self) -> None:
        muted = not self.player.is_muted()
        self.player.set_muted(muted)
        self.settings.setValue("audio/muted", muted)
        self._refresh_mute_button()

    def _set_volume(self, volume: int) -> None:
        self.player.set_volume(volume)
        self.settings.setValue("audio/volume", volume)

    def _set_speed(self, index: int) -> None:
        speed = self.speed_combo.itemData(index)
        if speed is not None:
            self.player.set_playback_rate(float(speed))
            self.settings.setValue("playback/speed", float(speed))

    def _set_startup(self, enabled: bool) -> None:
        try:
            set_startup_enabled(enabled)
        except OSError as error:
            QMessageBox.warning(self, "Startup setting failed", str(error))
            self.startup_checkbox.blockSignals(True)
            self.startup_checkbox.setChecked(not enabled)
            self.startup_checkbox.blockSignals(False)

    def _refresh_play_button(self) -> None:
        self.play_button.setText("Pause" if self.player.is_playing() else "Play")

    def _refresh_mute_button(self) -> None:
        self.mute_button.setText("Unmute" if self.player.is_muted() else "Mute")

    def _fullscreen_status(self, active: bool) -> None:
        self.status_label.setText(
            "Paused while a fullscreen app is active."
            if active
            else "Fullscreen apps automatically pause playback."
        )
        self._refresh_play_button()

    def _show_playback_error(self, message: str) -> None:
        self.status_label.setText(f"Playback error: {message}")


class LiveWallApplication:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.settings = QSettings("LiveWall", "LiveWall")
        self.player = WallpaperPlayer()
        self.player.set_volume(int(self.settings.value("audio/volume", 50)))
        self.player.set_muted(
            self.settings.value("audio/muted", True, type=bool)
        )
        self.player.set_playback_rate(
            float(self.settings.value("playback/speed", 1.0))
        )
        self.panel = ControlPanel(self.player)
        self.tray = QSystemTrayIcon(tray_icon(), self.app)
        self._create_tray_menu()
        self.tray.show()
        self.tray.activated.connect(self._tray_activated)
        self.player.playbackError.connect(self._tray_error)

    def _create_tray_menu(self) -> None:
        from PySide6.QtWidgets import QMenu

        self.tray_menu = QMenu()
        tray_menu = self.tray_menu
        self.play_action = QAction("Play", tray_menu)
        self.play_action.triggered.connect(self._toggle_playback)
        self.mute_action = QAction("Mute", tray_menu)
        self.mute_action.triggered.connect(self._toggle_mute)
        choose_action = QAction("Select video...", tray_menu)
        choose_action.triggered.connect(self.panel.choose_video)
        show_action = QAction("Open LiveWall", tray_menu)
        show_action.triggered.connect(self.show_panel)
        self.startup_action = QAction("Launch on Windows startup", tray_menu)
        self.startup_action.setCheckable(True)
        self.startup_action.setChecked(startup_enabled())
        self.startup_action.toggled.connect(self._set_startup_from_tray)
        exit_action = QAction("Exit", tray_menu)
        exit_action.triggered.connect(self.app.quit)
        tray_menu.addAction(self.play_action)
        tray_menu.addAction(self.mute_action)
        tray_menu.addSeparator()
        tray_menu.addAction(choose_action)
        tray_menu.addAction(show_action)
        tray_menu.addAction(self.startup_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)
        self.tray.setContextMenu(tray_menu)
        self.player.player.playbackStateChanged.connect(self._sync_tray_actions)
        self.panel.startup_checkbox.toggled.connect(self._sync_startup_action)
        self._sync_tray_actions()

    def _toggle_playback(self) -> None:
        self.player.toggle_playback()
        self._sync_tray_actions()

    def _toggle_mute(self) -> None:
        muted = not self.player.is_muted()
        self.player.set_muted(muted)
        self.settings.setValue("audio/muted", muted)
        self.panel._refresh_mute_button()
        self._sync_tray_actions()

    def _sync_startup_action(self, enabled: bool) -> None:
        self.startup_action.blockSignals(True)
        self.startup_action.setChecked(enabled)
        self.startup_action.blockSignals(False)

    def _set_startup_from_tray(self, enabled: bool) -> None:
        try:
            set_startup_enabled(enabled)
            self.panel.startup_checkbox.setChecked(enabled)
        except OSError as error:
            self.tray.showMessage(APP_NAME, f"Could not update startup setting: {error}")
            self.startup_action.blockSignals(True)
            self.startup_action.setChecked(not enabled)
            self.startup_action.blockSignals(False)

    def _sync_tray_actions(self) -> None:
        self.play_action.setText("Pause" if self.player.is_playing() else "Play")
        self.mute_action.setText("Unmute" if self.player.is_muted() else "Mute")

    def show_panel(self) -> None:
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_panel()

    def _tray_error(self, message: str) -> None:
        self.tray.showMessage(APP_NAME, message, QSystemTrayIcon.MessageIcon.Warning)

    def start(self, video_path: str | None, minimized: bool) -> int:
        if sys.platform != "win32":
            QMessageBox.critical(
                self.panel,
                APP_NAME,
                "LiveWall's desktop wallpaper integration is available on Windows only.",
            )
            return 1
        try:
            self.player.attach_to_desktop()
        except (OSError, RuntimeError) as error:
            QMessageBox.critical(self.panel, "Desktop integration failed", str(error))
            return 1

        selected_video = video_path or self.settings.value("wallpaper/path", "")
        if selected_video:
            try:
                self.player.load(selected_video)
                self.panel.file_label.setText(Path(selected_video).name)
                self.panel.file_label.setToolTip(selected_video)
                self.settings.setValue(
                    "wallpaper/path", str(Path(selected_video).resolve())
                )
            except (FileNotFoundError, OSError, RuntimeError) as error:
                if isinstance(error, FileNotFoundError):
                    self.settings.remove("wallpaper/path")
                self.tray.showMessage(
                    APP_NAME,
                    f"Could not restore wallpaper: {error}",
                    QSystemTrayIcon.MessageIcon.Warning,
                )
        if minimized:
            self.tray.showMessage(APP_NAME, "LiveWall is running in the system tray.")
        else:
            self.show_panel()
        return self.app.exec()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Video wallpapers for Windows.")
    parser.add_argument("video", nargs="?", help="Optional video file to use as wallpaper.")
    parser.add_argument("--minimized", action="store_true", help="Start in the system tray.")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, APP_NAME, "Windows reports that the system tray is unavailable.")
        return 1
    application = LiveWallApplication(app)
    return application.start(args.video, args.minimized)


if __name__ == "__main__":
    raise SystemExit(main())
