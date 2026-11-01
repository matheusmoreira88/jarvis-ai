"""HUD desktop independente: conversa textual, setup local e histórico."""
from __future__ import annotations

import sys
import re
import html
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import (QThread, QUrl, QTimer, QStandardPaths,
                           Qt, QLockFile, QDateTime)
from PySide6.QtGui import QTextCursor, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QDialog, QFormLayout, QLineEdit, QLabel,
                               QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget,
                               QMessageBox, QHBoxLayout, QFileDialog, QComboBox)
from PySide6.QtWidgets import (QCheckBox, QTextBrowser, QSystemTrayIcon, QMenu, QStyle,
                               QStackedWidget, QTabWidget, QScrollArea, QFrame)
from PySide6.QtWidgets import QInputDialog, QPlainTextEdit
from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget

from . import memory, __version__
from .settings import get_secret, save_secret, load_settings, save_settings
from .dashboard import (CoreOrb, JarvisReactor, DonutGauge, MemoryBrain,
                        ScreenPreviewWorker, ScreenFrameStore)
from .hud_theme import HUD_STYLE
from .reminders import parse_reminder_request
from .routines import validate_routine
from .calendar_import import import_events
from .autostart import set_enabled
from .claps import ClapWorker
from .setup_wizard import SetupDialog
from .updater import UpdateDownloadWorker, UpdateWorker
from .memory_ui import MemoryManagerDialog
from .integration_ui import (
    ContactsDialog,
    GmailWorker,
    WhatsAppComposeDialog,
    WhatsAppWebDialog,
)
from .media_controller import MediaControllerMixin
from .app_catalog_ui import AppCatalogControllerMixin
from .computer_controller import ComputerControllerMixin
from .voice_controller import VoiceControllerMixin
from .vision_controller import VisionControllerMixin
from .reply_controller import ReplyControllerMixin


