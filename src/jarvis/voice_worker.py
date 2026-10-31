"""Background microphone worker, separate from the HUD and provider adapter."""
from __future__ import annotations
import time
from threading import Event
from PySide6.QtCore import QThread, Signal
from .providers import transcribe_groq
from .voice import wait_for_spoken_utterance, WakeWordListener, strip_jarvis_prefix

class VoiceActivationWorker(QThread):
    """Accept Jarvis-prefixed transcripts or the optional local Hey Jarvis detector."""
    phrase = Signal(str)
    state_changed = Signal(str)
    failed = Signal(str)

    def __init__(self, mode: str = "jarvis"):
        super().__init__()
        self.mode = mode
        self.armed_until = 0.0
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
        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                time.sleep(0.08)
                continue
            try:
                if self.mode == "wake_word":
                    if not hasattr(self, "_wake_listener"):
                        self.state_changed.emit("carregando-palavra-chave")
                        self._wake_listener = WakeWordListener()
                    self.state_changed.emit("palavra-chave")
                    audio = self._wake_listener.listen_for_command(
                        self._stop_event.is_set,
                        self._pause_event.is_set,
                        on_detected=lambda: self.state_changed.emit("comando"),
                    )
                else:
                    self.state_changed.emit("escutando")
                    audio = wait_for_spoken_utterance(
                        self._stop_event.is_set, self._pause_event.is_set)
                if audio is None:
                    continue
                self._pause_event.set()
                self.state_changed.emit("transcrevendo")
                phrase = transcribe_groq(audio).strip()
                if self.mode == "wake_word":
                    phrase = strip_jarvis_prefix(phrase) or ""
                elif self.mode == "jarvis":
                    detected = strip_jarvis_prefix(phrase)
                    if detected is None and time.monotonic() < self.armed_until:
                        detected = phrase
                    if detected == "":
                        self.armed_until = time.monotonic() + 6
                    phrase = detected or ""
                if phrase:
                    self.phrase.emit(phrase)
                else:
                    self._pause_event.clear()
            except Exception as exc:
                self.state_changed.emit("erro")
                self.failed.emit(str(exc))
                self._pause_event.set()
        self.state_changed.emit("desligado")


