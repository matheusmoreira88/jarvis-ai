"""Memory library and animated knowledge-map windows."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QVBoxLayout)

from . import __version__, memory
from .dashboard import CoreOrb
from .hud_theme import HUD_STYLE
from .settings import load_settings


class MemoryManagerDialog(QDialog):
    """Review long-term notes and reminders stored locally by the user."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lembranças e lembretes")
        self.resize(650, 430)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar lembranças e lembretes…")
        self.search.textChanged.connect(self.refresh)
        layout.addWidget(self.search)
        self.items = QListWidget()
        layout.addWidget(self.items, 1)
        self.more_button = QPushButton("Carregar mais")
        self.more_button.clicked.connect(self.load_more)
        layout.addWidget(self.more_button)
        row = QHBoxLayout()
        remove = QPushButton("Excluir selecionado")
        remove.clicked.connect(self.remove_selected)
        clear = QPushButton("Apagar todas as lembranças")
        clear.clicked.connect(self.clear_all)
        close = QPushButton("Fechar")
        close.clicked.connect(self.accept)
        row.addWidget(remove); row.addWidget(clear); row.addStretch(1); row.addWidget(close)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        self.items.clear()
        self.offset = 0
        self.load_more()

    def load_more(self):
        page = memory.saved_items(query=self.search.text(), limit=100, offset=self.offset)
        for kind, item_id, title, detail in page:
            if kind == "reminder":
                due = datetime.fromisoformat(detail).astimezone().strftime("%d/%m/%Y %H:%M")
                label = f"LEMBRETE · {title} · prazo {due}"
            else:
                label = f"LEMBRANÇA · {title} · {detail}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, (kind, item_id))
            self.items.addItem(item)
        self.offset += len(page)
        self.more_button.setVisible(len(page) == 100)

    def remove_selected(self):
        item = self.items.currentItem()
        if item is None:
            return
        kind, item_id = item.data(Qt.ItemDataRole.UserRole)
        memory.delete_saved_item(kind, item_id)
        self.refresh()

    def clear_all(self):
        answer = QMessageBox.question(
            self, "Apagar lembranças", "Apagar todas as lembranças e lembretes salvos?")
        if answer == QMessageBox.StandardButton.Yes:
            memory.clear_long_term_memory()
            self.refresh()


class MemoryMapDialog(QDialog):
    """Independent animated knowledge window opened by voice or keyboard command."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setObjectName("memoryMapWindow")
        self.setWindowTitle("JARVIS · Mapa de conhecimento")
        self.resize(820, 720)
        self.setMinimumSize(560, 500)
        self.setStyleSheet(HUD_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        title = QLabel("MAPA DE CONHECIMENTO")
        title.setObjectName("settingsHeading")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        note = QLabel("Cada lembrança permanente ilumina novas conexões do núcleo neural.")
        note.setObjectName("settingsIntro")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note)
        count = memory.long_term_count()
        self.map = CoreOrb(__version__, self)
        self.map.set_memory_count(count)
        self.map.set_motion_enabled(not load_settings().get("reduce_motion", False))
        layout.addWidget(self.map, 1)
        counter = QLabel(f"{count:,} LEMBRANÇA(S) PERMANENTE(S)".replace(",", "."))
        counter.setObjectName("memoryCount")
        counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(counter)
        manage = QPushButton("GERENCIAR LEMBRANÇAS")
        manage.setObjectName("primaryAction")
        manage.clicked.connect(lambda: MemoryManagerDialog(self).exec())
        layout.addWidget(manage, 0, Qt.AlignmentFlag.AlignHCenter)
