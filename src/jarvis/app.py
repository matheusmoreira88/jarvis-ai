"""HUD desktop independente: conversa textual, setup local e histórico."""
from __future__ import annotations

import sys
import html
import re
from pathlib import Path
from threading import Event
from PySide6.QtCore import QThread, Signal, QUrl, QTimer, QUrlQuery, QStandardPaths, Qt
from PySide6.QtWidgets import (QApplication, QDialog, QFormLayout, QLineEdit, QLabel,
                               QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget,
                               QMessageBox, QHBoxLayout, QFileDialog, QComboBox)
from PySide6.QtWidgets import (QCheckBox, QTextBrowser, QSystemTrayIcon, QMenu, QStyle,
                               QStackedWidget, QTabWidget)
from PySide6.QtWidgets import QInputDialog, QPlainTextEdit
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEnginePermission
from PySide6.QtWebEngineWidgets import QWebEngineView

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

    def __init__(self, prompt: str, mode: str = "text", search_web: bool = False,
                 history: list[tuple[str, str]] | None = None):
        super().__init__()
        self.prompt = prompt
        self.mode = mode
        self.search_web = search_web
        self.history = history or []
        self.stop_event = Event()

    def stop_recording(self):
        """Ask a voice capture to finish now; other worker modes ignore this signal."""
        self.stop_event.set()

    def run(self):
        try:
            prompt = self.prompt
            image = None
            if self.mode == "voice":
                self.finished_text.emit("__REC__")
                prompt = transcribe_groq(record_utterance(self.stop_event.is_set))
                if not prompt:
                    raise RuntimeError("Não detectei fala. Tente novamente.")
                self.finished_text.emit("__VOICE_COMMAND__" + prompt)
                return
            elif self.mode == "screen":
                image = capture_primary_screen()
                self.finished_text.emit("__USER__" + prompt)
                self.finished_text.emit("__BUSY__")
                answer = analyze_image(prompt, image)
                self.finished_text.emit("__ANSWER__" + answer)
                return
            answer = ask_assistant(prompt, self.history, self.search_web)
            if self.mode == "spoken":
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
    """Transmite quadros da tela à Gemini Live enquanto a pessoa consentir."""
    observation = Signal(str)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self._active = True

    def run(self):
        try:
            import asyncio
            from google import genai
            from google.genai import types
            from .settings import get_secret

            asyncio.run(self._stream(genai, types, get_secret("gemini")))
        except Exception as exc:
            self.failed.emit(str(exc))

    async def _stream(self, genai, types, api_key: str | None):
        """Envia imagens pela sessão Live e renova a sessão antes do limite de duração."""
        import asyncio

        if not api_key:
            raise RuntimeError("Configure a chave Gemini para usar visão contínua.")
        client = genai.Client(api_key=api_key)
        try:
            while self._active:
                async with client.aio.live.connect(
                    model="gemini-3.1-flash-live-preview",
                    config={"response_modalities": ["AUDIO"], "output_audio_transcription": {}},
                ) as session:
                    await session.send_realtime_input(text=(
                        "Observe continuamente as imagens da tela que eu enviar. Em português, "
                        "avise apenas quando houver uma mudança relevante ou eu parecer precisar "
                        "de ajuda. Nunca execute ações no computador."
                    ))

                    async def receive_updates():
                        async for message in session.receive():
                            if not self._active:
                                break
                            content = getattr(message, "server_content", None)
                            transcript = getattr(content, "output_transcription", None) if content else None
                            text = getattr(transcript, "text", "").strip() if transcript else ""
                            if text:
                                self.observation.emit(text)

                    receiver = asyncio.create_task(receive_updates())
                    try:
                        # A Live API aceita até um quadro de vídeo por segundo.
                        for _ in range(110):
                            if not self._active or receiver.done():
                                break
                            await session.send_realtime_input(video=types.Blob(
                                data=capture_primary_screen(), mime_type="image/png"))
                            await asyncio.sleep(1)
                    finally:
                        receiver.cancel()
                        try:
                            await receiver
                        except asyncio.CancelledError:
                            pass
                if self._active:
                    await asyncio.sleep(0.2)
        finally:
            await client.aio.aclose()

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
        page = QWebEnginePage(profile, self.web)
        page.permissionRequested.connect(self._handle_web_permission)
        self.web.setPage(page); self.web.setUrl(QUrl(url))
        layout.addWidget(self.web, 1)

    def _handle_web_permission(self, permission):
        """Ask every time before WhatsApp Web uses this app's microphone or camera."""
        allowed_hosts = {"web.whatsapp.com", "www.whatsapp.com"}
        permission_types = QWebEnginePermission.PermissionType
        media_types = {
            permission_types.MediaAudioCapture,
            permission_types.MediaVideoCapture,
            permission_types.MediaAudioVideoCapture,
        }
        if (not permission.isValid()
                or permission.origin().host().lower() not in allowed_hosts
                or permission.permissionType() not in media_types):
            permission.deny()
            return
        label = {
            permission_types.MediaAudioCapture: "microfone",
            permission_types.MediaVideoCapture: "câmera",
            permission_types.MediaAudioVideoCapture: "microfone e câmera",
        }[permission.permissionType()]
        choice = QMessageBox.question(
            self, "Permissão do WhatsApp Web",
            f"Permitir que web.whatsapp.com use seu {label} para uma chamada iniciada "
            "ou atendida por você? Essa autorização vale para esta solicitação.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if choice == QMessageBox.StandardButton.Yes:
            permission.grant()
        else:
            permission.deny()


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
        form.addRow("Chave Groq", self.groq)
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
            QMessageBox.warning(
                self, "Configurações não salvas",
                f"Não foi possível acessar o cofre de credenciais do sistema: {exc}")


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
        self.tabs = QTabWidget(); layout.addWidget(self.tabs, 1)

        assistant_page = QWidget(); assistant_layout = QVBoxLayout(assistant_page)
        assistant_layout.addWidget(QLabel(
            "Comandos locais: ‘abrir calculadora’, ‘digitar: texto’ e ‘pressionar: enter’. "
            "Digitação e teclas pedem confirmação."))
        self.chat = QTextBrowser(); self.chat.setOpenExternalLinks(True)
        assistant_layout.addWidget(self.chat, 1)
        self.search_checkbox = QCheckBox("Pesquisar na web com Gemini nesta solicitação")
        self.search_checkbox.setToolTip("Ativa Google Search grounding; a API pode consumir cota adicional.")
        assistant_layout.addWidget(self.search_checkbox)
        assistant_actions = QHBoxLayout()
        self.talk_button = QPushButton("🎙 Falar")
        self.talk_button.clicked.connect(self.talk); assistant_actions.addWidget(self.talk_button)
        vision = QPushButton("▣ Analisar minha tela…")
        vision.clicked.connect(self.analyze_screen); assistant_actions.addWidget(vision)
        self.live_vision_button = QPushButton("Iniciar visão contínua")
        self.live_vision_button.setCheckable(True)
        self.live_vision_button.clicked.connect(self.toggle_live_vision)
        assistant_actions.addWidget(self.live_vision_button)
        self.clap_button = QPushButton("👏 Ativar duplo aplauso")
        self.clap_button.setCheckable(True)
        self.clap_button.clicked.connect(self.toggle_clap_detection)
        assistant_actions.addWidget(self.clap_button)
        assistant_layout.addLayout(assistant_actions)
        chat_row = QHBoxLayout()
        self.input = QLineEdit(); self.input.setPlaceholderText("Escreva um comando…")
        self.input.returnPressed.connect(self.send); chat_row.addWidget(self.input, 1)
        send = QPushButton("Enviar"); send.clicked.connect(self.send); chat_row.addWidget(send)
        assistant_layout.addLayout(chat_row)
        self.tabs.addTab(assistant_page, "Assistente")

        self.media_panel = QWidget(); media_layout = QVBoxLayout(self.media_panel)
        media_layout.setContentsMargins(6, 4, 6, 4)
        media_header = QHBoxLayout()
        media_header.addWidget(QLabel("MÍDIA · arquivos, URLs e YouTube"))
        self.media_title = QLabel("Parado"); media_header.addWidget(self.media_title, 1)
        self.compact_button = QPushButton("Minimizar")
        self.compact_button.clicked.connect(self.toggle_compact_media)
        media_header.addWidget(self.compact_button); media_layout.addLayout(media_header)
        self.media_view = QStackedWidget(self.media_panel)
        self.media_idle = QLabel("Escolha um arquivo, URL ou pesquise uma música no YouTube.")
        self.media_idle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_widget = QVideoWidget(self.media_view); self.video_widget.setMinimumHeight(260)
        self.youtube_view = QWebEngineView(self.media_view); self.youtube_view.setMinimumHeight(300)
        profile = QWebEngineProfile("jarvis-youtube", self)
        storage = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        profile.setPersistentStoragePath(storage + "/youtube-profile")
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.youtube_view.setPage(QWebEnginePage(profile, self.youtube_view))
        self.media_view.addWidget(self.media_idle)
        self.media_view.addWidget(self.video_widget)
        self.media_view.addWidget(self.youtube_view)
        media_layout.addWidget(self.media_view, 1)
        self.media_controls = QWidget(); media_controls_layout = QHBoxLayout(self.media_controls)
        self.media_source = QLineEdit(); self.media_source.setPlaceholderText("URL ou nome da música no YouTube")
        media_controls_layout.addWidget(self.media_source, 1)
        file_button = QPushButton("Arquivo…"); file_button.clicked.connect(self.open_media_file)
        media_controls_layout.addWidget(file_button)
        play_button = QPushButton("▶ Tocar / buscar"); play_button.clicked.connect(self.play_media)
        media_controls_layout.addWidget(play_button)
        pause_button = QPushButton("⏸ Pausar"); pause_button.clicked.connect(self.pause_media)
        media_controls_layout.addWidget(pause_button)
        download_button = QPushButton("Baixar áudio…"); download_button.clicked.connect(self.download_media)
        media_controls_layout.addWidget(download_button); media_layout.addWidget(self.media_controls)
        self.tabs.addTab(self.media_panel, "Mídia")
        self.player = QMediaPlayer(self); self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.errorOccurred.connect(lambda *_: self.media_title.setText("Falha ao abrir mídia"))

        self.status = QLabel("Pronto · microfone fechado")
        self.status.setStyleSheet("color:#aebce0;padding:4px")
        layout.addWidget(self.status)

        integrations_page = QWidget(); integrations_layout = QVBoxLayout(integrations_page)
        settings_row = QHBoxLayout()
        settings = QPushButton("Configurações"); settings.clicked.connect(self.setup)
        settings_row.addWidget(settings, 1)
        clear_memory = QPushButton("Apagar memória local…")
        clear_memory.clicked.connect(self.clear_local_memory); settings_row.addWidget(clear_memory, 1)
        integrations_layout.addLayout(settings_row)
        gmail_row = QHBoxLayout()
        configure_gmail = QPushButton("Configurar Gmail OAuth…")
        configure_gmail.clicked.connect(self.configure_gmail); gmail_row.addWidget(configure_gmail, 1)
        compose_gmail = QPushButton("Escrever e-mail…")
        compose_gmail.clicked.connect(self.compose_gmail); gmail_row.addWidget(compose_gmail, 1)
        integrations_layout.addLayout(gmail_row)
        wa_row = QHBoxLayout()
        manage_contacts = QPushButton("Contatos permitidos…")
        manage_contacts.clicked.connect(self.manage_whatsapp_contacts); wa_row.addWidget(manage_contacts, 1)
        send_whatsapp = QPushButton("Preparar mensagem WhatsApp…")
        send_whatsapp.clicked.connect(self.compose_whatsapp); wa_row.addWidget(send_whatsapp, 1)
        integrations_layout.addLayout(wa_row)
        startup_row = QHBoxLayout()
        autostart = QPushButton("Ativar início automático")
        autostart.clicked.connect(self.enable_autostart); startup_row.addWidget(autostart, 1)
        disable_autostart = QPushButton("Desativar início automático")
        disable_autostart.clicked.connect(self.disable_autostart); startup_row.addWidget(disable_autostart, 1)
        integrations_layout.addLayout(startup_row)
        modify_source = QPushButton("Propor alteração no código do JARVIS…")
        modify_source.clicked.connect(self.propose_source_change)
        integrations_layout.addWidget(modify_source)
        restore_source = QPushButton("Restaurar backup de código…")
        restore_source.clicked.connect(self.restore_source_backup)
        integrations_layout.addWidget(restore_source)
        integrations_layout.addStretch(1)
        self.tabs.addTab(integrations_page, "Integrações")
        for role, body in memory.recent(30): self._append(role, body)
        self.clap_worker = None
        self.live_vision_worker = None
        self.pending_voice_command = None
        self._close_when_vision_stops = False
        self._quit_requested = False
        self._waiting_for_workers = False
        self.background_workers: set[QThread] = set()
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
        if self._dispatch_computer_command(prompt):
            return
        self._start(prompt, "text")

    def _dispatch_computer_command(self, prompt: str) -> bool:
        """Executa apenas ações locais explícitas; nunca interpreta saída do modelo como ação."""
        normalized = prompt.strip()
        lowered = normalized.lower()
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
            if target not in {"bloco de notas", "calculadora", "explorador de arquivos"}:
                return False
            answer = QMessageBox.question(
                self, "Confirmar ação local", f"Permitir que o JARVIS abra {target}?")
            if answer == QMessageBox.StandardButton.Yes:
                try:
                    result = open_known_app(target)
                    self._record_control_action(prompt, result)
                except Exception as exc:
                    self.error(str(exc))
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
                self._append("user", "[Comando para digitar; conteúdo omitido do histórico]")
                memory.add("user", "[Comando para digitar; conteúdo omitido do histórico]")
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

    def _start(self, prompt: str, mode: str):
        search_web = self.search_checkbox.isChecked() and mode in {"text", "spoken"}
        if search_web and not get_secret("gemini"):
            self.error("Pesquisa na web usa Gemini. Cadastre uma chave Gemini em Configurações.")
            return
        if mode in {"voice", "spoken"}: self._stop_clap_worker()
        if mode not in {"screen", "spoken", "voice"}:
            self._append("user", prompt); memory.add("user", prompt)
        history = memory.recent()
        if mode in {"text", "spoken"} and history and history[-1] == ("user", prompt):
            history.pop()  # The provider adapter appends the current prompt itself.
        self.input.setEnabled(False); self.status.setText("Capturando/transmitindo somente a solicitação atual…")
        self.worker = ReplyWorker(prompt, mode, search_web, history)
        self._track_worker(self.worker)
        self.talk_button.setEnabled(mode == "voice")
        if mode == "voice":
            self.talk_button.setText("Parar gravação")
        else:
            self.talk_button.setText("🎙 Falar")
        self.worker.finished_text.connect(self._worker_event); self.worker.failed.connect(self.error)
        self.worker.finished.connect(lambda: self.status.setText("Pronto · microfone fechado"))
        if mode == "voice":
            self.worker.finished.connect(self._finish_voice_button)
            self.worker.finished.connect(self._after_voice_recording)
        elif mode == "spoken": self.worker.finished.connect(self._resume_clap_worker)
        else: self.worker.finished.connect(lambda: self.talk_button.setEnabled(True))
        self.worker.start()

    def talk(self):
        worker = getattr(self, "worker", None)
        if worker and worker.isRunning() and worker.mode == "voice":
            self.talk_button.setText("Encerrando gravação…")
            self.talk_button.setEnabled(False)
            worker.stop_recording()
            return
        if not get_secret("groq"):
            self.error("Cadastre a chave Groq em Configurações para ativar a transcrição push-to-talk.")
            return
        self._start("", "voice")

    def _finish_voice_button(self):
        self.talk_button.setText("🎙 Falar")
        self.talk_button.setEnabled(True)

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
            # A plain song name opens YouTube search; playback remains under user control.
            search_url = QUrl("https://www.youtube.com/results")
            query = QUrlQuery()
            query.addQueryItem("search_query", source)
            search_url.setQuery(query)
            self._play_youtube(search_url)
            return
        self._play_source(candidate_url, candidate_url.fileName() or candidate_url.host() or source)

    def _play_youtube(self, url: QUrl):
        self.player.stop()
        self.media_view.setCurrentWidget(self.youtube_view)
        self.youtube_view.setUrl(url)
        self.media_title.setText("YouTube · use os controles da página para reproduzir")

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

    def toggle_compact_media(self):
        compact = self.media_controls.isVisible()
        self.media_controls.setVisible(not compact)
        self.media_view.setVisible(not compact)
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
                "O JARVIS transmitirá imagens do monitor principal à Gemini Live, em até um "
                "quadro por segundo. As observações transcritas aparecerão no histórico do HUD. "
                "As imagens e o áudio gerado passam pelo serviço Google e podem consumir cota. A conexão "
                "será renovada periodicamente; você pode parar a qualquer momento. Iniciar?",
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
            self.status.setText("Visão Gemini Live ativa · até 1 quadro por segundo")
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
            self.live_vision_button.setEnabled(False)
            self.live_vision_button.setText("Parando após a solicitação atual…")
            worker.stop()

    def _worker_event(self, value: str):
        if value == "__REC__":
            self.status.setText("Ouvindo em tempo real · encerra após silêncio ou pelo botão (máx. 3 min).")
        elif value == "__BUSY__":
            self.status.setText("Analisando a captura enviada ao Gemini…")
        elif value.startswith("__USER__"):
            text = value[8:]
            self._append("user", text); memory.add("user", text)
        elif value.startswith("__VOICE_COMMAND__"):
            self.pending_voice_command = value[len("__VOICE_COMMAND__"):]
        elif value.startswith("__ANSWER__"):
            self.reply(value[10:])

    def reply(self, text: str):
        memory.add("assistant", text); self._append("assistant", text); self.input.setEnabled(True); self.input.setFocus()

    def _after_voice_recording(self):
        if self._quit_requested:
            self.pending_voice_command = None
            return
        prompt = (self.pending_voice_command or "").strip()
        self.pending_voice_command = None
        if not prompt:
            self.input.setEnabled(True)
            self._resume_clap_worker()
            return
        if self._dispatch_computer_command(prompt):
            self.input.setEnabled(True)
            self._resume_clap_worker()
            return
        self._append("user", prompt); memory.add("user", prompt)
        self._start(prompt, "spoken")

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

    def propose_source_change(self):
        """Só altera o próprio programa após gerar, exibir e confirmar uma proposta."""
        from .self_modify import SOURCE_ROOT, apply_file_update, propose_file_update

        path, _ = QFileDialog.getOpenFileName(
            self, "Escolher módulo do JARVIS", str(SOURCE_ROOT), "Python (*.py)")
        if not path:
            return
        request, accepted = QInputDialog.getMultiLineText(
            self, "Descrever alteração", "O que você quer que o JARVIS mude neste arquivo?")
        if not accepted or not request.strip():
            return
        try:
            proposal = propose_file_update(path, request)
        except Exception as exc:
            self.error(str(exc))
            return

        preview = QDialog(self)
        preview.setWindowTitle("Revisar proposta de alteração")
        preview.resize(900, 700)
        layout = QVBoxLayout(preview)
        note = QLabel("Revise o arquivo completo. A aplicação cria um backup local antes de gravar.")
        layout.addWidget(note)
        editor = QPlainTextEdit()
        editor.setPlainText(proposal)
        editor.setReadOnly(True)
        layout.addWidget(editor, 1)
        controls = QHBoxLayout()
        apply_button = QPushButton("Confirmar e aplicar")
        cancel_button = QPushButton("Cancelar")
        controls.addWidget(apply_button)
        controls.addWidget(cancel_button)
        layout.addLayout(controls)
        apply_button.clicked.connect(preview.accept)
        cancel_button.clicked.connect(preview.reject)
        if preview.exec() != QDialog.DialogCode.Accepted:
            return
        if QMessageBox.question(
            self, "Confirmar gravação",
            "Aplicar esta versão revisada ao código? Reinicie o JARVIS para carregar a mudança.") != QMessageBox.StandardButton.Yes:
            return
        try:
            backup = apply_file_update(path, proposal)
            QMessageBox.information(self, "Código atualizado", f"Backup salvo em:\n{backup}")
        except Exception as exc:
            self.error(str(exc))

    def restore_source_backup(self):
        """Permite escolher um backup validado para reverter uma alteração anterior."""
        from .self_modify import backups_for_file, restore_backup, SOURCE_ROOT

        path, _ = QFileDialog.getOpenFileName(
            self, "Escolher módulo", str(SOURCE_ROOT), "Python (*.py)")
        if not path:
            return
        try:
            backups = backups_for_file(path)
        except Exception as exc:
            self.error(str(exc))
            return
        if not backups:
            QMessageBox.information(self, "Sem backups", "Este módulo ainda não tem backups.")
            return
        labels = [backup.name for backup in backups]
        choice, accepted = QInputDialog.getItem(
            self, "Restaurar backup", "Escolha a versão salva:", labels, 0, False)
        if not accepted:
            return
        selected = backups[labels.index(choice)]
        if QMessageBox.question(
            self, "Confirmar restauração",
            f"Restaurar {selected.name}? A versão atual também será guardada como backup.") != QMessageBox.StandardButton.Yes:
            return
        try:
            safety_copy = restore_backup(path, str(selected))
            QMessageBox.information(
                self, "Backup restaurado",
                f"Reinicie o JARVIS para carregar a versão restaurada.\n\n"
                f"Backup da versão substituída:\n{safety_copy}")
        except Exception as exc:
            self.error(str(exc))
            return

    def clear_local_memory(self):
        worker = getattr(self, "worker", None)
        vision = self.live_vision_worker
        if ((worker and worker.isRunning()) or (vision and vision.isRunning())):
            QMessageBox.information(
                self, "Memória em uso",
                "Aguarde a conversa e a visão contínua terminarem antes de apagar o histórico.")
            return
        answer = QMessageBox.question(
            self, "Apagar memória local",
            "Apagar permanentemente o histórico de conversa salvo neste computador?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        memory.clear()
        self.chat.clear()
        QMessageBox.information(self, "Memória", "Histórico local apagado.")

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
        worker = getattr(self, "worker", None)
        if self._quit_requested and worker and worker.isRunning() and worker.mode == "voice":
            worker.stop_recording()
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
        active_workers = [worker for worker in self.background_workers if worker.isRunning()]
        if active_workers:
            self.status.setText("Encerrando após terminar os trabalhos em andamento…")
            if not self._waiting_for_workers:
                self._waiting_for_workers = True
                for worker in active_workers:
                    worker.finished.connect(self._close_after_background_workers)
            event.ignore()
            return
        self._stop_clap_worker()
        if self.tray_icon:
            self.tray_icon.hide()
        super().closeEvent(event)

    def _close_after_background_workers(self):
        if any(worker.isRunning() for worker in self.background_workers):
            return
        self._waiting_for_workers = False
        QTimer.singleShot(0, self.close)

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
        self._track_worker(self.gmail_worker)
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
    # Peça as duas chaves na primeira configuração, para deixar os dois serviços prontos.
    if not get_secret("gemini") or not get_secret("groq"):
        dialog = SetupDialog()
        dialog.gemini.setText(get_secret("gemini") or "")
        dialog.groq.setText(get_secret("groq") or "")
        dialog.email.setText(get_secret("user_email") or "")
        dialog.phone.setText(get_secret("user_phone") or "")
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        selected_provider = load_settings().get("provider", "gemini")
        missing = [name for name, label in (("gemini", "Gemini"), ("groq", "Groq"))
                   if not get_secret(name)]
        if missing:
            QMessageBox.critical(None, "Configuração necessária",
                "Cadastre as chaves de API para iniciar: " + ", ".join(missing) + ".")
            return
    window = JarvisWindow()
    if "--background" in sys.argv: window.showMinimized()
    else: window.show()
    sys.exit(app.exec())
