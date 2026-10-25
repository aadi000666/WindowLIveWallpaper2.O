"""Video wallpaper widget and desktop-aware playback controls."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl, QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QWidget

from . import win_api


class WallpaperPlayer(QWidget):
    """Borderless video surface hosted behind desktop icons on Windows."""

    fullscreenChanged = Signal(bool)
    playbackError = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LiveWall Wallpaper")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)

        self.video = QVideoWidget(self)
        self.video.setStyleSheet("background: black;")
        self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        self.video.setGeometry(self.rect())

        self.audio = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.setLoops(QMediaPlayer.Loops.Infinite)
        self.player.errorOccurred.connect(self._on_error)
        self.player.mediaStatusChanged.connect(self._on_media_status)

        self._video_path: Path | None = None
        self._media_error_reported = False
        self._paused_for_fullscreen = False
        self._user_paused = False
        self._was_playing_before_fullscreen = False

        self._fullscreen_timer = QTimer(self)
        self._fullscreen_timer.setInterval(1000)
        self._fullscreen_timer.timeout.connect(self._check_fullscreen)
        self._fullscreen_timer.start()

    @property
    def video_path(self) -> Path | None:
        return self._video_path

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self.video.setGeometry(self.rect())

    def load(self, path: str | Path) -> None:
        """Load and start a local video file."""
        file_path = Path(path).expanduser().resolve()
        if not file_path.is_file():
            raise FileNotFoundError(f"Video file does not exist: {file_path}")
        self._video_path = file_path
        self._media_error_reported = False
        self._user_paused = False
        self.player.setSource(QUrl.fromLocalFile(str(file_path)))
        self.player.play()

    def play(self) -> None:
        self._user_paused = False
        if self._paused_for_fullscreen:
            self._was_playing_before_fullscreen = True
            return
        self.player.play()

    def pause(self) -> None:
        self._user_paused = True
        self.player.pause()

    def toggle_playback(self) -> None:
        if self._user_paused or self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.play()
        else:
            self.pause()

    def set_muted(self, muted: bool) -> None:
        self.audio.setMuted(muted)

    def is_muted(self) -> bool:
        return self.audio.isMuted()

    def set_volume(self, volume: int) -> None:
        self.audio.setVolume(max(0.0, min(1.0, volume / 100.0)))

    def volume(self) -> int:
        return round(self.audio.volume() * 100)

    def set_playback_rate(self, rate: float) -> None:
        self.player.setPlaybackRate(max(0.25, min(2.0, rate)))

    def playback_rate(self) -> float:
        return self.player.playbackRate()

    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def attach_to_desktop(self) -> None:
        """Expose the native window and place it in the desktop WorkerW layer."""
        if sys.platform != "win32":
            raise OSError("LiveWall desktop wallpaper is supported on Windows only.")
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            raise RuntimeError("No display was found.")
        geometry = screen.geometry()
        self.setGeometry(0, 0, geometry.width(), geometry.height())
        self.show()
        self.winId()
        win_api.attach_to_desktop(int(self.winId()))
        self.video.setGeometry(self.rect())

    def _check_fullscreen(self) -> None:
        if sys.platform != "win32":
            return
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.geometry()
        is_fullscreen = win_api.foreground_window_is_fullscreen(
            (
                geometry.x(),
                geometry.y(),
                geometry.x() + geometry.width(),
                geometry.y() + geometry.height(),
            ),
            int(self.winId()) if self.testAttribute(Qt.WidgetAttribute.WA_WState_Created) else 0,
        )
        if is_fullscreen == self._paused_for_fullscreen:
            return

        self._paused_for_fullscreen = is_fullscreen
        if is_fullscreen:
            self._was_playing_before_fullscreen = self.is_playing()
            if self._was_playing_before_fullscreen:
                self.player.pause()
        elif self._was_playing_before_fullscreen and not self._user_paused:
            self.player.play()
        self.fullscreenChanged.emit(is_fullscreen)

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        # QMediaPlayer.Loops is available in current Qt 6 versions; this also
        # handles backends that report EndOfMedia without restarting themselves.
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self._video_path:
            if not self._paused_for_fullscreen and not self._user_paused:
                self.player.setPosition(0)
                self.player.play()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._report_media_error(
                "Qt could not decode this video. Try MP4 with H.264 video and AAC audio."
            )

    def _on_error(self, error, message: str) -> None:
        details = message or "The media backend could not open this video."
        details += (
            "\nTry an MP4 encoded as H.264 video with AAC audio. "
            "AV1 and some HEVC/MKV codecs may need extra Windows codecs."
        )
        self._report_media_error(details)

    def _report_media_error(self, message: str) -> None:
        if self._media_error_reported:
            return
        self._media_error_reported = True
        self.playbackError.emit(message)
