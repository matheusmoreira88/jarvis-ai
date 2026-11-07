"""Loads installed system voices away from the Qt interface thread."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class VoiceCatalogWorker(QThread):
    completed = Signal(list)

    def run(self):
        from .tts import available_system_voices
        self.completed.emit(available_system_voices())

