"""Push-to-talk: grava somente enquanto o usuário aciona o botão."""
from __future__ import annotations

import io
import wave
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000
MAX_SECONDS = 15


def record_utterance(seconds: int = MAX_SECONDS) -> bytes:
    frames = int(SAMPLE_RATE * min(max(seconds, 1), MAX_SECONDS))
    audio = sd.rec(frames, samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(SAMPLE_RATE)
        wav.writeframes(np.asarray(audio, dtype=np.int16).tobytes())
    return buffer.getvalue()


def speak(text: str) -> None:
    import pyttsx3
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()
    engine.stop()
