"""Builds the command-only media player without adding a permanent main tab."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)


def build_media_player(window) -> None:
    """Create media controls off-menu; voice/text commands open a floating player."""
    window.media_panel = QWidget(window)
    media_layout = QVBoxLayout(window.media_panel)
    media_layout.setContentsMargins(20, 18, 20, 18)
    media_layout.setSpacing(12)

    media_header = QHBoxLayout()
    media_header.addWidget(QLabel("PLAYER · arquivos, URLs e YouTube"))
    window.media_title = QLabel("YouTube pronto para buscar")
    media_header.addWidget(window.media_title, 1)
    window.media_window_button = QPushButton("Janela flutuante")
    window.media_window_button.clicked.connect(window.open_mini_player)
    media_header.addWidget(window.media_window_button)
    window.media_fullscreen_button = QPushButton("Tela cheia")
    window.media_fullscreen_button.clicked.connect(window.toggle_media_fullscreen)
    media_header.addWidget(window.media_fullscreen_button)
    window.compact_button = QPushButton("Recolher controles")
    window.compact_button.clicked.connect(window.toggle_compact_media)
    media_header.addWidget(window.compact_button)
    media_layout.addLayout(media_header)

    window.media_view = QStackedWidget(window.media_panel)
    window.media_idle = QLabel("Peça uma música ou informe uma URL.")
    window.media_idle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.video_widget = QVideoWidget(window.media_view)
    window.video_widget.setMinimumHeight(260)
    window.youtube_view = None
    window.youtube_profile = None
    window.youtube_status_timer = QTimer(window)
    window.youtube_status_timer.setInterval(1000)
    window.youtube_status_timer.timeout.connect(window._poll_youtube_status)
    window.mini_player_dialog = None
    window._last_auto_advanced_url = ""
    window.media_view.addWidget(window.media_idle)
    window.media_view.addWidget(window.video_widget)
    media_layout.addWidget(window.media_view, 1)

    window.media_controls = QWidget()
    controls_layout = QHBoxLayout(window.media_controls)
    window.media_source = QLineEdit()
    window.media_source.setPlaceholderText("URL ou nome da música no YouTube")
    controls_layout.addWidget(window.media_source, 1)
    for label, handler in (
        ("Arquivo…", window.open_media_file),
        ("Tocar / buscar", window.play_media),
        ("Pausar", window.pause_media),
        ("Baixar áudio…", window.download_media),
    ):
        button = QPushButton(label)
        button.clicked.connect(handler)
        controls_layout.addWidget(button)
    media_layout.addWidget(window.media_controls)

    library_row = QHBoxLayout()
    window.favorite_picker = QComboBox()
    window.favorite_picker.setMinimumWidth(180)
    library_row.addWidget(window.favorite_picker, 1)
    for label, handler in (
        ("Abrir favorito", window.play_selected_favorite),
        ("☆ Salvar", window.save_media_favorite),
        ("+ Fila", window.add_media_queue),
    ):
        button = QPushButton(label)
        button.clicked.connect(handler)
        library_row.addWidget(button)
    window.next_media_button = QPushButton("Próxima · 0")
    window.next_media_button.clicked.connect(window.play_next_media)
    library_row.addWidget(window.next_media_button)
    media_layout.addLayout(library_row)
    window._refresh_media_library()
    window.media_panel.hide()

    window.player = QMediaPlayer(window)
    window.audio_output = QAudioOutput(window)
    window.player.setAudioOutput(window.audio_output)
    window.player.setVideoOutput(window.video_widget)
    window.player.playbackStateChanged.connect(window._local_media_state_changed)
    window.player.mediaStatusChanged.connect(window._local_media_status_changed)
    window.player.errorOccurred.connect(
        lambda *_: window.media_title.setText("Falha ao abrir mídia"))

