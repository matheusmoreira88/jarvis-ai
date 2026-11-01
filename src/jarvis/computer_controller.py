"""Voice/text routing and guarded local computer actions."""
from __future__ import annotations

import re
import sys

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QThread, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from . import memory
from .computer import open_known_app
from .memory_ui import MemoryMapDialog
from .settings import get_secret, load_settings, save_settings


class ComputerControllerMixin:
    """Centralize local actions so confirmations and limits remain easy to audit."""

    def _dispatch_computer_command(self, prompt: str) -> bool:
        """Executa apenas ações locais explícitas; nunca interpreta saída do modelo como ação."""
        normalized = prompt.strip()
        lowered = normalized.casefold()
        lowered = re.sub(r"^\s*(?:oi\s+)?jarvis\s*[,;:.-]?\s*", "", lowered).strip()
        if lowered in {"minimiza", "minimize", "minimize o jarvis", "minimiza o jarvis"}:
            self.minimize_with_animation()
            return True
        if lowered in {"tela cheia", "jarvis em tela cheia"}:
            self.showFullScreen()
            return True
        if lowered in {"sair da tela cheia", "sair do modo tela cheia", "janela normal"}:
            self.showNormal()
            return True
        if lowered in {"desligar visão", "desative a visão", "pare de ver a tela"}:
            self.live_vision_button.setChecked(False); self.toggle_live_vision(False)
            return True
        if lowered in {"ligar visão", "ative a visão", "veja minha tela"}:
            self.live_vision_button.setChecked(True); self.toggle_live_vision(True)
            return True
        if lowered in {"desligar microfone", "desative o microfone", "pare de ouvir"}:
            self.voice_activation_button.setChecked(False)
            return True
        if lowered in {"modo pânico", "modo panico", "pare tudo", "interromper tudo",
                       "interrompa tudo", "desligue tudo"}:
            self.panic_stop()
            return True
        if self._handle_media_command(normalized):
            return True
        open_intent = bool(re.match(
            r"^(?:abra|abre|abrir|mostre|mostra|mostrar|quero ver|vá para|vai para)\b", lowered))
        if open_intent and any(word in lowered for word in ("configuração", "configurações", "configuracao", "configuracoes", "ajustes")):
            self.tabs.setCurrentIndex(3)
            self.status.setText("Configurações abertas")
            return True
        if open_intent and any(word in lowered for word in ("conversa", "conversas", "chat", "histórico", "historico")):
            self.tabs.setCurrentIndex(1)
            self.status.setText("Conversa aberta")
            return True
        if open_intent and any(word in lowered for word in ("mídia", "midia", "música", "musica", "player")):
            self.tabs.setCurrentIndex(2)
            self.status.setText("Mídia aberta")
            return True
        if open_intent and any(word in lowered for word in ("memória", "memoria", "mapa de conhecimento", "cérebro", "cerebro")):
            self.open_memory_map()
            self.status.setText("Mapa de conhecimento aberto")
            return True
        if open_intent and any(word in lowered for word in ("painel", "núcleo", "nucleo", "jarvis")):
            self.tabs.setCurrentIndex(0)
            self.status.setText("Núcleo aberto")
            return True
        for routine in load_settings().get("routines", []):
            if not isinstance(routine, dict):
                continue
            if lowered == str(routine.get("phrase", "")).strip().casefold():
                self._run_routine(routine)
                return True
        for action in load_settings().get("quick_actions", []):
            if not isinstance(action, dict):
                continue
            if lowered == str(action.get("phrase", "")).strip().lower():
                return self._dispatch_computer_command(str(action.get("command", "")))
        from .extensions import load_extensions
        extension_actions, _extension_errors = load_extensions()
        for action in extension_actions:
            if lowered == str(action.get("phrase", "")).strip().casefold():
                return self._dispatch_computer_command(str(action.get("command", "")))

        if lowered.startswith("abrir aplicativo:"):
            requested = normalized[len("abrir aplicativo:"):].strip()
            if not requested:
                QMessageBox.information(self, "Abrir aplicativo", "Diga o nome do aplicativo.")
                return True
            self._launch_installed_by_name(requested, prompt)
            return True

        if lowered.startswith("abrir exe:"):
            path = normalized[len("abrir exe:"):].strip()
            if not path:
                QMessageBox.information(self, "Abrir aplicativo", "Informe o caminho completo do .exe.")
                return True
            try:
                from .computer import open_user_selected_executable
                self._record_private_control_action(
                    prompt, open_user_selected_executable(path))
            except Exception as exc:
                self.error(str(exc))
            return True

        if lowered.startswith("agir:"):
            request = normalized[len("agir:"):].strip()
            if not request:
                QMessageBox.information(
                    self, "Ação na tela", "Descreva o que você quer que o JARVIS faça.")
                return True
            if not get_secret("gemini"):
                QMessageBox.warning(
                    self, "Gemini necessário",
                    "Cadastre a chave Gemini em Configurações para planejar uma ação na tela.")
                return True
            self._start(request, "plan")
            return True

        if lowered == "clicar":
            from .computer import click_pointer
            answer = QMessageBox.question(
                self, "Confirmar clique",
                "Clicar uma vez na posição atual do ponteiro no aplicativo ativo?")
            if answer == QMessageBox.StandardButton.Yes:
                self._record_control_action(prompt, "Clique enviado na posição atual do ponteiro.")
                self._yield_focus_to_active_app()
                QTimer.singleShot(500, lambda: self._run_pointer_action(click_pointer))
            return True

        if lowered in {"rolar: cima", "rolar: baixo"}:
            from .computer import scroll_page
            direction = lowered.split(":", 1)[1].strip()
            answer = QMessageBox.question(
                self, "Confirmar rolagem",
                f"Rolar a página para {direction} no aplicativo ativo?")
            if answer == QMessageBox.StandardButton.Yes:
                self._record_control_action(prompt, f"Página rolada para {direction}.")
                self._yield_focus_to_active_app()
                QTimer.singleShot(500, lambda: self._run_pointer_action(
                    lambda: scroll_page(direction)))
            return True

        if lowered.startswith("abrir "):
            target = normalized[6:].strip().lower()
            if target in {"bloco de notas", "calculadora", "explorador de arquivos"}:
                try:
                    result = open_known_app(target)
                    self._record_control_action(prompt, result)
                except Exception as exc:
                    self.error(str(exc))
                return True
            self._launch_installed_by_name(normalized[6:].strip(), prompt)
            return True

        if lowered.startswith("digitar:"):
            text = normalized.split(":", 1)[1].strip()
            if not text:
                QMessageBox.information(self, "Digitar texto", "Use ‘digitar: seu texto’.")
                return True
            answer = QMessageBox.question(
                self, "Confirmar digitação",
                "O texto temporariamente substituirá a área de transferência; o HUD será ocultado "
                "e ele será colado no aplicativo que estiver ativo. "
                "Deixe o cursor no campo de destino antes de confirmar.\n\n" + text[:1200])
            if answer == QMessageBox.StandardButton.Yes:
                QApplication.clipboard().setText(text)
                self._append("private_action", prompt)
                memory.add("private_action", prompt)
                self._append("assistant", "Texto colado no aplicativo ativo.")
                memory.add("assistant", "Texto colado no aplicativo ativo.")
                self._yield_focus_to_active_app()
                QTimer.singleShot(500, self._paste_into_active_app)
            return True

        if lowered.startswith("pressionar:"):
            key = normalized.split(":", 1)[1].strip().lower().replace(" ", "")
            from .computer import SAFE_KEYS, SAFE_SHORTCUTS
            if key not in SAFE_KEYS | SAFE_SHORTCUTS:
                self.error("Tecla fora da lista permitida; consulte a seção de controle local no README.")
                return True
            answer = QMessageBox.question(
                self, "Confirmar tecla",
                f"Pressionar ‘{key}’ no aplicativo ativo depois de ocultar o HUD?")
            if answer == QMessageBox.StandardButton.Yes:
                self._record_control_action(prompt, f"Tecla {key} enviada ao aplicativo ativo.")
                self._yield_focus_to_active_app()
                QTimer.singleShot(500, lambda: self._press_in_active_app(key))
            return True
        return False

    def open_memory_map(self):
        dialog = self.memory_map_dialog
        if dialog is not None and dialog.isVisible():
            dialog.showNormal()
            dialog.raise_()
            dialog.activateWindow()
            return
        dialog = MemoryMapDialog(self)
        self.memory_map_dialog = dialog
        dialog.destroyed.connect(lambda *_: setattr(self, "memory_map_dialog", None))
        dialog.show()

    def minimize_with_animation(self):
        """Suaviza a saída antes de entregar a janela à barra de tarefas."""
        self.minimize_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self.minimize_animation.setDuration(220)
        self.minimize_animation.setStartValue(1.0)
        self.minimize_animation.setEndValue(0.35)
        self.minimize_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        def finish():
            self.showMinimized()
            self.setWindowOpacity(1.0)
        self.minimize_animation.finished.connect(finish)
        self.minimize_animation.start()

    def panic_stop(self):
        """Immediately disable every ambient microphone and screen observer."""
        settings = load_settings()
        settings.update({
            "hands_free_enabled": False,
            "voice_activation_enabled": False,
            "live_vision_enabled": False,
            "clap_enabled": False,
        })
        save_settings(settings)
        if getattr(self, "voice_activation_button", None):
            self.voice_activation_button.setChecked(False)
        if getattr(self, "live_vision_button", None):
            self.live_vision_button.blockSignals(True)
            self.live_vision_button.setChecked(False)
            self.live_vision_button.blockSignals(False)
            self.toggle_live_vision(False)
        if getattr(self, "clap_button", None):
            self.clap_button.blockSignals(True)
            self.clap_button.setChecked(False)
            self.clap_button.blockSignals(False)
        self._stop_clap_worker()
        self._stop_screen_preview()
        worker = getattr(self, "worker", None)
        if worker and worker.isRunning() and getattr(worker, "mode", None) == "voice":
            worker.stop_recording()
        self.core_orb.set_state("ready")
        self.voice_state.setText("Modo pânico · sensores desligados")
        self.answer_preview.setText("Microfone, visão e detecção de palmas foram desligados.")
        self.status.setText("MODO PÂNICO · sensores desligados")
        self._refresh_privacy_indicators()
        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "JARVIS · modo pânico", "Microfone, visão e palmas foram desligados.",
                QSystemTrayIcon.MessageIcon.Warning, 4000)

    def _run_pointer_action(self, action):
        """Mostra no HUD erros do mouse, em vez de deixar a exceção escapar do timer."""
        try:
            result = action()
            self.status.setText(result)
        except Exception as exc:
            self.error(f"Não foi possível controlar o mouse: {exc}")

    def _record_control_action(self, prompt: str, result: str):
        self._append("user", prompt); memory.add("user", prompt)
        self._append("assistant", result); memory.add("assistant", result)

    def _record_private_control_action(self, prompt: str, result: str):
        """Mantém caminhos locais no histórico, mas fora do contexto enviado às APIs."""
        self._append("private_action", prompt); memory.add("private_action", prompt)
        self._append("assistant", result); memory.add("assistant", result)

    def _track_worker(self, worker: QThread):
        """Keep a thread alive until Qt tells us its background task has finished."""
        self.background_workers.add(worker)
        worker.finished.connect(lambda worker=worker: self.background_workers.discard(worker))

    def _yield_focus_to_active_app(self):
        if self.tray_icon and self.tray_icon.isVisible():
            self.hide()
        else:
            self.showMinimized()

    def _paste_into_active_app(self):
        try:
            import pyautogui
            chord = ("command", "v") if sys.platform == "darwin" else ("ctrl", "v")
            pyautogui.hotkey(*chord)
        except Exception as exc:
            self._report_control_failure("colar texto", exc)

    def _press_in_active_app(self, key: str):
        try:
            from .computer import press_key
            press_key(key)
        except Exception as exc:
            self._report_control_failure("pressionar tecla", exc)

    def _report_control_failure(self, action: str, error: Exception):
        message = f"Falha ao {action}: {error}"
        if self.tray_icon:
            self.tray_icon.showMessage("JARVIS", message)
        self.show_from_tray()
        self.error(message)