class JarvisWindow(MediaControllerMixin, AppCatalogControllerMixin, ComputerControllerMixin, VoiceControllerMixin, VisionControllerMixin, ReplyControllerMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS · Assistente desktop")
        self.resize(1280, 860)
        self.setMinimumSize(900, 640)
        self.setStyleSheet(HUD_STYLE)
        central = QWidget(); central.setObjectName("centralSurface"); self.setCentralWidget(central)
        layout = QVBoxLayout(central); layout.setContentsMargins(18, 12, 18, 14); layout.setSpacing(10)

        self.tabs = QTabWidget(); self.tabs.setObjectName("mainTabs"); self.tabs.tabBar().hide()
        main_area = QWidget(); main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(10)
        topbar = QHBoxLayout(); topbar.setContentsMargins(8, 3, 8, 3); topbar.setSpacing(12)
        brand = QLabel("◉  J . A . R . V . I . S")
        brand.setObjectName("commandBrand")
        topbar.addWidget(brand)
        self.page_title = QLabel("NÚCLEO")
        self.page_title.setObjectName("commandSection")
        topbar.addWidget(self.page_title)
        topbar.addStretch(1)
        self.status = QLabel("Pronto"); self.status.setObjectName("statusLabel")
        self.status.setMaximumWidth(420)
        topbar.addWidget(self.status)
        self.clock_label = QLabel(); self.clock_label.setObjectName("commandClock")
        topbar.addWidget(self.clock_label)
        panic_button = QPushButton("INTERROMPER")
        panic_button.setObjectName("panicCommand")
        panic_button.setToolTip("Desliga imediatamente microfone, visão e palmas (Ctrl+Shift+P)")
        panic_button.clicked.connect(self.panic_stop)
        topbar.addWidget(panic_button)
        settings_button = QPushButton("⚙")
        settings_button.setObjectName("roundCommand")
        settings_button.setToolTip("Abrir configurações")
        settings_button.clicked.connect(lambda: self.tabs.setCurrentIndex(3))
        topbar.addWidget(settings_button)
        main_layout.addLayout(topbar)
        layout.addWidget(main_area, 1)
        main_layout.addWidget(self.tabs, 1)

        dock = QWidget(); dock.setObjectName("commandDock")
        dock.setMaximumWidth(720)
        dock_layout = QHBoxLayout(dock)
        dock_layout.setContentsMargins(12, 6, 12, 6); dock_layout.setSpacing(8)
        dock_layout.addStretch(1)
        self.nav_buttons = []
        for index, label in enumerate(("NÚCLEO", "CONVERSA", "MÍDIA")):
            nav = QPushButton(label); nav.setObjectName("dockCommand"); nav.setCheckable(True)
            nav.clicked.connect(lambda checked=False, index=index: self.tabs.setCurrentIndex(index))
            dock_layout.addWidget(nav); self.nav_buttons.append(nav)
        self.nav_buttons[0].setChecked(True)
        apps_button = QPushButton("APLICATIVOS"); apps_button.setObjectName("dockCommand")
        apps_button.clicked.connect(self.open_installed_apps)
        dock_layout.addWidget(apps_button)
        dock_layout.addStretch(1)
        main_layout.addWidget(dock, 0, Qt.AlignmentFlag.AlignHCenter)
        self.voice_state = QLabel("Microfone desligado"); self.voice_state.setObjectName("voiceState")
        self.voice_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.voice_state)
        self.page_fade_animation = None
        self.tabs.currentChanged.connect(self._update_navigation)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()
        self.panic_shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        self.panic_shortcut.activated.connect(self.panic_stop)

        dashboard_page = QWidget(); dashboard_page.setObjectName("heroStage")
        dashboard_layout = QHBoxLayout(dashboard_page)
        dashboard_layout.setContentsMargins(22, 16, 18, 18)
        dashboard_layout.setSpacing(18)
        center_stage = QWidget(); center_stage.setObjectName("reactorStage")
        center_layout = QVBoxLayout(center_stage)
        center_layout.setContentsMargins(8, 0, 8, 0); center_layout.setSpacing(8)
        self.core_orb = JarvisReactor(__version__)
        center_layout.addWidget(self.core_orb, 1, Qt.AlignmentFlag.AlignHCenter)
        self.live_voice_hint = QLabel(f"JARVIS v{__version__} · Diga “Jarvis” e fale seu pedido")
        self.live_voice_hint.setObjectName("heroHint")
        self.live_voice_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.live_voice_hint.setWordWrap(True)
        center_layout.addWidget(self.live_voice_hint)
        self.answer_preview = QLabel("")
        self.answer_preview.setObjectName("answerPreview")
        self.answer_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.answer_preview.setWordWrap(True)
        center_layout.addWidget(self.answer_preview)
        dashboard_layout.addWidget(center_stage, 1)

        command_side = QWidget(); command_side.setObjectName("commandSidePanel")
        command_side.setMinimumWidth(300); command_side.setMaximumWidth(370)
        side_layout = QVBoxLayout(command_side)
        side_layout.setContentsMargins(13, 13, 13, 13); side_layout.setSpacing(10)
        system_title = QLabel("●  SISTEMA"); system_title.setObjectName("panelKicker")
        side_layout.addWidget(system_title)
        metrics = QWidget(); metrics.setObjectName("systemMetrics")
        metrics_layout = QHBoxLayout(metrics)
        metrics_layout.setContentsMargins(8, 7, 8, 7); metrics_layout.setSpacing(6)
        self.system_metric_labels = {}
        for key in ("CPU", "RAM", "DISCO"):
            metric = QLabel(f"{key}\n--")
            metric.setObjectName("systemMetric")
            metric.setAlignment(Qt.AlignmentFlag.AlignCenter)
            metrics_layout.addWidget(metric, 1)
            self.system_metric_labels[key] = metric
        side_layout.addWidget(metrics)
        self.system_uptime_label = QLabel("Inicializando monitor do sistema…")
        self.system_uptime_label.setObjectName("panelSubtle")
        side_layout.addWidget(self.system_uptime_label)
        conversation_title = QLabel("●  CONVERSA AO VIVO")
        conversation_title.setObjectName("panelKicker")
        side_layout.addWidget(conversation_title)
        self.dashboard_chat = QTextBrowser()
        self.dashboard_chat.setObjectName("dashboardChat")
        self.dashboard_chat.setOpenExternalLinks(True)
        side_layout.addWidget(self.dashboard_chat, 1)
        dashboard_send_row = QHBoxLayout(); dashboard_send_row.setSpacing(6)
        self.dashboard_input = QLineEdit()
        self.dashboard_input.setObjectName("dashboardInput")
        self.dashboard_input.setPlaceholderText("Digite um comando ou pergunta…")
        self.dashboard_input.returnPressed.connect(self.send_dashboard)
        dashboard_send_row.addWidget(self.dashboard_input, 1)
        dashboard_send = QPushButton("➤")
        dashboard_send.setObjectName("roundCommand")
        dashboard_send.clicked.connect(self.send_dashboard)
        dashboard_send_row.addWidget(dashboard_send)
        side_layout.addLayout(dashboard_send_row)
        dashboard_layout.addWidget(command_side)
        self.system_timer = QTimer(self)
        self.system_timer.timeout.connect(self._refresh_system_monitor)
        self.system_timer.start(2000)
        self._refresh_system_monitor()
        # O mapa de conhecimento continua existindo e será aberto em sua própria
        # janela na próxima etapa da nova navegação, sem competir com o núcleo.
        self.memory_brain = CoreOrb(__version__, dashboard_page)
        self.memory_brain.hide()
        self.memory_count_label = QLabel("0 lembranças salvas")
        self.memory_count_label.setObjectName("memoryCount")
        self.memory_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.memory_count_label.hide()
        self.screen_preview_title = QLabel("Visão da tela")
        self.screen_preview_label = QLabel()
        self.screen_preview_title.hide(); self.screen_preview_label.hide()
        self.dashboard_metrics = {}
        self.tabs.addTab(dashboard_page, "Painel")

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
        voice_hint = QLabel("A escuta e os recursos do sistema são gerenciados em Configurações.")
        voice_hint.setObjectName("mutedLabel")
        assistant_layout.addWidget(voice_hint)
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
        self.media_title = QLabel("YouTube pronto para buscar")
        media_header.addWidget(self.media_title, 1)
        self.media_window_button = QPushButton("Janela flutuante")
        self.media_window_button.clicked.connect(self.open_mini_player)
        media_header.addWidget(self.media_window_button)
        self.media_fullscreen_button = QPushButton("Tela cheia")
        self.media_fullscreen_button.clicked.connect(self.toggle_media_fullscreen)
        media_header.addWidget(self.media_fullscreen_button)
        self.compact_button = QPushButton("Recolher controles")
        self.compact_button.clicked.connect(self.toggle_compact_media)
        media_header.addWidget(self.compact_button); media_layout.addLayout(media_header)
        self.media_view = QStackedWidget(self.media_panel)
        self.media_idle = QLabel("Escolha um arquivo, URL ou pesquise uma música no YouTube.")
        self.media_idle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_widget = QVideoWidget(self.media_view); self.video_widget.setMinimumHeight(260)
        # Chromium is expensive to start. The YouTube view is created only when
        # somebody actually asks for media, keeping normal HUD startup lighter.
        self.youtube_view = None
        self.youtube_profile = None
        self.youtube_status_timer = QTimer(self)
        self.youtube_status_timer.setInterval(1000)
        self.youtube_status_timer.timeout.connect(self._poll_youtube_status)
        self.mini_player_dialog = None
        self._last_auto_advanced_url = ""
        self.media_view.addWidget(self.media_idle)
        self.media_view.addWidget(self.video_widget)
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
        library_row = QHBoxLayout()
        self.favorite_picker = QComboBox()
        self.favorite_picker.setMinimumWidth(180)
        library_row.addWidget(self.favorite_picker, 1)
        favorite_play = QPushButton("Abrir favorito")
        favorite_play.clicked.connect(self.play_selected_favorite)
        library_row.addWidget(favorite_play)
        favorite_save = QPushButton("☆ Salvar")
        favorite_save.clicked.connect(self.save_media_favorite)
        library_row.addWidget(favorite_save)
        add_queue = QPushButton("+ Fila")
        add_queue.clicked.connect(self.add_media_queue)
        library_row.addWidget(add_queue)
        self.next_media_button = QPushButton("Próxima · 0")
        self.next_media_button.clicked.connect(self.play_next_media)
        library_row.addWidget(self.next_media_button)
        media_layout.addLayout(library_row)
        self._refresh_media_library()
        self.tabs.addTab(self.media_panel, "Mídia")
        self.player = QMediaPlayer(self); self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.playbackStateChanged.connect(self._local_media_state_changed)
        self.player.mediaStatusChanged.connect(self._local_media_status_changed)
        self.player.errorOccurred.connect(lambda *_: self.media_title.setText("Falha ao abrir mídia"))

        settings_scroll = QScrollArea(); settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        settings_scroll.setObjectName("settingsScroll")
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        integrations_page = QWidget(); integrations_page.setObjectName("settingsContent")
        settings_scroll.setWidget(integrations_page)
        outer_layout = QHBoxLayout(integrations_page)
        outer_layout.setContentsMargins(20, 20, 20, 28)
        settings_column = QWidget(); settings_column.setObjectName("settingsColumn")
        settings_column.setMaximumWidth(830)
        integrations_layout = QVBoxLayout(settings_column)
        integrations_layout.setContentsMargins(0, 0, 0, 0)
        integrations_layout.setSpacing(16)
        outer_layout.addStretch(1); outer_layout.addWidget(settings_column, 1); outer_layout.addStretch(1)

        heading = QLabel("Seu JARVIS")
        heading.setObjectName("settingsHeading")
        integrations_layout.addWidget(heading)
        intro = QLabel("Ajuste o essencial para conversar, ouvir e usar sua tela."
                       " Recursos opcionais ficam recolhidos no fim da página.")
        intro.setObjectName("settingsIntro")
        intro.setWordWrap(True)
        integrations_layout.addWidget(intro)

        def settings_card(title: str, description: str) -> QVBoxLayout:
            card = QWidget(); card.setObjectName("settingsCard")
            body = QVBoxLayout(card)
            body.setContentsMargins(22, 20, 22, 22)
            body.setSpacing(12)
            title_label = QLabel(title); title_label.setObjectName("settingsCardTitle")
            note_label = QLabel(description); note_label.setObjectName("settingsCardNote")
            note_label.setWordWrap(True)
            body.addWidget(title_label); body.addWidget(note_label)
            integrations_layout.addWidget(card)
            return body

        access = settings_card("Conexão", "Guarde sua chave Gemini no cofre deste computador.")
        credentials_form = QFormLayout()
        credentials_form.setSpacing(12)
        credentials_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.gemini_key_input = QLineEdit(get_secret("gemini") or "")
        self.gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.user_email_input = QLineEdit(get_secret("user_email") or "")
        self.user_phone_input = QLineEdit(get_secret("user_phone") or "")
        credentials_form.addRow("Chave Gemini", self.gemini_key_input)
        self.user_email_input.setPlaceholderText("Seu e-mail, se quiser usar integrações")
        self.user_phone_input.setPlaceholderText("Seu telefone, se quiser usar integrações")
        credentials_form.addRow("Seu e-mail (opcional)", self.user_email_input)
        credentials_form.addRow("Seu telefone (opcional)", self.user_phone_input)
        access.addLayout(credentials_form)
        save_settings_button = QPushButton("Salvar configurações")
        save_settings_button.setObjectName("primaryAction")
        save_settings_button.clicked.connect(self._save_settings_page)
        access.addWidget(save_settings_button)

        voice_card = settings_card("Voz e tela", "Diga “Jarvis” para falar. Escolha qual tela ele pode observar.")
        voice_row = QHBoxLayout(); voice_row.setSpacing(10)
        self.voice_activation_button = QPushButton("Ativar voz mãos livres")
        self.voice_activation_button.setObjectName("settingsToggle")
        self.voice_activation_button.setCheckable(True)
        self.voice_activation_button.setToolTip(
            "Diga Jarvis e seu pedido. A palavra é reconhecida no computador "
            "antes de enviar o comando para transcrição.")
        self.voice_activation_button.toggled.connect(self.toggle_voice_activation)
        voice_row.addWidget(self.voice_activation_button, 1)
        self.live_vision_button = QPushButton("Iniciar visão contínua")
        self.live_vision_button.setObjectName("settingsToggle")
        self.live_vision_button.setCheckable(True)
        self.live_vision_button.clicked.connect(self.toggle_live_vision)
        voice_row.addWidget(self.live_vision_button, 1)
        voice_card.addLayout(voice_row)
        self.screen_monitor_picker = QComboBox()
        try:
            from mss import mss
            with mss() as capture:
                for index in range(1, len(capture.monitors)):
                    monitor = capture.monitors[index]
                    self.screen_monitor_picker.addItem(
                        f"Tela {index} · {monitor['width']}×{monitor['height']}", index)
        except Exception:
            self.screen_monitor_picker.addItem("Tela principal", 1)
        selected_screen = self.screen_monitor_picker.findData(
            load_settings().get("screen_monitor", 1))
        self.screen_monitor_picker.setCurrentIndex(max(0, selected_screen))
        voice_card.addWidget(QLabel("Tela observada"))
        voice_card.addWidget(self.screen_monitor_picker)

        preferences = settings_card("Aparência e memória", "Controle o movimento da interface e o uso das lembranças salvas.")
        self.share_memory_checkbox = QCheckBox("Incluir lembranças salvas no contexto enviado à IA")
        self.share_memory_checkbox.setChecked(load_settings().get("share_long_term_memory", True))
        preferences.addWidget(self.share_memory_checkbox)
        self.reduce_motion_checkbox = QCheckBox("Reduzir animações do HUD")
        self.reduce_motion_checkbox.setChecked(load_settings().get("reduce_motion", False))
        preferences.addWidget(self.reduce_motion_checkbox)
        open_memories = QPushButton("Ver lembranças e lembretes…")
        open_memories.clicked.connect(self.manage_memory)
        preferences.addWidget(open_memories)
        memory_backup_row = QHBoxLayout(); memory_backup_row.setSpacing(10)
        export_memory = QPushButton("Exportar memória…")
        export_memory.clicked.connect(self.export_memory_backup)
        memory_backup_row.addWidget(export_memory, 1)
        import_memory = QPushButton("Importar memória…")
        import_memory.clicked.connect(self.import_memory_backup)
        memory_backup_row.addWidget(import_memory, 1)
        preferences.addLayout(memory_backup_row)
        clear_memory = QPushButton("Apagar conversa e memória local…")
        clear_memory.clicked.connect(self.clear_local_memory)
        preferences.addWidget(clear_memory)

        system_card = settings_card("Aplicativo", "Atualize o JARVIS e escolha se ele inicia com o Windows.")
        startup_row = QHBoxLayout(); startup_row.setSpacing(10)
        autostart = QPushButton("Iniciar com o Windows")
        autostart.clicked.connect(self.enable_autostart); startup_row.addWidget(autostart, 1)
        disable_autostart = QPushButton("Não iniciar automaticamente")
        disable_autostart.clicked.connect(self.disable_autostart); startup_row.addWidget(disable_autostart, 1)
        system_card.addLayout(startup_row)
        update_row = QHBoxLayout(); update_row.setSpacing(10)
        check_update = QPushButton("Verificar atualizações")
        check_update.clicked.connect(self.check_for_updates)
        self.update_state_label = QLabel(f"Versão {__version__}")
        update_row.addWidget(check_update); update_row.addWidget(self.update_state_label, 1)
        system_card.addLayout(update_row)
        rollback_update = QPushButton("Restaurar instalador anterior verificado…")
        rollback_update.clicked.connect(self.restore_previous_version)
        system_card.addWidget(rollback_update)
        self.api_usage_label = QLabel()
        self.api_usage_label.setObjectName("settingsCardNote")
        self.api_usage_label.setWordWrap(True)
        system_card.addWidget(self.api_usage_label)
        self.api_usage_timer = QTimer(self)
        self.api_usage_timer.timeout.connect(self._refresh_api_usage)
        self.api_usage_timer.start(10_000)
        self._refresh_api_usage()
        diagnostics_button = QPushButton("Exportar diagnóstico para suporte…")
        diagnostics_button.clicked.connect(self.export_diagnostics)
        system_card.addWidget(diagnostics_button)
        save_preferences = QPushButton("Salvar preferências")
        save_preferences.setObjectName("primaryAction")
        save_preferences.clicked.connect(self._save_settings_page)
        system_card.addWidget(save_preferences)

        advanced_toggle = QPushButton("Mostrar recursos opcionais  ▾")
        advanced_toggle.setObjectName("settingsDisclosure")
        advanced_toggle.setCheckable(True)
        integrations_layout.addWidget(advanced_toggle)
        advanced_card = QWidget(); advanced_card.setObjectName("settingsCard")
        advanced_layout = QVBoxLayout(advanced_card)
        advanced_layout.setContentsMargins(22, 20, 22, 22)
        advanced_layout.setSpacing(12)
        advanced_layout.addWidget(QLabel("INTEGRAÇÕES E FERRAMENTAS"))
        advanced_layout.addWidget(QLabel(
            "Use estes recursos se precisar conectar serviços ou personalizar comandos."))
        calendar_button = QPushButton("Importar calendário (.ics)…")
        calendar_button.clicked.connect(self.import_calendar)
        advanced_layout.addWidget(calendar_button)
        quick_row = QHBoxLayout()
        quick_manage = QPushButton("Configurar ações rápidas…")
        quick_manage.clicked.connect(self.manage_quick_actions)
        self.quick_action_hint = QLabel("Nenhuma ação personalizada")
        quick_row.addWidget(quick_manage); quick_row.addWidget(self.quick_action_hint, 1)
        advanced_layout.addLayout(quick_row)
        routines_row = QHBoxLayout()
        routines_button = QPushButton("Configurar rotinas…")
        routines_button.clicked.connect(self.manage_routines)
        self.routines_hint = QLabel("Nenhuma rotina configurada")
        routines_row.addWidget(routines_button); routines_row.addWidget(self.routines_hint, 1)
        advanced_layout.addLayout(routines_row)
        extensions_row = QHBoxLayout()
        extensions_button = QPushButton("Abrir extensões seguras…")
        extensions_button.clicked.connect(self.open_extensions_folder)
        self.extensions_hint = QLabel()
        extensions_row.addWidget(extensions_button); extensions_row.addWidget(self.extensions_hint, 1)
        advanced_layout.addLayout(extensions_row)
        voice_engine_row = QHBoxLayout()
        self.tts_engine_picker = QComboBox()
        self.tts_engine_picker.addItem("Voz do Windows (padrão)", "system")
        self.tts_engine_picker.addItem("Piper neural local (opcional)", "piper")
        tts_index = self.tts_engine_picker.findData(load_settings().get("tts_engine", "system"))
        self.tts_engine_picker.setCurrentIndex(max(0, tts_index))
        voice_engine_row.addWidget(QLabel("Voz de resposta"))
        voice_engine_row.addWidget(self.tts_engine_picker, 1)
        advanced_layout.addLayout(voice_engine_row)
        piper_row = QHBoxLayout()
        self.piper_executable_input = QLineEdit(load_settings().get("piper_executable", ""))
        self.piper_executable_input.setPlaceholderText("piper.exe")
        choose_piper = QPushButton("Executável…")
        choose_piper.clicked.connect(self.select_piper_executable)
        piper_row.addWidget(self.piper_executable_input, 1); piper_row.addWidget(choose_piper)
        advanced_layout.addLayout(piper_row)
        piper_model_row = QHBoxLayout()
        self.piper_model_input = QLineEdit(load_settings().get("piper_model", ""))
        self.piper_model_input.setPlaceholderText("modelo-de-voz.onnx")
        choose_piper_model = QPushButton("Modelo…")
        choose_piper_model.clicked.connect(self.select_piper_model)
        piper_model_row.addWidget(self.piper_model_input, 1); piper_model_row.addWidget(choose_piper_model)
        advanced_layout.addLayout(piper_model_row)
        analyze_screen_button = QPushButton("Analisar minha tela…")
        analyze_screen_button.clicked.connect(self.analyze_screen)
        advanced_layout.addWidget(analyze_screen_button)
        self.clap_button = QPushButton("Ativar duplo aplauso")
        self.clap_button.setCheckable(True)
        self.clap_button.clicked.connect(self.toggle_clap_detection)
        advanced_layout.addWidget(self.clap_button)
        launch_app = QPushButton("Ver todos os aplicativos instalados…")
        launch_app.clicked.connect(self.open_installed_apps)
        advanced_layout.addWidget(launch_app)
        launch_exe = QPushButton("Escolher um arquivo .exe…")
        launch_exe.clicked.connect(self.select_and_open_executable)
        advanced_layout.addWidget(launch_exe)
        gmail_row = QHBoxLayout()
        configure_gmail = QPushButton("Configurar Gmail OAuth…")
        configure_gmail.clicked.connect(self.configure_gmail); gmail_row.addWidget(configure_gmail, 1)
        compose_gmail = QPushButton("Escrever e-mail…")
        compose_gmail.clicked.connect(self.compose_gmail); gmail_row.addWidget(compose_gmail, 1)
        advanced_layout.addLayout(gmail_row)
        wa_row = QHBoxLayout()
        manage_contacts = QPushButton("Contatos permitidos…")
        manage_contacts.clicked.connect(self.manage_whatsapp_contacts); wa_row.addWidget(manage_contacts, 1)
        send_whatsapp = QPushButton("Preparar mensagem WhatsApp…")
        send_whatsapp.clicked.connect(self.compose_whatsapp); wa_row.addWidget(send_whatsapp, 1)
        advanced_layout.addLayout(wa_row)
        modify_source = QPushButton("Propor alteração no código do JARVIS…")
        modify_source.clicked.connect(self.propose_source_change)
        advanced_layout.addWidget(modify_source)
        restore_source = QPushButton("Restaurar backup de código…")
        restore_source.clicked.connect(self.restore_source_backup)
        advanced_layout.addWidget(restore_source)
        from .self_modify import source_editing_available
        if not source_editing_available():
            modify_source.hide()
            restore_source.hide()
            source_note = QLabel(
                "Alterações do próprio código ficam disponíveis somente ao executar "
                "o projeto pelo código-fonte, não no instalador compilado.")
            source_note.setObjectName("settingsCardNote")
            advanced_layout.addWidget(source_note)
        advanced_card.hide()
        def show_advanced(opened: bool):
            advanced_card.setVisible(opened)
            advanced_toggle.setText("Ocultar recursos opcionais  ▴" if opened
                                    else "Mostrar recursos opcionais  ▾")
        advanced_toggle.toggled.connect(show_advanced)
        integrations_layout.addWidget(advanced_card)
        integrations_layout.addStretch(1)
        for label in integrations_page.findChildren(QLabel):
            label.setWordWrap(True)
        self.tabs.addTab(settings_scroll, "Configurações")
        saved_messages = memory.history_page(limit=50)
        self.oldest_message_id = saved_messages[0][0] if saved_messages else None
        if saved_messages:
            for _message_id, role, body in saved_messages: self._append(role, body)
            self.load_older_button.setVisible(len(saved_messages) == 50)
        else:
            # A tela inicial explica o HUD sem criar uma mensagem falsa no histórico.
            self.chat.setHtml(
                "<div style='margin:14px 8px;color:#aebbd0'>"
                "<div style='font-size:22px;font-weight:700;color:#e8fff8'>Olá!</div>"
                "<p>Este é seu espaço de conversa contínua. Escreva uma mensagem ou ative "
                "<b>Jarvis</b> para falar naturalmente, sem botão de gravação.</p>"
                "<p>Use <b>Analisar minha tela</b> para uma captura pontual ou escreva "
                "<b>agir: clique no botão Salvar</b> para revisar uma ação visual. "
                "A prévia local da tela é fluida; a Gemini recebe até 1 imagem por segundo.</p>"
                "<p style='color:#7f91aa'>As conversas ficam na memória local. Comandos que "
                "alteram o computador pedem confirmação antes de agir.</p></div>"
            )
        self.clap_worker = None
        self.voice_activation_worker = None
        self.installed_apps_cache = None
        self._refresh_privacy_indicators()
        self._refresh_routines_hint()
        self._refresh_extensions_hint()
        self.live_vision_worker = None
        self.screen_frame_store = ScreenFrameStore()
        self.core_orb.set_motion_enabled(not load_settings().get("reduce_motion", False))
        self.memory_brain.set_motion_enabled(not load_settings().get("reduce_motion", False))
        self.pending_voice_command = None
        self.memory_map_dialog = None
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
        settings = load_settings()
        settings["activation_mode"] = "jarvis_local"
        if not settings.get("v061_defaults_applied"):
            settings["hands_free_enabled"] = True
            settings["live_vision_enabled"] = True
            settings["v061_defaults_applied"] = True
        settings["voice_activation_enabled"] = bool(settings.get("hands_free_enabled"))
        save_settings(settings)
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self._check_due_reminders)
        self.reminder_timer.start(30_000)
        self._refresh_memory_map()
        QTimer.singleShot(1200, self._check_due_reminders)
        if settings["hands_free_enabled"] and get_secret("gemini"):
            QTimer.singleShot(500, lambda: self.voice_activation_button.setChecked(True))
        if settings["live_vision_enabled"] and get_secret("gemini"):
            QTimer.singleShot(900, lambda: (self.live_vision_button.setChecked(True),
                                           self.toggle_live_vision(True)))

    def _save_settings_page(self):
        """Persiste preferências e credenciais editadas na página Configurações."""
        try:
            save_secret("gemini", self.gemini_key_input.text())
            save_secret("user_email", self.user_email_input.text())
            save_secret("user_phone", self.user_phone_input.text())
            save_settings({**load_settings(), "provider": "gemini",
                           "share_long_term_memory": self.share_memory_checkbox.isChecked(),
                           "reduce_motion": self.reduce_motion_checkbox.isChecked(),
                           "tts_engine": self.tts_engine_picker.currentData(),
                           "piper_executable": self.piper_executable_input.text().strip(),
                           "piper_model": self.piper_model_input.text().strip(),
                           "screen_monitor": self.screen_monitor_picker.currentData() or 1})
            self.core_orb.set_motion_enabled(not self.reduce_motion_checkbox.isChecked())
            self.memory_brain.set_motion_enabled(not self.reduce_motion_checkbox.isChecked())
            preferences = load_settings()
            if get_secret("gemini") and preferences.get("hands_free_enabled", True):
                self.voice_activation_button.setChecked(True)
            if (get_secret("gemini") and preferences.get("live_vision_enabled", True)
                    and not self.live_vision_worker):
                self.live_vision_button.setChecked(True)
                self.toggle_live_vision(True)
            QMessageBox.information(
                self, "Configurações",
                "Preferências e chaves salvas neste computador. A seleção de tela entra "
                "em vigor na próxima ativação da visão contínua.")
        except Exception as exc:
            QMessageBox.warning(self, "Configurações não salvas", str(exc))

    def select_piper_executable(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Piper", self.piper_executable_input.text(), "Piper (piper.exe)")
        if path:
            self.piper_executable_input.setText(path)

    def select_piper_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar modelo de voz", self.piper_model_input.text(),
            "Modelo Piper (*.onnx)")
        if path:
            self.piper_model_input.setText(path)

    def _refresh_privacy_indicators(self):
        """Atualiza o estado interno sem poluir o painel central."""
        label = "Jarvis"
        state = "Ativa" if getattr(self, "voice_activation_button", None) and self.voice_activation_button.isChecked() else "Desligada"
        self._set_dashboard_metric("voz", f"{state} · {label}")
        vision = "Ao vivo" if getattr(self, "live_vision_worker", None) else "Desligada"
        self._set_dashboard_metric("tela", vision)
        if hasattr(self, "screen_preview_title"):
            active = bool(getattr(self, "live_vision_worker", None))
            self.screen_preview_title.setText("VISÃO DA TELA · AO VIVO" if active else "VISÃO DA TELA · DESLIGADA")

    def manage_quick_actions(self):
        """Cria aliases para comandos locais já validados pelo despachante do JARVIS."""
        settings = load_settings()
        actions = settings.get("quick_actions", [])
        if actions:
            choice, ok = QInputDialog.getItem(
                self, "Ações rápidas", "O que deseja fazer?",
                ["Adicionar ação", "Remover ação"], 0, False)
            if not ok:
                return
            if choice == "Remover ação":
                names = [f"{index + 1}. {item.get('title', 'Atalho')} — {item.get('phrase', '')}"
                         for index, item in enumerate(actions) if isinstance(item, dict)]
                selected, ok = QInputDialog.getItem(self, "Remover ação", "Selecione o atalho:", names, 0, False)
                if ok and selected:
                    index = int(selected.split(".", 1)[0]) - 1
                    if 0 <= index < len(actions):
                        actions.pop(index)
                        save_settings({**settings, "quick_actions": actions})
                        self._refresh_quick_action_buttons()
                return
        title, ok = QInputDialog.getText(self, "Ação rápida", "Nome visível do atalho:")
        if not ok or not title.strip():
            return
        phrase, ok = QInputDialog.getText(self, "Ação rápida", "Frase para reconhecer:")
        if not ok or not phrase.strip():
            return
        command, ok = QInputDialog.getText(
            self, "Ação rápida", "Comando local (ex.: abrir calculadora, abrir conversa, abrir mídia):")
        if not ok or not command.strip():
            return
        allowed = ("abrir ", "abrir aplicativo:", "abrir exe:", "abrir conversa", "abrir mídia")
        if not command.strip().lower().startswith(allowed):
            QMessageBox.warning(self, "Comando não permitido",
                "Atalhos só podem chamar comandos locais reconhecidos pelo JARVIS.")
            return
        actions.append({"title": title.strip(), "phrase": phrase.strip(), "command": command.strip()})
        save_settings({**settings, "quick_actions": actions})
        self._refresh_quick_action_buttons()

    def _refresh_quick_action_buttons(self):
        """Atualiza apenas o resumo dos atalhos, que ficam nas configurações."""
        if not hasattr(self, "quick_action_hint"):
            return
        actions = load_settings().get("quick_actions", [])
        names = [item.get("title", "Atalho") for item in actions if isinstance(item, dict)]
        self.quick_action_hint.setText(" · ".join(names) if names else "Nenhuma ação personalizada")

    def _refresh_extensions_hint(self):
        if not hasattr(self, "extensions_hint"):
            return
        from .extensions import load_extensions
        actions, errors = load_extensions()
        summary = f"{len(actions)} comando(s) carregado(s)"
        if errors:
            summary += f" · {len(errors)} manifesto(s) ignorado(s)"
            self.extensions_hint.setToolTip("\n".join(errors))
        else:
            self.extensions_hint.setToolTip("")
        self.extensions_hint.setText(summary)

    def open_extensions_folder(self):
        """Abre a pasta de manifestos e cria um exemplo declarativo na primeira vez."""
        from PySide6.QtGui import QDesktopServices
        from .extensions import EXTENSIONS_DIR, create_example
        create_example()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(EXTENSIONS_DIR)))
        self._refresh_extensions_hint()
        QMessageBox.information(
            self, "Extensões seguras",
            "A pasta foi aberta com um exemplo JSON. As extensões podem adicionar frases "
            "para comandos já permitidos, mas não executam código nem comandos arbitrários. "
            "Salve o arquivo e reabra Configurações para atualizar o indicador.")

    def _refresh_routines_hint(self):
        routines = load_settings().get("routines", [])
        names = [item.get("name", "Rotina") for item in routines if isinstance(item, dict)]
        self.routines_hint.setText(" · ".join(names) if names else "Nenhuma rotina configurada")

    def manage_routines(self):
        """Let the operator compose a short sequence of supported local commands."""
        settings = load_settings()
        routines = settings.get("routines", [])
        if routines:
            choice, ok = QInputDialog.getItem(
                self, "Rotinas", "O que deseja fazer?", ["Adicionar rotina", "Remover rotina"],
                0, False)
            if not ok:
                return
            if choice == "Remover rotina":
                names = [f"{index + 1}. {item.get('name', 'Rotina')}"
                         for index, item in enumerate(routines)]
                selected, ok = QInputDialog.getItem(
                    self, "Remover rotina", "Selecione:", names, 0, False)
                if ok and selected:
                    routines.pop(int(selected.split(".", 1)[0]) - 1)
                    save_settings({**settings, "routines": routines})
                    self._refresh_routines_hint()
                return
        name, ok = QInputDialog.getText(self, "Nova rotina", "Nome (ex.: Modo estudo):")
        if not ok or not name.strip():
            return
        phrase, ok = QInputDialog.getText(self, "Nova rotina", "Frase de ativação:")
        if not ok or not phrase.strip():
            return
        commands, ok = QInputDialog.getMultiLineText(
            self, "Nova rotina", "Um comando por linha (abrir aplicativo:, toca, abrir painel…):")
        if not ok:
            return
        try:
            routine = validate_routine(name, phrase, commands.splitlines())
        except ValueError as exc:
            QMessageBox.warning(self, "Rotina inválida", str(exc))
            return
        routines.append(routine)
        save_settings({**settings, "routines": routines})
        self._refresh_routines_hint()

    def _run_routine(self, routine: dict):
        name = str(routine.get("name", "Rotina"))
        commands = list(routine.get("commands", []))
        self.status.setText(f"Executando rotina · {name}")
        memory.add("private_action", f"Rotina iniciada: {name}")
        for index, command in enumerate(commands):
            QTimer.singleShot(index * 600, lambda command=command:
                              self._dispatch_computer_command(command))

    def check_for_updates(self):
        """Consulta a versão publicada e oferece abrir o instalador se houver novidade."""
        if getattr(self, "update_worker", None) and self.update_worker.isRunning():
            return
        self.update_state_label.setText("Consultando GitHub…")
        self.update_worker = UpdateWorker()
        self.update_worker.latest.connect(self._update_check_completed)
        self.update_worker.failed.connect(self._update_check_failed)
        self.update_worker.start()

    def _update_check_completed(self, metadata: dict):
        """Compare releases and offer only a checksum-verified installer."""
        from . import __version__
        from PySide6.QtGui import QDesktopServices
        tag = metadata.get("tag", "")
        release_url = metadata.get("page_url", "")
        current = tuple(int(part) for part in re.findall(r"\d+", __version__))
        latest = tuple(int(part) for part in re.findall(r"\d+", tag))
        if not tag or not release_url:
            self.update_state_label.setText("Não foi encontrada uma release publicada")
        elif latest <= current:
            self.update_state_label.setText(f"Você está na versão atual ({__version__})")
            QMessageBox.information(self, "Atualizações", "Esta instalação já está atualizada.")
        else:
            self.update_state_label.setText(f"Nova versão disponível: {tag}")
            if not metadata.get("installer_url") or not metadata.get("checksum_url"):
                QMessageBox.information(
                    self, "Atualização disponível",
                    "Esta release não possui o checksum exigido pelo atualizador seguro. "
                    "A página oficial será aberta para instalação manual.")
                QDesktopServices.openUrl(QUrl(release_url))
                return
            notes = metadata.get("notes", "").strip()
            prompt = f"A versão {tag} está disponível. Baixar e verificar agora?"
            if notes:
                prompt += "\n\nPrincipais notas:\n" + notes[:1200]
            answer = QMessageBox.question(self, "Atualização disponível", prompt)
            if answer == QMessageBox.StandardButton.Yes:
                self.update_state_label.setText(f"Baixando e verificando {tag}…")
                self.update_download_worker = UpdateDownloadWorker(metadata)
                self.update_download_worker.completed.connect(self._verified_update_ready)
                self.update_download_worker.failed.connect(self._update_download_failed)
                self.update_download_worker.start()

    def _update_check_failed(self, message: str):
        self.update_state_label.setText("Falha ao consultar atualizações")
        QMessageBox.warning(self, "Atualizações", f"Não foi possível consultar o GitHub: {message}")

    def _verified_update_ready(self, path: str):
        from PySide6.QtGui import QDesktopServices
        self.update_state_label.setText("Instalador verificado por SHA-256")
        answer = QMessageBox.question(
            self, "Atualização verificada",
            "O instalador foi baixado e o SHA-256 corresponde ao publicado na release. "
            "Executar agora? A versão instalada atual continuará disponível no histórico "
            "de releases para reinstalação manual.")
        if answer == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _update_download_failed(self, message: str):
        self.update_state_label.setText("Atualização descartada")
        QMessageBox.warning(
            self, "Atualização não instalada",
            "O download não passou pela verificação de segurança:\n" + message)

    def restore_previous_version(self):
        """Oferece o pacote anterior preservado pelo atualizador, sem ignorar seu checksum."""
        from PySide6.QtGui import QDesktopServices
        from .updater import previous_verified_installer
        installer = previous_verified_installer()
        if installer is None:
            QMessageBox.information(
                self, "Versão anterior",
                "Ainda não há duas versões baixadas e verificadas pelo atualizador. "
                "Depois da próxima atualização, o instalador anterior ficará disponível aqui.")
            return
        answer = QMessageBox.question(
            self, "Restaurar versão anterior",
            f"Executar o pacote anterior verificado?\n\n{installer.name}\n\n"
            "O instalador pedirá a confirmação final antes de substituir a versão atual.")
        if answer == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(installer)))

    def export_diagnostics(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar diagnóstico", "jarvis-diagnostico.json",
            "Diagnóstico JSON (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            from .diagnostics import export_report
            result = export_report(path)
            QMessageBox.information(
                self, "Diagnóstico exportado",
                "Arquivo criado sem chaves, tokens, contatos ou conteúdo das conversas:\n"
                f"{result}")
        except Exception as exc:
            self.error(f"Não foi possível exportar o diagnóstico: {exc}")

    def _update_navigation(self, index: int):
        """Mantém a central inferior e o título sincronizados com a área ativa."""
        labels = ("NÚCLEO", "CONVERSA", "MÍDIA", "CONFIGURAÇÕES")
        for position, button in enumerate(self.nav_buttons):
            button.setChecked(position == index)
        if 0 <= index < len(labels):
            self.page_title.setText(labels[index])

    def _update_clock(self):
        now = QDateTime.currentDateTime()
        self.clock_label.setText(now.toString("HH:mm:ss\nddd, dd MMM yyyy").upper())

    def _refresh_api_usage(self):
        from .usage import today
        usage = today()
        labels = {
            "chat": "conversa", "search": "pesquisa",
            "transcription": "transcrição", "screen_analysis": "captura",
            "screen_action": "ação visual", "live_vision_frames": "quadros ao vivo",
            "code_proposal": "proposta de código",
        }
        parts = [f"{labels.get(key, key)}: {value}"
                 for key, value in sorted(usage["categories"].items())]
        details = " · ".join(parts) if parts else "nenhuma solicitação"
        self.api_usage_label.setText(
            f"Uso local da API hoje: {usage['total']} · {details}. "
            "Este contador não calcula preço e não envia telemetria.")

    def _message_markup(self, role: str, body: str) -> str:
        label = "Você" if role in {"user", "private_action"} else "JARVIS"
        safe_body = html.escape(body).replace("\n", "<br>")
        safe_body = re.sub(
            r"(https://[^\s&lt;&gt;]+)",
            lambda match: f'<a href="{match.group(1)}">{match.group(1)}</a>', safe_body)
        return f"<p style='margin:5px 0 14px'><b>{label}</b><br>{safe_body}</p>"

    def _append(self, role: str, body: str):
        markup = self._message_markup(role, body)
        self.chat.append(markup)
        if hasattr(self, "dashboard_chat"):
            self.dashboard_chat.append(markup)

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
        if self._handle_memory_command(prompt):
            return
        if self._dispatch_computer_command(prompt):
            return
        self._start(prompt, "text")

    def send_dashboard(self):
        prompt = self.dashboard_input.text().strip()
        if not prompt:
            return
        self.dashboard_input.clear()
        if self._handle_memory_command(prompt):
            return
        if self._dispatch_computer_command(prompt):
            return
        self._start(prompt, "text")

    def _refresh_system_monitor(self):
        try:
            import psutil
            values = {
                "CPU": psutil.cpu_percent(interval=None),
                "RAM": psutil.virtual_memory().percent,
                "DISCO": psutil.disk_usage(str(Path.home().anchor or "/")).percent,
            }
            for key, value in values.items():
                self.system_metric_labels[key].setText(f"{key}\n{value:.0f}%")
            uptime_seconds = max(0, int(datetime.now().timestamp() - psutil.boot_time()))
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes = remainder // 60
            self.system_uptime_label.setText(
                f"Sistema ativo há {hours}h {minutes:02d}min · indicadores locais")
        except Exception as exc:
            self.system_uptime_label.setText(
                f"Monitor indisponível · {type(exc).__name__}")

    def _handle_memory_command(self, prompt: str, *, already_recorded: bool = False) -> bool:
        """Save explicit long-term notes and dated reminders without calling an API."""
        text = prompt.strip()
        lowered = text.casefold()
        if not re.match(
                r"^(?:(?:hey\s+)?jarvis[:,]?\s*)?(?:me\s+lemb(?:ra|re)|lemb(?:ra|re)|guarda\s+na\s+mem[oó]ria|salva\s+na\s+mem[oó]ria|anota\s+na\s+mem[oó]ria)\b",
                text, re.IGNORECASE):
            return False

        result = ""
        parsed = parse_reminder_request(text)
        asks_for_reminder = bool(re.match(r"^(?:(?:hey\s+)?jarvis[:,]?\s*)?me\s+lemb(?:ra|re)\s+de\b", text, re.I))
        if parsed:
            item_id = memory.save_reminder(parsed["title"], parsed["due_at"],
                                           parsed["remind_at"], parsed.get("repeat_rule"))
            # Preserve an accompanying plan or explanation as permanent context.
            memory.save_memory("Contexto: " + parsed["title"], text)
            due = datetime.fromisoformat(parsed["due_at"]).astimezone()
            notify = datetime.fromisoformat(parsed["remind_at"]).astimezone()
            result = (f"Lembrete salvo: {parsed['title']} — vence em "
                      f"{due.strftime('%d/%m/%Y às %H:%M')}; vou avisar em "
                      f"{notify.strftime('%d/%m/%Y às %H:%M')}.")
            if parsed.get("repeat_rule"):
                frequency = {"daily": "diariamente", "weekly": "semanalmente",
                             "monthly": "mensalmente", "yearly": "anualmente"}
                result += " Repetição: " + frequency[parsed["repeat_rule"]] + "."
            QTimer.singleShot(100, self._check_due_reminders)
        elif asks_for_reminder:
            result = ("Não identifiquei uma data. Diga, por exemplo: “me lembra de entregar o trabalho amanhã” "
                      "ou “me lembra 1 dia antes, trabalho dia 18/11/2027”.")
        else:
            body = text
            body = re.sub(r"(?i)^\s*(?:(?:hey\s+)?jarvis[:,]?\s*)?", "", body)
            body = re.sub(r"(?i)^\s*(?:lembre?|lembra)\s+(?:que\s+|de\s+)?", "", body).strip()
            body = re.sub(r"(?i)^\s*(?:guarda|salva|anota)\s+na\s+mem[oó]ria\s*", "", body).strip()
            if not body:
                result = "O que você quer que eu guarde na memória?"
            else:
                title = re.sub(r"\s+", " ", body).strip(" .,:;")[:90]
                memory.save_memory(title, body)
                result = "Guardei essa lembrança no computador. Ela não expira; você pode removê-la no mapa de memória."

        if not already_recorded:
            self._append("user", text)
            memory.add("user", text)
        self._append("assistant", result)
        memory.add("assistant", result)
        self.status.setText("Lembrança local salva")
        self._refresh_memory_map()
        return True

    def manage_memory(self):
        """Open the local memory library for reviewing and deleting saved entries."""
        dialog = MemoryManagerDialog(self)
        dialog.exec()
        self._refresh_memory_map()

    def export_memory_backup(self):
        default_name = f"jarvis-memory-{datetime.now().strftime('%Y-%m-%d')}.sqlite3"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar memória", default_name, "Backup SQLite (*.sqlite3)")
        if not path:
            return
        if not path.lower().endswith(".sqlite3"):
            path += ".sqlite3"
        try:
            result = memory.export_database(path)
            QMessageBox.information(self, "Memória exportada", f"Backup salvo em:\n{result}")
        except Exception as exc:
            self.error(f"Não foi possível exportar a memória: {exc}")

    def import_memory_backup(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar memória", "", "Backup SQLite (*.sqlite3 *.db)")
        if not path:
            return
        answer = QMessageBox.question(
            self, "Substituir memória local",
            "Importar este backup substituirá a conversa, lembranças e lembretes atuais. "
            "Uma cópia automática do banco atual será preservada. Continuar?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            backup = memory.import_database(path)
            QMessageBox.information(
                self, "Memória importada",
                "O backup foi importado com sucesso." +
                (f"\nBanco anterior preservado em:\n{backup}" if backup else ""))
            self._refresh_memory_map()
        except Exception as exc:
            self.error(f"Não foi possível importar a memória: {exc}")

    def _refresh_memory_map(self):
        count = memory.long_term_count()
        self.memory_brain.set_memory_count(count)
        self.memory_count_label.setText(
            f"{count:,} lembrança(s) salva(s)".replace(",", "."))

    def import_calendar(self):
        """Bring dated calendar events into the local reminder database."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar calendário", "", "Calendário iCalendar (*.ics)")
        if not path:
            return
        try:
            events, skipped = import_events(path)
            for event in events:
                memory.save_reminder(event["title"], event["due_at"], event["remind_at"])
            self._refresh_memory_map()
            QTimer.singleShot(0, self._check_due_reminders)
            QMessageBox.information(
                self, "Calendário importado",
                f"{len(events)} evento(s) importado(s), com aviso um dia antes. "
                f"{skipped} entrada(s) ignorada(s).")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Importação não concluída", str(exc))

    def _check_due_reminders(self):
        """Notify once at startup and periodically while the HUD remains open."""
        due = memory.due_reminders()
        if not due:
            self._refresh_memory_map()
            return
        ids = [row[0] for row in due]
        lines = []
        for _item_id, title, due_stamp in due:
            due_local = datetime.fromisoformat(due_stamp).astimezone()
            lines.append(f"• {title} — prazo {due_local.strftime('%d/%m/%Y às %H:%M')}")
        message = "Você tem este(s) lembrete(s):\n" + "\n".join(lines)
        self._append("assistant", "⏰ " + message)
        memory.add("assistant", "⏰ " + message)
        if self.isVisible() and not self.isMinimized():
            QMessageBox.information(self, "Lembretes do JARVIS", message)
        elif self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "Lembretes do JARVIS", "\n".join(lines),
                QSystemTrayIcon.MessageIcon.Information, 12000)
        # A conversa persistida permite recuperar o aviso mesmo se o app fechar agora.
        memory.mark_reminders_notified(ids)
        self._refresh_memory_map()

    def _start_screen_preview(self):
        worker = getattr(self, "screen_preview_worker", None)
        if worker and worker.isRunning():
            return
        worker = ScreenPreviewWorker(self.screen_frame_store)
        self.screen_preview_worker = worker
        worker.frame.connect(self._show_screen_preview_frame)
        worker.failed.connect(self.error)
        self._track_worker(worker)
        worker.start()

    def _show_screen_preview_frame(self, image):
        if not self.live_vision_worker or not self.screen_preview_label.isVisible():
            return
        pixmap = QPixmap.fromImage(image)
        self.screen_preview_label.setPixmap(pixmap)

    def _stop_screen_preview(self):
        worker = getattr(self, "screen_preview_worker", None)
        if worker and worker.isRunning():
            worker.stop()

    def setup(self):
        dialog = SetupDialog()
        dialog.gemini.setText(get_secret("gemini") or "")
        dialog.exec()

    def propose_source_change(self):
        """Só altera o próprio programa após gerar, exibir e confirmar uma proposta."""
        from .self_modify import (SOURCE_ROOT, apply_file_update, proposal_diff,
                                  propose_file_update, source_editing_available)

        if not source_editing_available():
            QMessageBox.information(
                self, "Código-fonte indisponível",
                "Este recurso funciona somente ao executar o JARVIS pelo código-fonte.")
            return

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
        note = QLabel(
            "Revise as linhas removidas (-) e adicionadas (+). Um backup local será criado antes de gravar.")
        layout.addWidget(note)
        editor = QPlainTextEdit()
        editor.setPlainText(proposal_diff(path, proposal))
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
        panic_action = menu.addAction("Modo pânico · desligar sensores")
        panic_action.triggered.connect(self.panic_stop)
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
        self._stop_screen_preview()
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
        # A mesma chave Gemini atende conversa, voz, visão e pesquisa.
        if not get_secret("gemini"):
            dialog = SetupDialog()
            dialog.gemini.setText(get_secret("gemini") or "")
            if dialog.exec() != QDialog.DialogCode.Accepted: return
            if not get_secret("gemini"):
                QMessageBox.critical(None, "Configuração necessária",
                    "Cadastre a chave Gemini para iniciar.")
                return
        window = JarvisWindow()
        if "--background" in sys.argv: window.showMinimized()
        else: window.show()
        return app.exec()
    finally:
        instance_lock.unlock()
