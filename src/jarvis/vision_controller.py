"""On-demand screen analysis and continuous Gemini Live vision lifecycle."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QMessageBox

from . import memory
from .settings import get_secret, load_settings, save_settings
from .vision_worker import LiveVisionWorker


class VisionControllerMixin:
    """Keep live screen observation independent from the main interface layout."""

    def analyze_screen(self):
        prompt = self.input.text().strip() or "Descreva o que aparece na minha tela e destaque elementos importantes."
        self.input.clear()
        self._start(prompt, "screen")

    def toggle_live_vision(self, enabled: bool):
        if enabled:
            if not get_secret("gemini"):
                QMessageBox.warning(self, "Gemini necessário",
                                    "A visão de tela usa Gemini. Cadastre a chave em Configurações.")
                self.live_vision_button.setChecked(False)
                return
            self._start_screen_preview()
            self.live_vision_worker = LiveVisionWorker(self.screen_frame_store.jpeg)
            self.live_vision_worker.observation.connect(self._live_observation)
            self.live_vision_worker.failed.connect(self.error)
            self.live_vision_worker.finished.connect(self._live_vision_finished)
            self.live_vision_worker.start()
            self.live_vision_button.setText("Parar visão contínua")
            save_settings({**load_settings(), "live_vision_enabled": True})
            self.status.setText("Visão ao vivo · prévia local fluida; Gemini recebe até 1 imagem/s")
            self._set_dashboard_metric("tela", "Ao vivo")
        else:
            save_settings({**load_settings(), "live_vision_enabled": False})
            self._stop_screen_preview()
            self._stop_live_vision()
        self._refresh_privacy_indicators()

    def _live_observation(self, text: str):
        self._append("assistant", "[Observação da tela] " + text)
        memory.add("assistant", "[Observação da tela] " + text)

    def _live_vision_finished(self):
        self.live_vision_button.setChecked(False)
        self.live_vision_button.setText("Iniciar visão contínua")
        self.live_vision_button.setEnabled(True)
        self.live_vision_worker = None
        self._stop_screen_preview()
        self.screen_preview_label.setPixmap(QPixmap())
        self.screen_preview_label.setText("A prévia local aparece aqui quando a visão estiver ativa")
        self.status.setText("Visão contínua parada")
        self._set_dashboard_metric("tela", "Desligada")
        self._refresh_privacy_indicators()
        if self._close_when_vision_stops:
            QTimer.singleShot(0, self.close)

    def _stop_live_vision(self):
        worker = self.live_vision_worker
        if worker and worker.isRunning():
            self.live_vision_button.setEnabled(False)
            self.live_vision_button.setText("Parando após a solicitação atual…")
            worker.stop()

