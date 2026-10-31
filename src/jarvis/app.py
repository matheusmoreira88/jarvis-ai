"""HUD desktop independente: conversa textual, setup local e histórico."""
from __future__ import annotations

import sys
import html
import json
import re
from pathlib import Path
from threading import Event
from PySide6.QtCore import QThread, Signal, QUrl, QTimer, QUrlQuery, QStandardPaths, Qt, QLockFile
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (QApplication, QDialog, QFormLayout, QLineEdit, QLabel,
                               QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget,
                               QMessageBox, QHBoxLayout, QFileDialog, QComboBox)
from PySide6.QtWidgets import (QCheckBox, QTextBrowser, QSystemTrayIcon, QMenu, QStyle,
                               QStackedWidget, QTabWidget)
from PySide6.QtWidgets import QInputDialog, QPlainTextEdit
from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtWidgets import QListWidget, QListWidgetItem
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEnginePermission
from PySide6.QtWebEngineWidgets import QWebEngineView

from . import memory
from .providers import analyze_image, ask_assistant, propose_screen_action, transcribe_groq
from .settings import get_secret, save_secret, load_settings, save_settings
from .vision import capture_primary_screen
from .voice import record_utterance, wait_for_spoken_utterance, speak
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
                recording = record_utterance(self.stop_event.is_set)
                self.finished_text.emit("__TRANSCRIBING__")
                prompt = transcribe_groq(recording)
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
            elif self.mode == "plan":
                image = capture_primary_screen()
                self.finished_text.emit("__BUSY__")
                action = propose_screen_action(prompt, image)
                self.finished_text.emit("__PLAN__" + json.dumps(action, ensure_ascii=False))
                return
            answer = ask_assistant(prompt, self.history, self.search_web)
            if self.mode == "spoken":
                self.finished_text.emit("__ANSWER__" + answer)
                speak(answer)
            else:
                self.finished_text.emit("__ANSWER__" + answer)
        except Exception as exc:
            self.failed.emit(str(exc))


class VoiceActivationWorker(QThread):
    """Detecta fala localmente e transcreve somente frases após silêncio."""
    phrase = Signal(str)
    state_changed = Signal(str)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self._stop_event = Event()
        self._pause_event = Event()

    def stop(self):
        self._stop_event.set()
        self._pause_event.clear()

    def pause(self):
        self._pause_event.set()

    def resume(self):
        self._pause_event.clear()

    def run(self):
        import time
        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                time.sleep(0.08)
                continue
            try:
                self.state_changed.emit("escutando")
                audio = wait_for_spoken_utterance(
                    self._stop_event.is_set, self._pause_event.is_set)
                if audio is None:
                    continue
                self._pause_event.set()
                self.state_changed.emit("transcrevendo")
                phrase = transcribe_groq(audio).strip()
                if phrase:
                    self.phrase.emit(phrase)
                else:
                    self._pause_event.clear()
            except Exception as exc:
                self.state_changed.emit("erro")
                self.failed.emit(str(exc))
                self._pause_event.set()
        self.state_changed.emit("desligado")


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
            from .providers import SYSTEM_INSTRUCTION
            from .settings import get_secret

            asyncio.run(self._stream(genai, types, get_secret("gemini")))
        except Exception as exc:
            self.failed.emit(str(exc))

    async def _stream(self, genai, types, api_key: str | None):
        """Envia imagens pela sessão Live e renova a sessão antes do limite de duração."""
        import asyncio
        import sounddevice as sd

        if not api_key:
            raise RuntimeError("Configure a chave Gemini para usar visão contínua.")
        client = genai.Client(api_key=api_key)
        audio_output = None
        audio_error_reported = False
        try:
            while self._active:
                async with client.aio.live.connect(
                    model="gemini-3.8-live",
                    config={
                        "response_modalities": ["AUDIO"],
                        "output_audio_transcription": {},
                        "system_instruction": SYSTEM_INSTRUCTION,
                    },
                ) as session:
                    async def receive_updates():
                        nonlocal audio_output, audio_error_reported
                        async for message in session.receive():
                            if not self._active:
                                break
                            content = getattr(message, "server_content", None)
                            transcript = getattr(content, "output_transcription", None) if content else None
                            text = getattr(transcript, "text", "").strip() if transcript else ""
                            if text:
                                self.observation.emit(text)
                            model_turn = getattr(content, "model_turn", None) if content else None
                            for part in (getattr(model_turn, "parts", ()) if model_turn else ()):
                                audio = getattr(part, "inline_data", None)
                                data = getattr(audio, "data", None) if audio else None
                                if data and audio_output is not False:
                                    try:
                                        if audio_output is None:
                                            audio_output = sd.RawOutputStream(
                                                samplerate=24_000, channels=1, dtype="int16")
                                            audio_output.start()
                                        # Este worker já roda fora da UI; a escrita bloqueante não congela o HUD.
                                        audio_output.write(data)
                                    except Exception as exc:
                                        if audio_output is not None:
                                            try:
                                                audio_output.stop()
                                            except Exception:
                                                pass
                                            try:
                                                audio_output.close()
                                            except Exception:
                                                pass
                                        audio_output = False
                                        if not audio_error_reported:
                                            self.failed.emit(
                                                f"Não foi possível reproduzir a voz da Gemini Live: {exc}")
                                            audio_error_reported = True

                    receiver = asyncio.create_task(receive_updates())
                    try:
                        # A Live API aceita até um quadro de vídeo por segundo.
                        for frame_number in range(110):
                            if not self._active or receiver.done():
                                break
                            await session.send_realtime_input(video=types.Blob(
                                data=capture_primary_screen(), mime_type="image/png"))
                            # Vídeo sozinho não inicia uma resposta: peça uma leitura após cinco quadros.
                            if frame_number % 5 == 4:
                                await session.send_realtime_input(text=(
                                    "Analise as imagens recentes da tela. Em português, informe "
                                    "somente mudanças importantes ou algo que pareça exigir ajuda. "
                                    "Não execute ações no computador."
                                ))
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
            try:
                if audio_output not in (None, False):
                    try:
                        audio_output.stop()
                    finally:
                        audio_output.close()
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


