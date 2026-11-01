"""Media playback, YouTube, queue, favorites, and floating-player behavior."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt, QUrl, QUrlQuery
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QVBoxLayout,
)

from . import media_library
from .integration_ui import DownloadWorker
from .media_commands import parse_media_command
from .settings import load_settings


class MediaControllerMixin:
    """Give the main window media behavior without owning its visual construction."""

    def _handle_media_command(self, prompt: str) -> bool:
        """Apply the UI-independent media command parsed from speech or text."""
        command = parse_media_command(prompt)
        if command is None:
            return False
        if command.action == "pause":
            self.pause_media()
            return True
        if command.action == "next":
            self.play_next_media()
            return True
        if command.action == "fullscreen":
            if self.tabs.currentIndex() == 2 or self.mini_player_dialog:
                self.toggle_media_fullscreen()
            return True
        if command.action == "minimize":
            if self.mini_player_dialog:
                self.mini_player_dialog.showMinimized()
            else:
                self._set_compact_media(True)
            return True
        if command.action == "window":
            self.open_mini_player()
            return True
        self.search_youtube_in_hud(command.query)
        if command.window:
            QTimer.singleShot(1400, self.open_mini_player)
        if command.fullscreen:
            QTimer.singleShot(1800, self.toggle_media_fullscreen)
        if command.minimized:
            QTimer.singleShot(1400, lambda: self._set_compact_media(True))
        return True

    def search_youtube_in_hud(self, query: str):
        """Loads official YouTube search results inside the media page of the HUD."""
        self.media_source.setText(query)
        self.tabs.setCurrentIndex(2)
        if query.strip():
            search_url = QUrl("https://www.youtube.com/results")
            params = QUrlQuery(); params.addQueryItem("search_query", query.strip())
            search_url.setQuery(params)
        else:
            search_url = QUrl("https://www.youtube.com/")
        self._play_youtube(search_url, query.strip())

    def _set_dashboard_metric(self, key: str, value: str):
        metric = getattr(self, "dashboard_metrics", {}).get(key)
        if metric is not None:
            metric.setText(f"{key.upper()} · {value}")

    def _youtube_load_started(self):
        self._set_dashboard_metric("mídia", "Conectando…")
        self.status.setText("Abrindo YouTube dentro da HUD…")

    def _youtube_load_finished(self, success: bool):
        if not success:
            self._set_dashboard_metric("mídia", "Falha ao abrir")
            self.status.setText("Não foi possível carregar o YouTube")
            return
        self._set_dashboard_metric("mídia", "YouTube pronto")
        self.status.setText("YouTube carregado na HUD")
        if not self.youtube_status_timer.isActive():
            self.youtube_status_timer.start()

    def _poll_youtube_status(self):
        if not self.youtube_view.isVisible() and not self.mini_player_dialog:
            return
        script = (
            "(() => { const v=document.querySelector('video'); "
            "if (!v) return 'ready'; if (!v.paused && !v.ended) return 'playing'; "
            "if (v.ended) return 'ended'; return 'paused'; })()")
        self.youtube_view.page().runJavaScript(script, self._youtube_playback_status)

    def _youtube_playback_status(self, state):
        states = {
            "playing": ("Reproduzindo", "YouTube reproduzindo"),
            "paused": ("Pausada", "Vídeo pausado no YouTube"),
            "ended": ("Concluída", "Reprodução encerrada"),
            "ready": ("YouTube pronto", "Escolha um resultado na página"),
        }
        result = states.get(state)
        if result:
            self._set_dashboard_metric("mídia", result[0])
            self.media_title.setText(result[1])
        if state == "ended" and media_library.queue():
            current_url = self.youtube_view.url().toString()
            if current_url != self._last_auto_advanced_url:
                self._last_auto_advanced_url = current_url
                QTimer.singleShot(0, self.play_next_media)

    def _local_media_status_changed(self, state):
        if state == QMediaPlayer.MediaStatus.EndOfMedia and media_library.queue():
            QTimer.singleShot(0, self.play_next_media)

    def _refresh_media_library(self):
        selected = self.favorite_picker.currentText() if self.favorite_picker.count() else ""
        self.favorite_picker.clear()
        self.favorite_picker.addItem("Favoritos…", "")
        for value in media_library.favorites():
            self.favorite_picker.addItem(value, value)
        index = self.favorite_picker.findText(selected)
        if index >= 0:
            self.favorite_picker.setCurrentIndex(index)
        self.next_media_button.setText(f"Próxima · {len(media_library.queue())}")

    def _current_media_reference(self) -> str:
        url = self.youtube_view.url().toString()
        if "youtube.com/watch" in url or "youtu.be/" in url:
            return url
        return self.media_source.text().strip()

    def save_media_favorite(self):
        try:
            media_library.add_favorite(self._current_media_reference())
            self._refresh_media_library()
            self.status.setText("Mídia salva nos favoritos")
        except ValueError as exc:
            QMessageBox.information(self, "Favoritos", str(exc))

    def play_selected_favorite(self):
        value = self.favorite_picker.currentData()
        if value:
            self.media_source.setText(value)
            self.play_media()

    def add_media_queue(self):
        try:
            media_library.enqueue(self._current_media_reference())
            self._refresh_media_library()
            self.status.setText("Adicionado à fila de mídia")
        except ValueError as exc:
            QMessageBox.information(self, "Fila", str(exc))

    def play_next_media(self):
        value = media_library.dequeue()
        self._refresh_media_library()
        if value is None:
            self.status.setText("A fila de mídia está vazia")
            return
        self.media_source.setText(value)
        self.play_media()

    def _local_media_state_changed(self, state):
        states = {
            QMediaPlayer.PlaybackState.PlayingState: ("Reproduzindo", "Reproduzindo mídia local"),
            QMediaPlayer.PlaybackState.PausedState: ("Pausada", "Mídia pausada"),
            QMediaPlayer.PlaybackState.StoppedState: ("Parada", "Player parado"),
        }
        value, title = states.get(state, ("Parada", "Player parado"))
        self._set_dashboard_metric("mídia", value)
        if self.media_view.currentWidget() is not self.youtube_view:
            self.media_title.setText(title)

    def open_mini_player(self):
        """Moves the active YouTube page into a small floating window without restarting it."""
        if self.mini_player_dialog:
            self.mini_player_dialog.showNormal()
            self.mini_player_dialog.raise_()
            self.mini_player_dialog.activateWindow()
            return
        current_url = self.youtube_view.url().toString()
        if not current_url or current_url == "about:blank":
            query = self.media_source.text().strip()
            self.search_youtube_in_hud(query)
            QTimer.singleShot(1400, self.open_mini_player)
            return
        dialog = QDialog(self, Qt.WindowType.Window)
        dialog.setWindowTitle("JARVIS · Player YouTube")
        dialog.setMinimumSize(640, 380)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.media_view.removeWidget(self.youtube_view)
        self.youtube_view.setParent(dialog)
        box = QVBoxLayout(dialog); box.setContentsMargins(10, 10, 10, 10); box.setSpacing(8)
        controls = QHBoxLayout()
        label = QLabel("JARVIS · PLAYER FLUTUANTE"); label.setObjectName("dashboardKicker")
        controls.addWidget(label); controls.addStretch(1)
        minimize = QPushButton("Minimizar"); minimize.clicked.connect(dialog.showMinimized)
        controls.addWidget(minimize)
        fullscreen = QPushButton("Tela cheia")
        fullscreen.clicked.connect(lambda: self._toggle_window_fullscreen(dialog))
        controls.addWidget(fullscreen)
        back = QPushButton("Voltar ao HUD"); back.clicked.connect(dialog.close)
        controls.addWidget(back)
        box.addLayout(controls); box.addWidget(self.youtube_view, 1)
        self.mini_player_dialog = dialog
        dialog.finished.connect(self._restore_mini_player)
        dialog.show()

    def _restore_mini_player(self, *_args):
        """Returns the live YouTube widget to the embedded HUD player when its window closes."""
        dialog = self.mini_player_dialog
        if dialog is None:
            return
        self.youtube_view.setParent(self.media_view)
        self.media_view.addWidget(self.youtube_view)
        self.media_view.setCurrentWidget(self.youtube_view)
        self.mini_player_dialog = None
        dialog.hide()
        self._set_dashboard_metric("mídia", "YouTube pronto")

    def _toggle_window_fullscreen(self, window):
        if window.isFullScreen():
            window.showNormal()
        else:
            window.showFullScreen()

    def toggle_media_fullscreen(self):
        """Toggles full screen on the floating player or the complete media HUD."""
        target = self.mini_player_dialog or self
        self._toggle_window_fullscreen(target)

    def _youtube_fullscreen_requested(self, request):
        request.accept()
        if request.toggleOn():
            self.toggle_media_fullscreen()
        else:
            target = self.mini_player_dialog or self
            if target.isFullScreen():
                target.showNormal()

    def open_media_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir mídia", "",
            "Áudio e vídeo (*.mp3 *.wav *.m4a *.mp4 *.mkv);;Todos os arquivos (*)")
        if path:
            self.media_source.setText(path)
            self._play_source(QUrl.fromLocalFile(path), Path(path).name)

    def play_media(self):
        source = self.media_source.text().strip()
        if not source:
            self.open_media_file(); return
        if Path(source).is_file():
            self._play_source(QUrl.fromLocalFile(str(Path(source).resolve())), Path(source).name)
            return

        candidate = source
        if not candidate.lower().startswith(("http://", "https://")) and any(
                host in candidate.lower() for host in ("youtube.com/", "youtu.be/")):
            candidate = "https://" + candidate
        candidate_url = QUrl.fromUserInput(candidate)
        youtube_hosts = {"youtube.com", "www.youtube.com", "music.youtube.com", "youtu.be"}
        if candidate_url.host().lower() in youtube_hosts:
            self._play_youtube(candidate_url)
            return
        if not candidate.lower().startswith(("http://", "https://")):
            # Search on the official site in the embedded view; playback stays on YouTube.
            self.search_youtube_in_hud(source)
            return
        self._play_source(candidate_url, candidate_url.fileName() or candidate_url.host() or source)

    def _play_youtube(self, url: QUrl, query: str = ""):
        self.player.stop()
        if self.mini_player_dialog:
            self._restore_mini_player()
        self.media_view.setCurrentWidget(self.youtube_view)
        self.youtube_view.setUrl(url)
        title = f"Buscando no YouTube · {query}" if query else "YouTube · navegue e reproduza na HUD"
        self.media_title.setText(title)
        self._set_dashboard_metric("mídia", "Buscando…")
        self.status.setText("Pesquisa do YouTube aberta dentro da HUD")
        if not self.youtube_status_timer.isActive():
            self.youtube_status_timer.start()
        # Keep Qt WebEngine's video surface free of opacity effects.

    def _play_source(self, url: QUrl, title: str):
        video_suffixes = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}
        is_video = Path(url.path()).suffix.lower() in video_suffixes
        self.youtube_view.setUrl(QUrl("about:blank"))
        self.media_view.setCurrentWidget(self.video_widget if is_video else self.media_idle)
        self.player.setSource(url)
        self.player.play()
        self.media_title.setText(title or "Reproduzindo")

    def pause_media(self):
        if self.media_view.currentWidget() is self.youtube_view:
            self.youtube_view.page().runJavaScript(
                "(() => { const player = document.querySelector('video'); "
                "if (player) player.paused ? player.play() : player.pause(); })()")
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def download_media(self):
        source = self.media_source.text().strip()
        if not source:
            QMessageBox.information(self, "Baixar áudio", "Informe uma URL de mídia primeiro.")
            return
        consent = QMessageBox.question(self, "Confirmar download",
            "Baixar somente mídia que você tem autorização para salvar?")
        if consent != QMessageBox.StandardButton.Yes:
            return
        folder = QFileDialog.getExistingDirectory(self, "Escolher pasta de destino")
        if not folder: return
        self.status.setText("Baixando mídia…")
        self.download_worker = DownloadWorker(source, folder)
        self._track_worker(self.download_worker)
        self.download_worker.completed.connect(self._download_done)
        self.download_worker.failed.connect(self.error)
        self.download_worker.start()

    def _download_done(self, path: str):
        self.status.setText("Download concluído")
        QMessageBox.information(self, "Download concluído", f"Arquivo salvo em:\n{path}")

    def _set_compact_media(self, compact: bool):
        self.media_controls.setVisible(not compact)
        if load_settings().get("reduce_motion", False):
            self.media_view.setMaximumHeight(180 if compact else 16_777_215)
            self.compact_button.setText("Mostrar controles" if compact else "Recolher controles")
            return
        if getattr(self, "media_view_animation", None):
            self.media_view_animation.stop()
        current_height = max(180, self.media_view.height())
        target_height = 180 if compact else max(current_height, int(self.height() * 0.58))
        self.media_view.setMaximumHeight(current_height)
        self.media_view_animation = QPropertyAnimation(self.media_view, b"maximumHeight", self)
        self.media_view_animation.setDuration(280)
        self.media_view_animation.setStartValue(current_height)
        self.media_view_animation.setEndValue(target_height)
        self.media_view_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.media_view_animation.finished.connect(
            lambda compact=compact: self.media_view.setMaximumHeight(180 if compact else 16_777_215))
        self.media_view_animation.start()
        self.compact_button.setText("Mostrar controles" if compact else "Recolher controles")
        self._set_dashboard_metric("mídia", "Compacta" if compact else "Expandida")

    def toggle_compact_media(self):
        self._set_compact_media(self.media_controls.isVisible())

    def _animate_widget(self, widget):
        """Adds a short ease-out fade when the active media surface changes."""
        if load_settings().get("reduce_motion", False):
            return
        if getattr(self, "media_fade_animation", None):
            self.media_fade_animation.stop()
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.68)
        widget.setGraphicsEffect(effect)
        self.media_fade_animation = QPropertyAnimation(effect, b"opacity", self)
        self.media_fade_animation.setDuration(280)
        self.media_fade_animation.setStartValue(0.68)
        self.media_fade_animation.setEndValue(1.0)
        self.media_fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.media_fade_animation.start()

