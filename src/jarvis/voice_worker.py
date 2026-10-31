"""Background microphone worker, separate from the HUD and provider adapter."""
from __future__ import annotations
import time
from threading import Event
import sounddevice as sd
from PySide6.QtCore import QThread, Signal
from .providers import transcribe_groq
from .voice import (BLOCK_SIZE, SAMPLE_RATE, wait_for_spoken_utterance,
                    WakeWordListener, strip_jarvis_prefix)

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
        if self.mode == "wake_word":
            self._listen_loop()
        else:
            # A single stream avoids repeatedly opening the audio device while idle.
            try:
                with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                    blocksize=BLOCK_SIZE, dtype="int16") as stream:
                    self._listen_loop(stream)
            except Exception as exc:
                self.failed.emit(str(exc))
        self.state_changed.emit("desligado")

    def _listen_loop(self, stream=None):
        local_filter = None
        if self.mode == "jarvis_local":
            self.state_changed.emit("carregando-palavra-chave")
            from .local_wake import LocalJarvisFilter
            local_filter = LocalJarvisFilter()
        stream_running = stream is not None
        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                if stream is not None and stream_running:
                    stream.stop()
                    stream_running = False
                time.sleep(0.08)
                continue
            if stream is not None and not stream_running:
                stream.start()
                stream_running = True
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
                        self._stop_event.is_set, self._pause_event.is_set,
                        stream=stream)
                if audio is None:
                    continue
                if (local_filter is not None and time.monotonic() >= self.armed_until
                        and not local_filter.heard_jarvis(audio)):
                    # Only a locally detected wake name can send audio to Groq.
                    continue
                self._pause_event.set()
                if stream is not None and stream_running:
                    stream.stop()
                    stream_running = False
                self.state_changed.emit("transcrevendo")
                phrase = transcribe_groq(audio).strip()
                if self.mode == "wake_word":
                    phrase = strip_jarvis_prefix(phrase) or ""
                elif self.mode in {"jarvis", "jarvis_local"}:
                    detected = strip_jarvis_prefix(phrase)
                    if detected is None and time.monotonic() < self.armed_until:
                        detected = phrase
                    if detected == "":
                        self.armed_until = time.monotonic() + 6
                    phrase = detected or ""
                if phrase:
                    self.armed_until = 0.0
                    self.phrase.emit(phrase)
                else:
                    self._pause_event.clear()
            except Exception as exc:
                self.state_changed.emit("erro")
                self.failed.emit(str(exc))
                self._pause_event.set()


