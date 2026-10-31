"""HUD desktop independente: conversa textual, setup local e histórico."""
from __future__ import annotations

import sys
from PySide6.QtCore import QThread, Signal, QUrl
from PySide6.QtWidgets import (QApplication, QDialog, QFormLayout, QLineEdit, QLabel,
                               QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget,
                               QMessageBox, QHBoxLayout, QFileDialog)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from . import memory
from .providers import analyze_image, ask_gemini, transcribe_groq
from .settings import get_secret, save_secret, load_settings, save_settings
from .vision import capture_primary_screen
from .voice import record_utterance, speak
from .computer import open_known_app
from .autostart import set_enabled
from .claps import ClapWorker


class ReplyWorker(QThread):
    finished_text = Signal(str)
    failed = Signal(str)

    def __init__(self, prompt: str, mode: str = "text"):
        super().__init__()
        self.prompt = prompt
        self.mode = mode

    def run(self):
        try:
            prompt = self.prompt
            image = None
            if self.mode == "voice":
                self.finished_text.emit("__REC__")
                prompt = transcribe_groq(record_utterance())
                if not prompt:
                    raise RuntimeError("Não detectei fala. Tente novamente.")
                self.finished_text.emit("__USER__" + prompt)
            elif self.mode == "screen":
                image = capture_primary_screen()
                self.finished_text.emit("__USER__" + prompt)
                self.finished_text.emit("__BUSY__")
                answer = analyze_image(prompt, image)
                self.finished_text.emit("__ANSWER__" + answer)
                return
            answer = ask_gemini(prompt, memory.recent())
            if self.mode == "voice":
                self.finished_text.emit("__ANSWER__" + answer)
                speak(answer)
            else:
                self.finished_text.emit("__ANSWER__" + answer)
        except Exception as exc:
            self.failed.emit(str(exc))


class DownloadWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)
    def __init__(self, url: str, folder: str):
        super().__init__(); self.url = url; self.folder = folder
    def run(self):
        try:
            from .media import download_audio
            self.completed.emit(download_audio(self.url, self.folder))
        except Exception as exc:
            self.failed.emit(str(exc))


class GmailWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)
    def __init__(self, to: str, subject: str, body: str):
        super().__init__(); self.to = to; self.subject = subject; self.body = body
    def run(self):
        try:
            from .gmail import send_email
            send_email(self.to, self.subject, self.body)
            self.completed.emit("E-mail enviado.")
        except Exception as exc:
            self.failed.emit(str(exc))


class SetupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configurar JARVIS")
        form = QFormLayout(self)
        self.gemini = QLineEdit(); self.gemini.setEchoMode(QLineEdit.EchoMode.Password)
        self.groq = QLineEdit(); self.groq.setEchoMode(QLineEdit.EchoMode.Password)
        self.email = QLineEdit(); self.phone = QLineEdit()
        form.addRow("Chave Gemini", self.gemini)
        form.addRow("Chave Groq (opcional)", self.groq)
        form.addRow("E-mail (opcional, local)", self.email)
        form.addRow("Telefone (opcional, local)", self.phone)
        save = QPushButton("Salvar neste computador")
        save.clicked.connect(self._save)
        form.addRow(save)

    def _save(self):
        try:
            save_secret("gemini", self.gemini.text())
            save_secret("groq", self.groq.text())
            save_secret("user_email", self.email.text())
            save_secret("user_phone", self.phone.text())
            self.accept()
        except Exception as exc:
            QLabel(f"Não foi possível acessar o cofre do sistema: {exc}", self).show()


class JarvisWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS · Assistente desktop")
        self.resize(1100, 760)
        self.setStyleSheet("QWidget{background:#0b1020;color:#e7ebf5;font-family:'Segoe UI';font-size:14px} QTextEdit,QLineEdit{background:#141d30;border:1px solid #34415e;border-radius:8px;padding:10px} QPushButton{background:#627cf0;border:0;border-radius:8px;padding:10px 18px;font-weight:600} QPushButton:hover{background:#7890ff}")
        central = QWidget(); self.setCentralWidget(central); layout = QVBoxLayout(central)
        head = QLabel("JARVIS  /  ASSISTENTE PESSOAL")
        head.setStyleSheet("font-size:22px;font-weight:700;color:#9fb2ff;padding:8px")
        layout.addWidget(head)
        self.chat = QTextEdit(); self.chat.setReadOnly(True); layout.addWidget(self.chat, 1)
        self.media_panel = QWidget(); media_layout = QVBoxLayout(self.media_panel)
        media_layout.setContentsMargins(6, 4, 6, 4)
        media_header = QHBoxLayout()
        media_header.addWidget(QLabel("MÍDIA · reprodução local ou URL"))
        self.media_title = QLabel("Parado"); media_header.addWidget(self.media_title, 1)
        self.compact_button = QPushButton("Minimizar")
        self.compact_button.clicked.connect(self.toggle_compact_media)
        media_header.addWidget(self.compact_button); media_layout.addLayout(media_header)
        self.media_controls = QWidget(); media_controls_layout = QHBoxLayout(self.media_controls)
        self.media_source = QLineEdit(); self.media_source.setPlaceholderText("URL de mídia")
        media_controls_layout.addWidget(self.media_source, 1)
        file_button = QPushButton("Arquivo…"); file_button.clicked.connect(self.open_media_file)
        media_controls_layout.addWidget(file_button)
        play_button = QPushButton("▶ Tocar"); play_button.clicked.connect(self.play_media)
        media_controls_layout.addWidget(play_button)
        pause_button = QPushButton("⏸ Pausar"); pause_button.clicked.connect(self.pause_media)
        media_controls_layout.addWidget(pause_button)
        download_button = QPushButton("Baixar áudio…"); download_button.clicked.connect(self.download_media)
        media_controls_layout.addWidget(download_button); media_layout.addWidget(self.media_controls)
        layout.addWidget(self.media_panel)
        self.player = QMediaPlayer(self); self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.errorOccurred.connect(lambda *_: self.media_title.setText("Falha ao abrir mídia"))
        controls = QVBoxLayout()
        self.status = QLabel("Pronto · microfone fechado")
        self.status.setStyleSheet("color:#aebce0;padding:4px")
        controls.addWidget(self.status)
        actions = QHBoxLayout()
        talk = QPushButton("🎙 Gravar comando (até 15 s)")
        talk.clicked.connect(self.talk); actions.addWidget(talk)
        vision = QPushButton("▣ Analisar minha tela…")
        vision.clicked.connect(self.analyze_screen); actions.addWidget(vision)
        self.clap_button = QPushButton("👏 Ativar duplo aplauso")
        self.clap_button.setCheckable(True)
        self.clap_button.clicked.connect(self.toggle_clap_detection)
        actions.addWidget(self.clap_button)
        controls.addLayout(actions); layout.addLayout(controls)
        row = QVBoxLayout(); self.input = QLineEdit(); self.input.setPlaceholderText("Escreva um comando…")
        self.input.returnPressed.connect(self.send); row.addWidget(self.input)
        send = QPushButton("Enviar"); send.clicked.connect(self.send); row.addWidget(send)
        layout.addLayout(row)
        settings = QPushButton("Configurações"); settings.clicked.connect(self.setup); layout.addWidget(settings)
        gmail_row = QHBoxLayout()
        configure_gmail = QPushButton("Configurar Gmail OAuth…")
        configure_gmail.clicked.connect(self.configure_gmail); gmail_row.addWidget(configure_gmail)
        compose_gmail = QPushButton("Escrever e-mail…")
        compose_gmail.clicked.connect(self.compose_gmail); gmail_row.addWidget(compose_gmail)
        layout.addLayout(gmail_row)
        autostart = QPushButton("Ativar início automático")
        autostart.clicked.connect(self.enable_autostart); layout.addWidget(autostart)
        for role, body in memory.recent(30): self._append(role, body)
        self.clap_worker = None
        if load_settings().get("clap_enabled", False):
            self.clap_button.setChecked(True)
            self._start_clap_worker()

    def _append(self, role: str, body: str):
        label = "Você" if role == "user" else "JARVIS"
        self.chat.append(f"<b>{label}</b><br>{body.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')}<br>")

    def send(self):
        prompt = self.input.text().strip()
        if not prompt: return
        self.input.clear()
        if prompt.lower().startswith("abrir "):
            target = prompt[6:].strip().lower()
            if target in {"bloco de notas", "calculadora", "explorador de arquivos"}:
                answer = QMessageBox.question(
                    self, "Confirmar ação local", f"Permitir que o JARVIS abra {target}?")
                if answer == QMessageBox.StandardButton.Yes:
                    try:
                        result = open_known_app(target)
                        self._append("user", prompt); memory.add("user", prompt)
                        self._append("assistant", result); memory.add("assistant", result)
                    except Exception as exc:
                        self.error(str(exc))
                return
        self._start(prompt, "text")

    def _start(self, prompt: str, mode: str):
        if mode == "voice": self._stop_clap_worker()
        if mode != "screen":
            self._append("user", prompt); memory.add("user", prompt)
        self.input.setEnabled(False); self.status.setText("Capturando/transmitindo somente a solicitação atual…")
        self.worker = ReplyWorker(prompt, mode)
        self.worker.finished_text.connect(self._worker_event); self.worker.failed.connect(self.error)
        self.worker.finished.connect(lambda: self.status.setText("Pronto · microfone fechado"))
        if mode == "voice": self.worker.finished.connect(self._resume_clap_worker)
        self.worker.start()

    def talk(self):
        if not get_secret("groq"):
            self.error("Cadastre a chave Groq em Configurações para ativar a transcrição push-to-talk.")
            return
        self._start("", "voice")

    def open_media_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir mídia", "",
            "Áudio e vídeo (*.mp3 *.wav *.m4a *.mp4 *.mkv);;Todos os arquivos (*)")
        if path:
            self.media_source.setText(path)
            self._play_source(QUrl.fromLocalFile(path), path.rsplit("/", 1)[-1])

    def play_media(self):
        source = self.media_source.text().strip()
        if not source:
            self.open_media_file(); return
        url = QUrl.fromUserInput(source)
        self._play_source(url, url.fileName() or url.host() or source)

    def _play_source(self, url: QUrl, title: str):
        self.player.setSource(url); self.player.play(); self.media_title.setText(title or "Reproduzindo")

    def pause_media(self):
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
        self.download_worker.completed.connect(self._download_done)
        self.download_worker.failed.connect(self.error)
        self.download_worker.start()

    def _download_done(self, path: str):
        self.status.setText("Download concluído")
        QMessageBox.information(self, "Download concluído", f"Arquivo salvo em:\n{path}")

    def toggle_compact_media(self):
        compact = self.media_controls.isVisible()
        self.media_controls.setVisible(not compact)
        self.compact_button.setText("Expandir" if compact else "Minimizar")

    def analyze_screen(self):
        prompt = self.input.text().strip() or "Descreva o que aparece na minha tela e destaque elementos importantes."
        self.input.clear()
        self._start(prompt, "screen")

    def _worker_event(self, value: str):
        if value == "__REC__":
            self.status.setText("Gravando até 15 s… aguarde o fim da gravação.")
        elif value == "__BUSY__":
            self.status.setText("Analisando a captura enviada ao Gemini…")
        elif value.startswith("__USER__"):
            text = value[8:]
            self._append("user", text); memory.add("user", text)
        elif value.startswith("__ANSWER__"):
            self.reply(value[10:])

    def reply(self, text: str):
        memory.add("assistant", text); self._append("assistant", text); self.input.setEnabled(True); self.input.setFocus()

    def error(self, text: str):
        self.chat.append(f"<span style='color:#ff8998'>Falha: {text}</span>")
        self.input.setEnabled(True)

    def setup(self):
        dialog = SetupDialog()
        dialog.email.setText(get_secret("user_email") or "")
        dialog.phone.setText(get_secret("user_phone") or "")
        dialog.exec()

    def enable_autostart(self):
        answer = QMessageBox.question(self, "Início automático",
            "Permitir que o JARVIS inicie minimizado ao entrar no sistema?")
        if answer != QMessageBox.StandardButton.Yes: return
        try:
            set_enabled(True)
            QMessageBox.information(self, "JARVIS", "Início automático ativado.")
        except Exception as exc:
            self.error(str(exc))

    def toggle_clap_detection(self, enabled: bool):
        if enabled:
            answer = QMessageBox.warning(
                self, "Escuta local por palmas",
                "Enquanto ativado, o microfone permanece aberto e o áudio é analisado localmente para detectar duas palmas. O áudio ambiente não é salvo nem enviado. Ativar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                self.clap_button.setChecked(False)
                return
            save_settings({**load_settings(), "clap_enabled": True})
            self._start_clap_worker()
        else:
            save_settings({**load_settings(), "clap_enabled": False})
            self._stop_clap_worker()

    def _start_clap_worker(self):
        if self.clap_worker and self.clap_worker.isRunning(): return
        self.clap_worker = ClapWorker()
        self.clap_worker.double_clap.connect(self._toggle_fullscreen)
        self.clap_worker.error.connect(self._clap_error)
        self.clap_worker.start()
        self.status.setText("Escutando palmas localmente · microfone aberto")

    def _stop_clap_worker(self):
        worker = self.clap_worker
        if worker and worker.isRunning():
            worker.stop(); worker.wait(2000)
        self.clap_worker = None

    def _resume_clap_worker(self):
        if self.clap_button.isChecked(): self._start_clap_worker()

    def _clap_error(self, message: str):
        self.clap_button.setChecked(False)
        save_settings({**load_settings(), "clap_enabled": False})
        self.status.setText("Detecção de palmas desativada")
        QMessageBox.warning(self, "Microfone indisponível", message)

    def _toggle_fullscreen(self):
        if self.isFullScreen(): self.showNormal()
        else: self.showFullScreen()

    def closeEvent(self, event):
        self._stop_clap_worker()
        super().closeEvent(event)

    def configure_gmail(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar OAuth Client JSON", "",
                                               "JSON (*.json)")
        if not path: return
        try:
            from .gmail import install_client_file
            install_client_file(path)
            QMessageBox.information(self, "Gmail", "Credencial local instalada. Na primeira autorização, o navegador abrirá para você entrar e conceder envio de e-mails.")
        except Exception as exc:
            self.error(str(exc))

    def compose_gmail(self):
        dialog = QDialog(self); dialog.setWindowTitle("Novo e-mail")
        form = QFormLayout(dialog)
        recipient = QLineEdit(); subject = QLineEdit(); body = QTextEdit()
        form.addRow("Para", recipient); form.addRow("Assunto", subject); form.addRow("Mensagem", body)
        send_button = QPushButton("Revisar e enviar")
        form.addRow(send_button)
        send_button.clicked.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        to, title, text = recipient.text().strip(), subject.text().strip(), body.toPlainText().strip()
        if not to or not title or not text:
            QMessageBox.warning(self, "E-mail", "Preencha destinatário, assunto e mensagem."); return
        preview = f"Para: {to}\nAssunto: {title}\n\n{text[:800]}"
        if QMessageBox.question(self, "Confirmar envio", preview) != QMessageBox.StandardButton.Yes:
            return
        self.gmail_worker = GmailWorker(to, title, text)
        self.gmail_worker.completed.connect(lambda msg: QMessageBox.information(self, "Gmail", msg))
        self.gmail_worker.failed.connect(self.error)
        self.gmail_worker.start()


def main():
    app = QApplication(sys.argv)
    if not get_secret("gemini"):
        dialog = SetupDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted: return
    window = JarvisWindow()
    if "--background" in sys.argv: window.showMinimized()
    else: window.show()
    sys.exit(app.exec())
