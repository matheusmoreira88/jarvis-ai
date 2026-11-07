"""Background reply pipeline: capture, cloud text stream, and local speech."""
from __future__ import annotations

import json
import re
from queue import SimpleQueue
from threading import Event, Thread
from PySide6.QtCore import QThread, Signal
from .providers import (analyze_image, fast_local_reply, stream_assistant,
                        propose_screen_action, transcribe_gemini)
from .vision import capture_primary_screen
from .voice import record_utterance, speak_fragments


class SpeechTestWorker(QThread):
    """Reproduz uma frase curta sem congelar a janela de configurações."""
    failed = Signal(str)
    succeeded = Signal()

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def run(self):
        try:
            from .voice import speak
            speak(self.text)
            self.succeeded.emit()
        except Exception as exc:
            self.failed.emit(str(exc))

class ReplyWorker(QThread):
    finished_text = Signal(str)
    partial_text = Signal(str)
    failed = Signal(str)
    speech_failed = Signal(str)

    def __init__(self, prompt: str, mode: str = "text", search_web: bool = False,
                 history: list[tuple[str, str]] | None = None):
        super().__init__()
        self.prompt = prompt
        self.mode = mode
        self.search_web = search_web
        self.history = history or []
        self.stop_event = Event()

    def stop_recording(self):
        """Stop recording or ask an in-flight response to finish promptly."""
        self.stop_event.set()

    def stop(self):
        """Compatibility helper used by the controller during shutdown."""
        self.stop_event.set()

    def _speak_queue(self, fragments):
        try:
            speak_fragments(fragments)
        except Exception as exc:
            # A resposta de texto continua válida mesmo se o alto-falante falhar.
            self.speech_failed.emit(str(exc))

    def run(self):
        try:
            prompt = self.prompt
            image = None
            if self.mode == "voice":
                self.finished_text.emit("__REC__")
                recording = record_utterance(self.stop_event.is_set)
                self.finished_text.emit("__TRANSCRIBING__")
                prompt = transcribe_gemini(recording)
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
                image = capture_primary_screen(monitor_index=1)
                self.finished_text.emit("__BUSY__")
                action = propose_screen_action(prompt, image)
                self.finished_text.emit("__PLAN__" + json.dumps(action, ensure_ascii=False))
                return
            local_answer = fast_local_reply(prompt) if self.mode in {"text", "spoken"} else None
            if local_answer:
                self.partial_text.emit(local_answer)
                self.finished_text.emit("__STREAM_DONE__" + local_answer)
                if self.mode == "spoken":
                    from .voice import speak
                    speak(local_answer)
                return
            speech_queue = SimpleQueue() if self.mode == "spoken" else None
            speech_thread = None
            if speech_queue is not None:
                speech_thread = Thread(target=self._speak_queue, args=(speech_queue,), daemon=True)
                speech_thread.start()
            answer_parts = []
            speech_pending = ""
            try:
                for part in stream_assistant(prompt, self.history, self.search_web):
                    if self.stop_event.is_set():
                        raise RuntimeError("Resposta interrompida pelo usuário.")
                    answer_parts.append(part)
                    self.partial_text.emit(part)
                    if speech_queue is not None:
                        speech_pending += part
                        while True:
                            boundary = re.search(r"[.!?](?:\s|$)|[,;:](?:\s|$)", speech_pending)
                            if not boundary:
                                if len(speech_pending) >= 95:
                                    split = speech_pending.rfind(" ", 0, 95)
                                    if split > 35:
                                        speech_queue.put(speech_pending[:split])
                                        speech_pending = speech_pending[split + 1:]
                                        continue
                                break
                            speech_queue.put(speech_pending[:boundary.end()])
                            speech_pending = speech_pending[boundary.end():]
                answer = "".join(answer_parts) or "Não recebi uma resposta em texto."
                if speech_queue is not None and speech_pending.strip():
                    speech_queue.put(speech_pending)
                self.finished_text.emit("__STREAM_DONE__" + answer)
            finally:
                if speech_queue is not None:
                    speech_queue.put(None)
                if speech_thread is not None:
                    # Nunca bloqueie o encerramento da janela esperando o TTS.
                    speech_thread.join(timeout=2)
        except Exception as exc:
            self.failed.emit(str(exc))
