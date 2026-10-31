"""HUD desktop independente: conversa textual, setup local e histórico."""
from __future__ import annotations

import sys
import html
import re
from PySide6.QtCore import QThread, Signal, QUrl, QTimer
from PySide6.QtWidgets import (QApplication, QDialog, QFormLayout, QLineEdit, QLabel,
                               QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget,
                               QMessageBox, QHBoxLayout, QFileDialog, QComboBox)
from PySide6.QtWidgets import (QCheckBox, QTextBrowser, QSystemTrayIcon, QMenu, QStyle)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QStandardPaths

from . import memory
from .providers import analyze_image, ask_assistant, transcribe_groq
from .settings import get_secret, save_secret, load_settings, save_settings
from .vision import capture_primary_screen
from .voice import record_utterance, speak
from .computer import open_known_app
from .autostart import set_enabled
from .claps import ClapWorker


class ReplyWorker(QThread):
    finished_text = Signal(str)
    failed = Signal(str)

    def __init__(self, prompt: str, mode: str = "text", search_web: bool = False):
        super().__init__()
        self.prompt = prompt
        self.mode = mode
        self.search_web = search_web

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
            answer = ask_assistant(prompt, memory.recent(), self.search_web)
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


class LiveVisionWorker(QThread):
    """Observa a tela em intervalos e envia capturas ao Gemini após consentimento."""
    observation = Signal(str)
    failed = Signal(str)

    def __init__(self, interval_seconds: int = 10):
        super().__init__()
        self.interval_seconds = interval_seconds
        self._active = True

    def run(self):
        try:
            while self._active:
                image = capture_primary_screen()
                text = analyze_image(
                    "Observe esta captura recente da tela. Resuma somente mudanças ou itens "
                    "importantes visíveis; se não houver algo relevante, diga isso brevemente.", image)
                if self._active:
                    self.observation.emit(text)
                for _ in range(self.interval_seconds * 10):
                    if not self._active:
                        break
                    self.msleep(100)
        except Exception as exc:
            self.failed.emit(str(exc))

    def stop(self):
        self._active = False


class WhatsAppWebDialog(QDialog):
    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WhatsApp · JARVIS HUD"); self.resize(1080, 760)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Revise a conversa e pressione Enviar no WhatsApp Web."))
        self.web = QWebEngineView(self)
        profile = QWebEngineProfile("jarvis-whatsapp", self)
        storage = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        profile.setPersistentStoragePath(storage + "/whatsapp-profile")
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.web.setPage(QWebEnginePage(profile, self.web)); self.web.setUrl(QUrl(url))
        layout.addWidget(self.web, 1)


class ContactsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from .whatsapp import contacts
        self.setWindowTitle("Contatos permitidos · WhatsApp"); self.items = contacts()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Somente estes contatos podem receber mensagens preparadas pelo JARVIS."))
        self.listing = QComboBox(); layout.addWidget(self.listing)
        row = QHBoxLayout(); self.name = QLineEdit(); self.name.setPlaceholderText("Nome")
        self.phone = QLineEdit(); self.phone.setPlaceholderText("Telefone internacional com DDI")
        add = QPushButton("Adicionar"); remove = QPushButton("Remover selecionado")
        add.clicked.connect(self.add_contact); remove.clicked.connect(self.remove_contact)
        row.addWidget(self.name); row.addWidget(self.phone); row.addWidget(add); row.addWidget(remove)
        layout.addLayout(row); self.refresh()

    def refresh(self):
        self.listing.clear()
        for contact in self.items:
            self.listing.addItem(f"{contact['name']} · +{contact['phone']}")
        if not self.items:
            self.listing.addItem("Lista vazia")

    def add_contact(self):
        name, phone = self.name.text().strip(), "".join(c for c in self.phone.text() if c.isdigit())
        if not name or len(phone) < 8:
            QMessageBox.warning(self, "Contato", "Informe nome e telefone com DDI."); return
        self.items.append({"name": name, "phone": phone})
        from .whatsapp import save_contacts
        save_contacts(self.items); self.name.clear(); self.phone.clear(); self.refresh()

    def remove_contact(self):
        if self.items:
            index = self.listing.currentIndex()
            if index < 0 or index >= len(self.items):
                return
            self.items.pop(index)
            from .whatsapp import save_contacts
            save_contacts(self.items); self.refresh()


class WhatsAppComposeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from .whatsapp import contacts
        self.items = contacts(); self.setWindowTitle("Preparar mensagem WhatsApp")
        layout = QFormLayout(self); self.recipient = QComboBox(); self.message = QTextEdit()
        for contact in self.items:
            self.recipient.addItem(contact["name"], contact["phone"])
        layout.addRow("Contato permitido", self.recipient); layout.addRow("Mensagem", self.message)
        button = QPushButton("Revisar mensagem"); button.clicked.connect(self.accept); layout.addRow(button)

    @property
    def phone(self) -> str:
        return str(self.recipient.currentData() or "")

    @property
    def message_text(self) -> str:
        return self.message.toPlainText().strip()


class SetupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configurar JARVIS")
        form = QFormLayout(self)
        self.gemini = QLineEdit(); self.gemini.setEchoMode(QLineEdit.EchoMode.Password)
        self.groq = QLineEdit(); self.groq.setEchoMode(QLineEdit.EchoMode.Password)
        self.email = QLineEdit(); self.phone = QLineEdit()
        self.provider = QComboBox(); self.provider.addItem("Gemini", "gemini")
        self.provider.addItem("Groq", "groq")
        self.provider.setCurrentIndex(0 if load_settings().get("provider", "gemini") == "gemini" else 1)
        form.addRow("Provedor de conversa", self.provider)
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
            save_settings({**load_settings(), "provider": self.provider.currentData()})
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
        self.chat = QTextBrowser(); self.chat.setOpenExternalLinks(True); layout.addWidget(self.chat, 1)
        self.search_checkbox = QCheckBox("Pesquisar na web com Gemini nesta solicitação")
        self.search_checkbox.setToolTip("Ativa Google Search grounding; a API pode consumir cota adicional.")
        layout.addWidget(self.search_checkbox)
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
        self.live_vision_button = QPushButton("Iniciar visão contínua")
        self.live_vision_button.setCheckable(True)
        self.live_vision_button.clicked.connect(self.toggle_live_vision)
        actions.addWidget(self.live_vision_button)
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
        wa_row = QHBoxLayout()
        manage_contacts = QPushButton("Contatos permitidos…")
        manage_contacts.clicked.connect(self.manage_whatsapp_contacts)
        wa_row.addWidget(manage_contacts)
        send_whatsapp = QPushButton("Preparar mensagem WhatsApp…")
        send_whatsapp.clicked.connect(self.compose_whatsapp)
        wa_row.addWidget(send_whatsapp)
        layout.addLayout(wa_row)
        autostart = QPushButton("Ativar início automático")
        autostart.clicked.connect(self.enable_autostart); layout.addWidget(autostart)
        disable_autostart = QPushButton("Desativar início automático")
        disable_autostart.clicked.connect(self.disable_autostart); layout.addWidget(disable_autostart)
        for role, body in memory.recent(30): self._append(role, body)
        self.clap_worker = None
        self.live_vision_worker = None
        self._close_when_vision_stops = False
        self._quit_requested = False
        self.tray_icon = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._create_tray_icon()
        if load_settings().get("clap_enabled", False):
            self.clap_button.setChecked(True)
            self._start_clap_worker()

    def _append(self, role: str, body: str):
        label = "Você" if role == "user" else "JARVIS"
        safe_body = html.escape(body).replace("\n", "<br>")
        safe_body = re.sub(
            r"(https://[^\s&lt;&gt;]+)",
            lambda match: f'<a href="{match.group(1)}">{match.group(1)}</a>', safe_body)
        self.chat.append(f"<b>{label}</b><br>{safe_body}<br>")

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
        search_web = self.search_checkbox.isChecked() and mode in {"text", "voice"}
        if search_web and not get_secret("gemini"):
            self.error("Pesquisa na web usa Gemini. Cadastre uma chave Gemini em Configurações.")
            return
        if mode == "voice": self._stop_clap_worker()
        if mode != "screen":
            self._append("user", prompt); memory.add("user", prompt)
        self.input.setEnabled(False); self.status.setText("Capturando/transmitindo somente a solicitação atual…")
        self.worker = ReplyWorker(prompt, mode, search_web)
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

    def toggle_live_vision(self, enabled: bool):
        if enabled:
            if not get_secret("gemini"):
                QMessageBox.warning(self, "Gemini necessário",
                                    "A visão de tela usa Gemini. Cadastre a chave em Configurações.")
                self.live_vision_button.setChecked(False)
                return
            answer = QMessageBox.warning(
                self, "Visão contínua da tela",
                "A cada 10 segundos, uma captura do monitor principal será enviada ao Gemini "
                "para análise. Isso pode consumir cota da API e expõe o conteúdo visível ao "
                "provedor. Você pode parar a qualquer momento. Iniciar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                self.live_vision_button.setChecked(False)
                return
            self.live_vision_worker = LiveVisionWorker()
            self.live_vision_worker.observation.connect(self._live_observation)
            self.live_vision_worker.failed.connect(self.error)
            self.live_vision_worker.finished.connect(self._live_vision_finished)
            self.live_vision_worker.start()
            self.live_vision_button.setText("Parar visão contínua")
            self.status.setText("Visão contínua ativa · capturas a cada 10 segundos")
        else:
            self._stop_live_vision()

    def _live_observation(self, text: str):
        self._append("assistant", "[Observação da tela] " + text)
        memory.add("assistant", "[Observação da tela] " + text)

    def _live_vision_finished(self):
        self.live_vision_button.setChecked(False)
        self.live_vision_button.setText("Iniciar visão contínua")
        self.live_vision_button.setEnabled(True)
        self.live_vision_worker = None
        self.status.setText("Visão contínua parada")
        if self._close_when_vision_stops:
            QTimer.singleShot(0, self.close)

    def _stop_live_vision(self):
        worker = self.live_vision_worker
        if worker and worker.isRunning():
            worker.stop()

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
        self.chat.append(f"<span style='color:#ff8998'>Falha: {html.escape(text)}</span>")
        self.input.setEnabled(True)

    def setup(self):
        dialog = SetupDialog()
        dialog.gemini.setText(get_secret("gemini") or "")
        dialog.groq.setText(get_secret("groq") or "")
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

    def disable_autostart(self):
        try:
            set_enabled(False)
            QMessageBox.information(self, "JARVIS", "Início automático desativado.")
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

    def _create_tray_icon(self):
        """Mantém o HUD disponível na bandeja quando a janela é fechada."""
        self.tray_icon = QSystemTrayIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), self)
        self.tray_icon.setToolTip("JARVIS AI · assistente em segundo plano")
        menu = QMenu()
        show_action = menu.addAction("Abrir JARVIS")
        show_action.triggered.connect(self.show_from_tray)
        menu.addSeparator()
        exit_action = menu.addAction("Encerrar")
        exit_action.triggered.connect(self.quit_from_tray)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason):
        if reason in {QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick}:
            self.show_from_tray()

    def show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_from_tray(self):
        self._quit_requested = True
        self.close()

    def closeEvent(self, event):
        if self.live_vision_worker and self.live_vision_worker.isRunning():
            self._close_when_vision_stops = True
            self.live_vision_button.setEnabled(False)
            self.status.setText("Aguardando a análise atual terminar para fechar com segurança…")
            self._stop_live_vision()
            event.ignore()
            return
        self._stop_live_vision()
        if self.tray_icon and self.tray_icon.isVisible() and not self._quit_requested:
            self.hide()
            self.tray_icon.showMessage(
                "JARVIS AI", "O JARVIS continua ativo na bandeja do sistema.",
                QSystemTrayIcon.MessageIcon.Information, 2500)
            event.ignore()
            return
        self._stop_clap_worker()
        if self.tray_icon:
            self.tray_icon.hide()
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

    def manage_whatsapp_contacts(self):
        ContactsDialog(self).exec()

    def compose_whatsapp(self):
        from .whatsapp import draft_url

        dialog = WhatsAppComposeDialog(self)
        if not dialog.items:
            QMessageBox.information(
                self, "WhatsApp", "Adicione primeiro um contato permitido.")
            return
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not dialog.phone or not dialog.message_text:
            QMessageBox.warning(self, "WhatsApp", "Escolha um contato e escreva a mensagem.")
            return
        contact = next((c["name"] for c in dialog.items if c["phone"] == dialog.phone), "Contato")
        preview = f"Para: {contact} (+{dialog.phone})\n\n{dialog.message_text[:800]}"
        if QMessageBox.question(self, "Revisar mensagem", preview) != QMessageBox.StandardButton.Yes:
            return
        url = draft_url(dialog.phone, dialog.message_text)
        try:
            self.whatsapp_dialog = WhatsAppWebDialog(url, self)
            self.whatsapp_dialog.exec()
        except Exception as exc:
            QMessageBox.warning(
                self, "WhatsApp Web indisponível",
                f"Não foi possível abrir o WhatsApp dentro do JARVIS: {exc}\n"
                "Confira se Qt WebEngine está instalado e tente novamente.")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS AI")
    app.setOrganizationName("Matheus Moreira")
    selected_provider = load_settings().get("provider", "gemini")
    if not get_secret(selected_provider):
        dialog = SetupDialog()
        dialog.gemini.setText(get_secret("gemini") or "")
        dialog.groq.setText(get_secret("groq") or "")
        dialog.email.setText(get_secret("user_email") or "")
        dialog.phone.setText(get_secret("user_phone") or "")
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        selected_provider = load_settings().get("provider", "gemini")
        if not get_secret(selected_provider):
            QMessageBox.critical(None, "Configuração necessária",
                f"Cadastre uma chave {selected_provider.title()} para iniciar.")
            return
    window = JarvisWindow()
    if "--background" in sys.argv: window.showMinimized()
    else: window.show()
    sys.exit(app.exec())
