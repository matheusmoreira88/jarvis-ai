"""Always-listening voice lifecycle and recognized-phrase dispatch."""
from __future__ import annotations

from . import memory
from .settings import get_secret, load_settings, save_settings
from .voice_worker import VoiceActivationWorker


class VoiceControllerMixin:
    """Keep microphone state independent from the main interface construction."""

    def toggle_voice_activation(self, enabled: bool):
        """Liga ou desliga a escuta automática; nenhum áudio em espera sai do computador."""
        save_settings({**load_settings(), "voice_activation_enabled": bool(enabled), "hands_free_enabled": bool(enabled)})
        if not enabled:
            worker = self.voice_activation_worker
            if worker and worker.isRunning():
                worker.stop()
                self.voice_state.setText("Desligando microfone…")
            else:
                self.voice_state.setText("Microfone desligado")
            self.voice_activation_button.setText("Desativar voz mãos livres" if enabled else "Ativar voz mãos livres")
            return
        if not get_secret("gemini"):
            save_settings({**load_settings(), "voice_activation_enabled": False, "hands_free_enabled": False})
            self.voice_activation_button.blockSignals(True)
            self.voice_activation_button.setChecked(False)
            self.voice_activation_button.blockSignals(False)
            self.voice_activation_button.setText("Ativar voz mãos livres")
            self.error("Cadastre uma chave Gemini em Configurações para transcrever os comandos de voz.")
            return
        if self.voice_activation_worker and self.voice_activation_worker.isRunning():
            self.voice_activation_worker.resume()
            return
        self._stop_clap_worker()
        self.voice_activation_button.setText("Desativar voz mãos livres")
        self.voice_state.setText("Abrindo microfone…")
        worker = VoiceActivationWorker(mode="jarvis_local")
        self.voice_activation_worker = worker
        worker.phrase.connect(self._handle_spoken_phrase)
        worker.state_changed.connect(self._voice_activation_state)
        worker.failed.connect(self._voice_activation_failed)
        worker.finished.connect(lambda worker=worker: self._voice_activation_finished(worker))
        self._track_worker(worker)
        worker.start()

    def _voice_activation_state(self, state: str):
        labels = {
            "escutando": "Diga Jarvis",
            "transcrevendo": "Fala detectada · transcrevendo com Gemini",
            "erro": "Falha no microfone",
            "desligado": "Microfone desligado",
            "palavra-chave": "Microfone ativo · aguardando Jarvis localmente",
            "comando": "Palavra-chave detectada · continue falando",
            "carregando-palavra-chave": "Preparando detector local (primeiro uso pode baixar o modelo)…",
        }
        self.voice_state.setText(labels.get(state, state))
        if hasattr(self, "live_voice_hint"):
            self.live_voice_hint.setText(labels.get(state, state))
        if state in {"escutando", "palavra-chave"}:
            self.core_orb.set_state("listening")
        elif state in {"transcrevendo", "comando"}:
            self.core_orb.set_state("thinking")
        elif state == "desligado" and not self.live_vision_worker:
            self.core_orb.set_state("ready")

    def _voice_activation_failed(self, message: str):
        self.voice_activation_button.setChecked(False)
        # Falha transitória do dispositivo ou da rede não muda a preferência
        # escolhida pelo usuário para a próxima inicialização.
        save_settings({**load_settings(), "voice_activation_enabled": True, "hands_free_enabled": True})
        self.error(f"Escuta automática foi desligada: {message}")

    def _voice_activation_finished(self, worker):
        if self.voice_activation_worker is worker:
            self.voice_activation_worker = None
        if not self.voice_activation_button.isChecked():
            self.voice_state.setText("Microfone desligado")
        self._refresh_privacy_indicators()

    def _pause_voice_activation(self):
        worker = self.voice_activation_worker
        if worker and worker.isRunning():
            worker.pause()

    def _resume_voice_activation(self):
        worker = self.voice_activation_worker
        if worker and worker.isRunning() and self.voice_activation_button.isChecked():
            worker.resume()

    def _handle_spoken_phrase(self, phrase: str):
        """Despacha cada frase reconhecida sem exigir botão para iniciar/parar gravação."""
        if phrase == "__WAKE__":
            self.answer_preview.setText("Estou ouvindo. Pode falar.")
            self.core_orb.set_state("listening")
            self._resume_voice_activation()
            return
        if self._quit_requested or not phrase.strip():
            return
        self.answer_preview.setText("Você: " + phrase)
        self._append("user", phrase)
        memory.add("user", phrase)
        if self._handle_memory_command(phrase, already_recorded=True):
            self._resume_voice_activation()
            return
        if self._dispatch_computer_command(phrase):
            self._resume_voice_activation()
            return
        self._start(phrase, "spoken")

