"""Captura de voz com detecção de fim de fala e síntese local."""
from __future__ import annotations

import io
import time
import wave
from collections.abc import Callable

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000
BLOCK_SIZE = 1_024  # Aproximadamente 64 ms por bloco, para encerrar sem longas esperas.
END_SILENCE_SECONDS = 1.15
START_TIMEOUT_SECONDS = 12
MAX_UTTERANCE_SECONDS = 180
SPEECH_THRESHOLD = 0.012  # RMS normalizado; ajustável após testes com microfones variados.


def record_utterance(
    stop_requested: Callable[[], bool] | None = None,
    *,
    max_seconds: int = MAX_UTTERANCE_SECONDS,
) -> bytes:
    """Grava enquanto há fala e fecha após silêncio contínuo, com botão de parada manual."""
    stop_requested = stop_requested or (lambda: False)
    chunks: list[np.ndarray] = []
    pre_roll: list[np.ndarray] = []
    speech_started = False
    last_speech_at: float | None = None
    capture_started_at = time.monotonic()

    # A stream em blocos permite detectar silêncio e também responder rápido ao botão Parar.
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        blocksize=BLOCK_SIZE,
        dtype="int16",
    ) as stream:
        while time.monotonic() - capture_started_at < max_seconds and not stop_requested():
            block, _overflowed = stream.read(BLOCK_SIZE)
            block = np.asarray(block, dtype=np.int16).copy()
            level = float(np.sqrt(np.mean(block.astype(np.float32) ** 2))) / 32768.0
            now = time.monotonic()

            if level >= SPEECH_THRESHOLD:
                if not speech_started:
                    # Preserva um pequeno início da palavra para não cortar a primeira sílaba.
                    chunks.extend(pre_roll[-5:])
                    speech_started = True
                chunks.append(block)
                last_speech_at = now
            elif speech_started:
                # Mantém o som final da frase até completar o tempo de silêncio.
                chunks.append(block)
                if last_speech_at is not None and now - last_speech_at >= END_SILENCE_SECONDS:
                    break
            else:
                pre_roll.append(block)
                if len(pre_roll) > 5:
                    pre_roll.pop(0)
                if now - capture_started_at >= START_TIMEOUT_SECONDS:
                    raise RuntimeError("Não detectei fala. Pressione o microfone e tente novamente.")

    if not speech_started or not chunks:
        raise RuntimeError("A gravação foi parada antes de detectar uma fala.")

    audio = np.concatenate(chunks, axis=0)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(audio.tobytes())
    return buffer.getvalue()


def wait_for_spoken_utterance(
    stop_requested: Callable[[], bool],
    pause_requested: Callable[[], bool],
    *,
    max_seconds: int = MAX_UTTERANCE_SECONDS,
) -> bytes | None:
    """Escuta em espera local e retorna só um segmento que contenha fala detectada."""
    chunks: list[np.ndarray] = []
    pre_roll: list[np.ndarray] = []
    speech_started = False
    speech_blocks = 0
    last_speech_at: float | None = None
    capture_started_at: float | None = None

    # O áudio ambiente só permanece em buffers curtos em memória; nada é enviado em espera.
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        blocksize=BLOCK_SIZE,
        dtype="int16",
    ) as stream:
        while not stop_requested() and not pause_requested():
            block, _overflowed = stream.read(BLOCK_SIZE)
            block = np.asarray(block, dtype=np.int16).copy()
            level = float(np.sqrt(np.mean(block.astype(np.float32) ** 2))) / 32768.0
            now = time.monotonic()

            if level >= SPEECH_THRESHOLD:
                if not speech_started:
                    capture_started_at = now
                    chunks.extend(pre_roll[-5:])
                    speech_started = True
                chunks.append(block)
                speech_blocks += 1
                last_speech_at = now
            elif speech_started:
                chunks.append(block)
                if last_speech_at is not None and now - last_speech_at >= END_SILENCE_SECONDS:
                    break
            else:
                pre_roll.append(block)
                if len(pre_roll) > 5:
                    pre_roll.pop(0)

            if capture_started_at and time.monotonic() - capture_started_at >= max_seconds:
                break

    if stop_requested() or pause_requested() or not speech_started or speech_blocks < 3:
        return None
    return _to_wav_bytes(chunks)


def _to_wav_bytes(chunks: list[np.ndarray]) -> bytes:
    """Empacota um segmento PCM em WAV para o serviço de transcrição."""
    audio = np.concatenate(chunks, axis=0)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(audio.tobytes())
    return buffer.getvalue()


def speak(text: str) -> None:
    """Lê a resposta pelo sintetizador instalado no computador, sem enviar áudio ao provedor."""
    import pyttsx3

    engine = pyttsx3.init()
    try:
        engine.say(text)
        engine.runAndWait()
    finally:
        engine.stop()