class AppCatalogWorker(QThread):
    """Enumerates installed Windows applications without blocking the interface."""
    loaded = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            from .computer import list_installed_apps
            self.loaded.emit(list_installed_apps())
        except Exception as exc:
            self.failed.emit(f"Não foi possível listar os aplicativos: {exc}")


class InstalledAppsDialog(QDialog):
    """Busca e seleciona apps instalados; a janela não inicia nada por conta própria."""
    def __init__(self, apps: list[dict[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aplicativos instalados")
        self.resize(620, 680)
        self.apps = apps
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"{len(apps)} aplicativos encontrados no menu Iniciar e nos registros do Windows. "
            "Escolha um item e selecione Abrir para iniciar."))
        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar aplicativo pelo nome…")
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)
        self.listing = QListWidget(); self.listing.itemDoubleClicked.connect(lambda *_: self.accept())
        layout.addWidget(self.listing, 1)
        self._items: list[QListWidgetItem] = []
        for app in apps:
            item = QListWidgetItem(app["name"])
            item.setData(Qt.ItemDataRole.UserRole, app)
            self.listing.addItem(item); self._items.append(item)
        if self._items:
            self.listing.setCurrentItem(self._items[0])
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Open,
            parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Open).setText("Abrir aplicativo")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _filter(self, text: str):
        query = text.casefold().strip()
        first_visible = None
        for item in self._items:
            visible = query in item.text().casefold()
            item.setHidden(not visible)
            if visible and first_visible is None:
                first_visible = item
        if self.listing.currentItem() is None or self.listing.currentItem().isHidden():
            self.listing.setCurrentItem(first_visible)

    @property
    def selected_app(self) -> dict[str, str] | None:
        item = self.listing.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None


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
        self.resize(1280, 860)
        self.setMinimumSize(900, 640)
        self.setStyleSheet("""
            QMainWindow, QWidget#centralSurface { background: #080b12; color: #edf2fb; }
            QWidget { color: #edf2fb; font-family: 'Segoe UI'; font-size: 13px; }
            QLabel { background: transparent; }
            QWidget#sideRail { background: #0d121c; border: 1px solid #1b2635; border-radius: 20px; }
            QLabel#brandTitle { color: #f5f8ff; font-size: 29px; font-weight: 800; letter-spacing: 2px; }
            QLabel#brandSubtitle, QLabel#mutedLabel { color: #7d8ba0; font-size: 10px; font-weight: 650; letter-spacing: 1px; }
            QLabel#pageTitle { color: #f2f6fd; font-size: 20px; font-weight: 700; }
            QLabel#sectionLabel { color: #8c9bb1; font-size: 10px; font-weight: 750; letter-spacing: 1.1px; padding: 4px 2px 0; }
            QLabel#statusLabel { color: #90a0b6; background: #101723; border: 1px solid #202c3d; border-radius: 13px; padding: 8px 13px; }
            QLabel#voiceState { color: #8897ab; font-size: 11px; }
            QTabWidget#mainTabs::pane { background: transparent; border: none; }
            QTabBar#hiddenTabs { max-height: 0; }
            QTextBrowser, QTextEdit, QLineEdit, QPlainTextEdit, QComboBox, QListWidget {
                background: #0a1019; color: #e8eef8; border: 1px solid #202c3d;
                border-radius: 14px; padding: 13px; selection-background-color: #276c61; }
            QTextBrowser { padding: 18px; }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QListWidget:focus { border: 1px solid #43bca3; }
            QPushButton { color: #dce5f2; background: #131d2b; border: 1px solid #263549;
                border-radius: 11px; padding: 10px 14px; font-weight: 650; }
            QPushButton:hover { background: #1a293a; border-color: #3a526e; }
            QPushButton:pressed { background: #101824; }
            QPushButton:checked { color: #cafff0; background: #11312d; border-color: #276c5d; }
            QPushButton#primaryAction { color: #061812; background: #55d4ad; border-color: #55d4ad; }
            QPushButton#primaryAction:hover { background: #78e5c3; }
            QPushButton#navButton { text-align: left; color: #8f9eb2; background: transparent;
                border: 1px solid transparent; padding: 13px 14px; }
            QPushButton#navButton:hover { color: #edf4ff; background: #131d2a; }
            QPushButton#navButton:checked { color: #d3fff2; background: #12302d; border-color: #1e5147; }
            QPushButton#listenButton { text-align: left; padding: 12px 11px; }
            QCheckBox { spacing: 9px; color: #afbdd0; }
            QCheckBox::indicator { width: 17px; height: 17px; border-radius: 5px; background: #0b1421; border: 1px solid #42536b; }
            QCheckBox::indicator:checked { background: #45c5a5; border-color: #45c5a5; }
            QMenu { background: #101a29; border: 1px solid #293b52; }
            QMenu::item:selected { background: #1c3048; }
            QScrollBar:vertical { background: #0a111c; width: 9px; margin: 3px; }
            QScrollBar::handle:vertical { background: #34465d; min-height: 28px; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        central = QWidget(); central.setObjectName("centralSurface"); self.setCentralWidget(central)
        layout = QHBoxLayout(central); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(16)

        side_rail = QWidget(); side_rail.setObjectName("sideRail"); side_rail.setFixedWidth(224)
        rail_layout = QVBoxLayout(side_rail); rail_layout.setContentsMargins(16, 22, 16, 18); rail_layout.setSpacing(9)
        head = QLabel("JARVIS"); head.setObjectName("brandTitle")
        subtitle = QLabel("DESKTOP INTELLIGENCE"); subtitle.setObjectName("brandSubtitle")
        rail_layout.addWidget(head); rail_layout.addWidget(subtitle)
        rail_layout.addSpacing(30)
        rail_caption = QLabel("ESPAÇO DE TRABALHO"); rail_caption.setObjectName("sectionLabel")
        rail_layout.addWidget(rail_caption)
        self.tabs = QTabWidget(); self.tabs.setObjectName("mainTabs"); self.tabs.tabBar().hide()
        self.nav_buttons = []
        for index, label in enumerate(("Conversa", "Mídia", "Integrações")):
            nav = QPushButton(label); nav.setObjectName("navButton"); nav.setCheckable(True)
            nav.clicked.connect(lambda checked=False, index=index: self.tabs.setCurrentIndex(index))
            rail_layout.addWidget(nav); self.nav_buttons.append(nav)
        self.nav_buttons[0].setChecked(True)
        rail_layout.addStretch(1)
        self.voice_activation_button = QPushButton("Ligar escuta automática")
        self.voice_activation_button.setObjectName("listenButton"); self.voice_activation_button.setCheckable(True)
        self.voice_activation_button.setToolTip(
            "Detecta fala no microfone. O áudio ambiente fica em buffers locais curtos; "
            "somente frases detectadas são enviadas à Groq para transcrição.")
        self.voice_activation_button.toggled.connect(self.toggle_voice_activation)
        rail_layout.addWidget(self.voice_activation_button)
        self.voice_state = QLabel("Microfone desligado"); self.voice_state.setObjectName("voiceState")
        rail_layout.addWidget(self.voice_state)
        rail_layout.addSpacing(6)
        rail_footer = QLabel("GEMINI  ·  GROQ"); rail_footer.setObjectName("brandSubtitle")
        rail_layout.addWidget(rail_footer)
        layout.addWidget(side_rail)

        main_area = QWidget(); main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(4, 2, 2, 2); main_layout.setSpacing(15)
        topbar = QHBoxLayout(); topbar.setContentsMargins(3, 4, 3, 2)
        page_title = QLabel("Conversa"); page_title.setObjectName("pageTitle")
        self.page_title = page_title
        topbar.addWidget(page_title); topbar.addStretch(1)
        self.status = QLabel("Pronto"); self.status.setObjectName("statusLabel")
        topbar.addWidget(self.status); main_layout.addLayout(topbar)
        layout.addWidget(main_area, 1); main_layout.addWidget(self.tabs, 1)
        self.tabs.currentChanged.connect(self._update_navigation)

        assistant_page = QWidget(); assistant_layout = QVBoxLayout(assistant_page)
        assistant_layout.setContentsMargins(20, 18, 20, 18); assistant_layout.setSpacing(12)
        assistant_layout.addWidget(QLabel(
            "Comandos: ‘abrir calculadora’, ‘digitar: texto’, ‘pressionar: enter’ e "
            "‘agir: pedido na tela’. Use ‘abrir exe: caminho completo’ para outros apps. "
            "Ações locais pedem confirmação."))
        self.load_older_button = QPushButton("Carregar mensagens anteriores")
        self.load_older_button.clicked.connect(self.load_older_history)
        self.load_older_button.hide()
        assistant_layout.addWidget(self.load_older_button)
        self.chat = QTextBrowser(); self.chat.setOpenExternalLinks(True)
        assistant_layout.addWidget(self.chat, 1)
        self.search_checkbox = QCheckBox("Pesquisar na web com Gemini nesta solicitação")
        self.search_checkbox.setToolTip("Ativa Google Search grounding; a API pode consumir cota adicional.")
        assistant_layout.addWidget(self.search_checkbox)
        assistant_actions = QHBoxLayout()
        voice_hint = QLabel("A escuta contínua identifica sua fala enquanto estiver ativada na barra lateral.")
        voice_hint.setObjectName("mutedLabel")
        assistant_actions.addWidget(voice_hint, 1)
        vision = QPushButton("Analisar minha tela…")
        vision.clicked.connect(self.analyze_screen); assistant_actions.addWidget(vision)
        self.live_vision_button = QPushButton("Iniciar visão contínua")
        self.live_vision_button.setCheckable(True)
        self.live_vision_button.clicked.connect(self.toggle_live_vision)
        assistant_actions.addWidget(self.live_vision_button)
        self.clap_button = QPushButton("Ativar duplo aplauso")
        self.clap_button.setCheckable(True)
        self.clap_button.clicked.connect(self.toggle_clap_detection)
        assistant_actions.addWidget(self.clap_button)
        assistant_layout.addLayout(assistant_actions)
        chat_row = QHBoxLayout()
        self.input = QLineEdit(); self.input.setPlaceholderText("Escreva um comando…")
        self.input.returnPressed.connect(self.send); chat_row.addWidget(self.input, 1)
        send = QPushButton("Enviar"); send.clicked.connect(self.send); chat_row.addWidget(send)
        send.setObjectName("primaryAction")
        assistant_layout.addLayout(chat_row)
        self.tabs.addTab(assistant_page, "Assistente")

        self.media_panel = QWidget(); media_layout = QVBoxLayout(self.media_panel)
        media_layout.setContentsMargins(20, 18, 20, 18); media_layout.setSpacing(12)
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
        play_button = QPushButton("Tocar / buscar"); play_button.clicked.connect(self.play_media)
        media_controls_layout.addWidget(play_button)
        pause_button = QPushButton("Pausar"); pause_button.clicked.connect(self.pause_media)
        media_controls_layout.addWidget(pause_button)
        download_button = QPushButton("Baixar áudio…"); download_button.clicked.connect(self.download_media)
        media_controls_layout.addWidget(download_button); media_layout.addWidget(self.media_controls)
        self.tabs.addTab(self.media_panel, "Mídia")
        self.player = QMediaPlayer(self); self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.errorOccurred.connect(lambda *_: self.media_title.setText("Falha ao abrir mídia"))

        integrations_page = QWidget(); integrations_layout = QVBoxLayout(integrations_page)
        integrations_layout.setContentsMargins(20, 18, 20, 18); integrations_layout.setSpacing(12)
        def add_section_title(text: str):
            title = QLabel(text); title.setObjectName("sectionLabel")
            integrations_layout.addWidget(title)

        add_section_title("PREFERÊNCIAS E MEMÓRIA LOCAL")
        settings_row = QHBoxLayout()
        settings = QPushButton("Configurações"); settings.clicked.connect(self.setup)
        settings_row.addWidget(settings, 1)
        clear_memory = QPushButton("Apagar memória local…")
        clear_memory.clicked.connect(self.clear_local_memory); settings_row.addWidget(clear_memory, 1)
        integrations_layout.addLayout(settings_row)
        add_section_title("APLICATIVOS DO COMPUTADOR")
        launch_app = QPushButton("Ver todos os aplicativos instalados…")
        launch_app.clicked.connect(self.open_installed_apps)
        integrations_layout.addWidget(launch_app)
        launch_exe = QPushButton("Escolher um arquivo .exe…")
        launch_exe.clicked.connect(self.select_and_open_executable)
        integrations_layout.addWidget(launch_exe)
        add_section_title("COMUNICAÇÃO · GMAIL E WHATSAPP")
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
        add_section_title("INÍCIO DO SISTEMA")
        startup_row = QHBoxLayout()
        autostart = QPushButton("Ativar início automático")
        autostart.clicked.connect(self.enable_autostart); startup_row.addWidget(autostart, 1)
        disable_autostart = QPushButton("Desativar início automático")
        disable_autostart.clicked.connect(self.disable_autostart); startup_row.addWidget(disable_autostart, 1)
        integrations_layout.addLayout(startup_row)
        add_section_title("CÓDIGO · ALTERAÇÕES SEMPRE REVISADAS")
        modify_source = QPushButton("Propor alteração no código do JARVIS…")
        modify_source.clicked.connect(self.propose_source_change)
        integrations_layout.addWidget(modify_source)
        restore_source = QPushButton("Restaurar backup de código…")
        restore_source.clicked.connect(self.restore_source_backup)
        integrations_layout.addWidget(restore_source)
        integrations_layout.addStretch(1)
        self.tabs.addTab(integrations_page, "Integrações")
        saved_messages = memory.history_page(limit=50)
        self.oldest_message_id = saved_messages[0][0] if saved_messages else None
        if saved_messages:
            for _message_id, role, body in saved_messages: self._append(role, body)
            self.load_older_button.setVisible(len(saved_messages) == 50)
        else:
            # A tela inicial explica o HUD sem criar uma mensagem falsa no histórico.
            self.chat.setHtml(
                "<div style='margin:14px 8px;color:#aebbd0'>"
                "<div style='font-size:22px;font-weight:700;color:#e8fff8'>Olá, Matheus.</div>"
                "<p>Este é seu espaço de conversa contínua. Escreva uma mensagem ou ative "
                "<b>escuta automática</b> na barra lateral para falar naturalmente.</p>"
                "<p>Use <b>Analisar minha tela</b> para uma captura pontual ou escreva "
                "<b>agir: clique no botão Salvar</b> para revisar uma ação visual. "
                "A visão contínua só começa depois da sua confirmação.</p>"
                "<p style='color:#7f91aa'>As conversas ficam na memória local. Comandos que "
                "alteram o computador pedem confirmação antes de agir.</p></div>"
            )
        self.clap_worker = None
        self.voice_activation_worker = None
        self.installed_apps_cache = None
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
        if load_settings().get("voice_activation_enabled", False):
            QTimer.singleShot(0, lambda: self.voice_activation_button.setChecked(True))

    def _update_navigation(self, index: int):
        """Mantém o menu lateral e o título sincronizados com a página ativa."""
        labels = ("Conversa", "Mídia", "Integrações")
        for position, button in enumerate(self.nav_buttons):
            button.setChecked(position == index)
        if 0 <= index < len(labels):
            self.page_title.setText(labels[index])

    def _message_markup(self, role: str, body: str) -> str:
        label = "Você" if role in {"user", "private_action"} else "JARVIS"
        safe_body = html.escape(body).replace("\n", "<br>")
        safe_body = re.sub(
            r"(https://[^\s&lt;&gt;]+)",
            lambda match: f'<a href="{match.group(1)}">{match.group(1)}</a>', safe_body)
        return f"<p style='margin:5px 0 14px'><b>{label}</b><br>{safe_body}</p>"

    def _append(self, role: str, body: str):
        self.chat.append(self._message_markup(role, body))

    def load_older_history(self):
        """Prepend an earlier page while keeping the current scroll position steady."""
        if self.oldest_message_id is None:
            self.load_older_button.hide()
            return
        older = memory.history_page(before_id=self.oldest_message_id, limit=50)
        if not older:
            self.load_older_button.hide()
            return
        bar = self.chat.verticalScrollBar()
        distance_from_bottom = bar.maximum() - bar.value()
        cursor = self.chat.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.insertHtml("".join(
            self._message_markup(role, body) for _message_id, role, body in older))
        self.chat.setTextCursor(cursor)
        bar.setValue(bar.maximum() - distance_from_bottom)
        self.oldest_message_id = older[0][0]
        if len(older) < 50:
            self.load_older_button.hide()

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
            consent = QMessageBox.warning(
                self, "Enviar captura para planejar uma ação",
                "A captura atual da tela será enviada ao Gemini para propor uma única ação. "
                "O JARVIS não fará nada antes de mostrar a proposta e pedir outra confirmação. "
                "Continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if consent == QMessageBox.StandardButton.Yes:
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

    def select_and_open_executable(self):
        """Abre o .exe que a pessoa escolheu explicitamente no seletor do Windows."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Escolher aplicativo", "", "Aplicativos Windows (*.exe)")
        if not path:
            return
        try:
            from .computer import open_user_selected_executable
            self._record_private_control_action(
                f"abrir exe: {path}", open_user_selected_executable(path))
        except Exception as exc:
            self.error(str(exc))

    def open_installed_apps(self):
        """Abre a lista do sistema em segundo plano para não congelar o HUD."""
        if self.installed_apps_cache is not None:
            self._show_installed_apps(self.installed_apps_cache)
            return
        if getattr(self, "app_catalog_worker", None) and self.app_catalog_worker.isRunning():
            self.status.setText("Carregando os aplicativos instalados…")
            return
        self.status.setText("Carregando os aplicativos instalados…")
        self.app_catalog_worker = AppCatalogWorker()
        self.app_catalog_worker.loaded.connect(self._show_installed_apps)
        self.app_catalog_worker.failed.connect(self.error)
        self.app_catalog_worker.finished.connect(lambda: self.status.setText("Pronto"))
        self._track_worker(self.app_catalog_worker)
        self.app_catalog_worker.start()

    def _show_installed_apps(self, apps: list[dict[str, str]]):
        self.installed_apps_cache = apps
        if not apps:
            QMessageBox.information(self, "Aplicativos instalados", "Não encontrei aplicativos inicializáveis.")
            return
        dialog = InstalledAppsDialog(apps, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected_app:
            return
        selected = dialog.selected_app
        try:
            from .computer import launch_installed_app
            result = launch_installed_app(selected)
            self._record_control_action(f"abrir aplicativo: {selected['name']}", result)
        except Exception as exc:
            self.error(f"Não foi possível abrir o aplicativo: {exc}")

    def _launch_installed_by_name(self, requested: str, prompt: str):
        """Busca no catálogo em segundo plano; usa o cache nas próximas chamadas."""
        requested = requested.strip()
        if not requested:
            QMessageBox.information(self, "Abrir aplicativo", "Informe o nome do aplicativo.")
            return
        if self.installed_apps_cache is None:
            self.pending_app_launch = (requested, prompt)
            if getattr(self, "app_catalog_worker", None) and self.app_catalog_worker.isRunning():
                return
            self.status.setText("Procurando o aplicativo instalado…")
            self.app_catalog_worker = AppCatalogWorker()
            self.app_catalog_worker.loaded.connect(self._complete_pending_app_launch)
            self.app_catalog_worker.failed.connect(self.error)
            self.app_catalog_worker.finished.connect(lambda: self.status.setText("Pronto"))
            self._track_worker(self.app_catalog_worker)
            self.app_catalog_worker.start()
            return
        self._complete_pending_app_launch(self.installed_apps_cache, (requested, prompt))

    def _complete_pending_app_launch(self, apps: list[dict[str, str]], request=None):
        """Resolve uma busca pendente pelo nome depois de carregar o catálogo."""
        self.installed_apps_cache = apps
        if request is None:
            request = getattr(self, "pending_app_launch", None)
        self.pending_app_launch = None
        if not request:
            return
        requested, prompt = request
        try:
            from .computer import launch_installed_app
            exact = [app for app in apps if app["name"].casefold() == requested.casefold()]
            matches = exact or [app for app in apps if requested.casefold() in app["name"].casefold()]
            if not matches:
                self.error(f"Não encontrei um aplicativo instalado chamado ‘{requested}’.")
                return
            selected = matches[0] if len(matches) == 1 else self._choose_installed_app(matches, requested)
            if selected:
                self._record_control_action(prompt, launch_installed_app(selected))
        except Exception as exc:
            self.error(f"Não foi possível abrir o aplicativo: {exc}")

    def _choose_installed_app(self, apps: list[dict[str, str]], query: str):
        """Quando um nome tem mais de uma correspondência, deixa a pessoa escolher."""
        dialog = InstalledAppsDialog(apps, self)
        dialog.search.setText(query)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.selected_app

    def _start(self, prompt: str, mode: str):
        self._pause_voice_activation()
        search_web = self.search_checkbox.isChecked() and mode in {"text", "spoken"}
        if search_web and not get_secret("gemini"):
            self.error("Pesquisa na web usa Gemini. Cadastre uma chave Gemini em Configurações.")
            self._resume_voice_activation()
            return
        if mode in {"voice", "spoken"}: self._stop_clap_worker()
        if mode not in {"screen", "spoken", "voice"}:
            self._append("user", prompt); memory.add("user", prompt)
        # A consulta inclui o texto atual; reserve 20 itens anteriores depois de removê-lo.
        history = memory.context_recent(limit=21)
        if mode in {"text", "spoken"} and history and history[-1] == ("user", prompt):
            history.pop()  # The provider adapter appends the current prompt itself.
        self.input.setEnabled(False)
        if mode == "screen":
            status = "Enviando captura pontual e pedido à Gemini…"
        elif mode == "plan":
            status = "Enviando captura consentida à Gemini para sugerir uma ação…"
        elif mode == "voice":
            status = "Abrindo o microfone para o comando por voz…"
        elif mode == "spoken":
            provider = load_settings().get("provider", "gemini").capitalize()
            status = f"Enviando transcrição e contexto recente à {provider}…"
        else:
            provider = "Gemini" if search_web else load_settings().get("provider", "gemini").capitalize()
            detail = "mensagem, contexto recente e pesquisa" if search_web else "mensagem e contexto recente"
            status = f"Enviando {detail} à {provider}…"
        self.status.setText(status)
        self.worker = ReplyWorker(prompt, mode, search_web, history)
        self._track_worker(self.worker)
        self.worker.finished_text.connect(self._worker_event)
        self.worker.failed.connect(self.error)
        self.worker.finished.connect(lambda: self.status.setText("Pronto"))
        self.worker.finished.connect(self._resume_voice_activation)
        if mode in {"voice", "spoken"}:
            self.worker.finished.connect(self._resume_clap_worker)
        self.worker.start()

    def toggle_voice_activation(self, enabled: bool):
        """Liga ou desliga a escuta automática; nenhum áudio em espera sai do computador."""
        save_settings({**load_settings(), "voice_activation_enabled": bool(enabled)})
        if not enabled:
            worker = self.voice_activation_worker
            if worker and worker.isRunning():
                worker.stop()
                self.voice_state.setText("Desligando microfone…")
            else:
                self.voice_state.setText("Microfone desligado")
            self.voice_activation_button.setText("Desligar escuta automática" if enabled else "Ligar escuta automática")
            return
        if not get_secret("groq"):
            save_settings({**load_settings(), "voice_activation_enabled": False})
            self.voice_activation_button.blockSignals(True)
            self.voice_activation_button.setChecked(False)
            self.voice_activation_button.blockSignals(False)
            self.voice_activation_button.setText("Ligar escuta automática")
            self.error("Cadastre uma chave Groq em Configurações para transcrever os comandos de voz.")
            return
        if self.voice_activation_worker and self.voice_activation_worker.isRunning():
            self.voice_activation_worker.resume()
            return
        self._stop_clap_worker()
        self.voice_activation_button.setText("Desligar escuta automática")
        self.voice_state.setText("Abrindo microfone…")
        worker = VoiceActivationWorker()
        self.voice_activation_worker = worker
        worker.phrase.connect(self._handle_spoken_phrase)
        worker.state_changed.connect(self._voice_activation_state)
        worker.failed.connect(self._voice_activation_failed)
        worker.finished.connect(lambda worker=worker: self._voice_activation_finished(worker))
        self._track_worker(worker)
        worker.start()

    def _voice_activation_state(self, state: str):
        labels = {
            "escutando": "Escutando fala · áudio ambiente fica local",
            "transcrevendo": "Fala detectada · transcrevendo com Groq",
            "erro": "Falha no microfone",
            "desligado": "Microfone desligado",
        }
        self.voice_state.setText(labels.get(state, state))

    def _voice_activation_failed(self, message: str):
        self.voice_activation_button.setChecked(False)
        save_settings({**load_settings(), "voice_activation_enabled": False})
        self.error(f"Escuta automática foi desligada: {message}")

    def _voice_activation_finished(self, worker):
        if self.voice_activation_worker is worker:
            self.voice_activation_worker = None
        if not self.voice_activation_button.isChecked():
            self.voice_state.setText("Microfone desligado")

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
        if self._quit_requested or not phrase.strip():
            self._resume_voice_activation()
            return
        self._append("user", phrase)
        memory.add("user", phrase)
        if self._dispatch_computer_command(phrase):
            self._resume_voice_activation()
            return
        self._start(phrase, "spoken")

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
                "quadro por segundo. As observações transcritas aparecerão no histórico do HUD e "
                "a voz será reproduzida no computador. Imagens e áudio gerado passam pelo Google "
                "e podem consumir cota. A conexão "
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
            self.status.setText("Microfone ativo · aguardando fala…")
        elif value == "__TRANSCRIBING__":
            self.status.setText("Fala concluída · transcrevendo…")
        elif value == "__BUSY__":
            self.status.setText("Analisando a captura enviada ao Gemini…")
        elif value.startswith("__USER__"):
            text = value[8:]
            self._append("user", text); memory.add("user", text)
        elif value.startswith("__VOICE_COMMAND__"):
            self.pending_voice_command = value[len("__VOICE_COMMAND__"):]
        elif value.startswith("__ANSWER__"):
            self.reply(value[10:])
        elif value.startswith("__PLAN__"):
            self._review_screen_action(value[len("__PLAN__"):])

    def _review_screen_action(self, payload: str):
        """Revalida a proposta e pede aprovação humana antes de tocar mouse/teclado."""
        from .computer import describe_screen_action, validate_screen_action
        try:
            action = validate_screen_action(json.loads(payload))
            description = describe_screen_action(action)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.error(f"Proposta de ação rejeitada: {exc}")
            return
        if action["action"] == "none":
            result = "Não encontrei uma ação de tela segura para esse pedido. Nada foi executado."
            self._append("assistant", result); memory.add("assistant", result)
            self.input.setEnabled(True)
            return
        answer = QMessageBox.question(
            self, "Revisar ação proposta", description + "\n\nExecutar agora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            result = "Ação cancelada. Nenhum clique ou tecla foi enviado."
            self._append("assistant", result); memory.add("assistant", result)
            self.input.setEnabled(True)
            return
        self._yield_focus_to_active_app()
        QTimer.singleShot(500, lambda action=action: self._run_screen_action(action))

    def _run_screen_action(self, action: dict):
        from .computer import perform_screen_action
        try:
            result = perform_screen_action(action)
            self._append("assistant", result); memory.add("assistant", result)
        except Exception as exc:
            self._report_control_failure("executar a ação de tela", exc)
        finally:
            self.input.setEnabled(True)

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
        if self._quit_requested:
            self._pause_voice_activation()
            voice_worker = self.voice_activation_worker
            if voice_worker and voice_worker.isRunning():
                voice_worker.stop()
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
        self._pause_voice_activation()
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
        summary = f"Destinatário: {to}\nAssunto: {title}"
        if not self._review_full_message(
                "Revisar e-mail completo", summary, text, "Confirmar e enviar"):
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
        summary = f"Contato autorizado: {contact} (+{dialog.phone})"
        if not self._review_full_message(
                "Revisar mensagem WhatsApp completa", summary,
                dialog.message_text, "Continuar para o WhatsApp"):
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

    def _review_full_message(self, title: str, summary: str,
                             body: str, confirm_label: str) -> bool:
        """Mostra o conteúdo inteiro num campo rolável antes de um envio externo."""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(700, 560)
        layout = QVBoxLayout(dialog)
        heading = QLabel(summary); heading.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(QLabel("Conteúdo completo:"))
        preview = QTextEdit(dialog); preview.setReadOnly(True); preview.setPlainText(body)
        layout.addWidget(preview, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok,
            parent=dialog)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(confirm_label)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return dialog.exec() == QDialog.DialogCode.Accepted


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS AI")
    app.setOrganizationName("Matheus Moreira")
    lock_directory = Path(QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation))
    lock_directory.mkdir(parents=True, exist_ok=True)
    instance_lock = QLockFile(str(lock_directory / "jarvis-instance.lock"))
    if not instance_lock.tryLock(100):
        QMessageBox.information(
            None, "JARVIS já está aberto",
            "Já existe uma instância do JARVIS em execução. Abra-a pela bandeja do sistema.")
        return
    try:
        # Peça as duas chaves na primeira configuração, para deixar os dois serviços prontos.
        if not get_secret("gemini") or not get_secret("groq"):
            dialog = SetupDialog()
            dialog.gemini.setText(get_secret("gemini") or "")
            dialog.groq.setText(get_secret("groq") or "")
            dialog.email.setText(get_secret("user_email") or "")
            dialog.phone.setText(get_secret("user_phone") or "")
            if dialog.exec() != QDialog.DialogCode.Accepted: return
            missing = [name for name, label in (("gemini", "Gemini"), ("groq", "Groq"))
                       if not get_secret(name)]
            if missing:
                QMessageBox.critical(None, "Configuração necessária",
                    "Cadastre as chaves de API para iniciar: " + ", ".join(missing) + ".")
                return
        window = JarvisWindow()
        if "--background" in sys.argv: window.showMinimized()
        else: window.show()
        return app.exec()
    finally:
        instance_lock.unlock()
