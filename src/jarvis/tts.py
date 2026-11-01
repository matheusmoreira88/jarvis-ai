"""Síntese local com Piper opcional e retorno confiável à voz do sistema."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from .settings import load_settings


def _system_speak(text: str) -> None:
    import pyttsx3
    engine = pyttsx3.init()
    try:
        engine.say(text)
        engine.runAndWait()
    finally:
        engine.stop()


def _piper_paths(settings: dict) -> tuple[Path, Path]:
    executable = Path(str(settings.get("piper_executable", "")).strip())
    model = Path(str(settings.get("piper_model", "")).strip())
    if not executable.is_file() or executable.suffix.casefold() != ".exe":
        raise RuntimeError("executável do Piper não encontrado")
    if not model.is_file() or model.suffix.casefold() != ".onnx":
        raise RuntimeError("modelo .onnx do Piper não encontrado")
    return executable, model


def piper_available(settings: dict | None = None) -> bool:
    try:
        _piper_paths(settings or load_settings())
        return True
    except RuntimeError:
        return False


def _piper_speak(text: str, settings: dict) -> None:
    executable, model = _piper_paths(settings)
    descriptor, name = tempfile.mkstemp(prefix="jarvis-voice-", suffix=".wav")
    os.close(descriptor)
    output = Path(name)
    try:
        completed = subprocess.run(
            [str(executable), "--model", str(model), "--output_file", str(output)],
            input=text,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=60,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0 or not output.exists() or output.stat().st_size < 44:
            detail = completed.stderr.strip()[-300:]
            raise RuntimeError(detail or "o Piper não produziu o áudio")
        if os.name != "nt":
            raise RuntimeError("a reprodução Piper desta versão requer Windows")
        import winsound
        winsound.PlaySound(str(output), winsound.SND_FILENAME)
    finally:
        output.unlink(missing_ok=True)


def speak_text(text: str) -> None:
    """Fala localmente; se a voz neural falhar, mantém a resposta pela voz do sistema."""
    settings = load_settings()
    if settings.get("tts_engine") == "piper":
        try:
            _piper_speak(text, settings)
            return
        except Exception:
            pass
    _system_speak(text)


def speak_queue(fragments) -> None:
    """Consome respostas em fluxo, sem recriar a voz do Windows a cada frase."""
    settings = load_settings()
    use_piper = settings.get("tts_engine") == "piper" and piper_available(settings)
    if use_piper:
        while True:
            fragment = fragments.get()
            if fragment is None:
                return
            if fragment.strip():
                try:
                    _piper_speak(fragment.strip(), settings)
                except Exception:
                    _system_speak(fragment.strip())
    else:
        import pyttsx3
        engine = pyttsx3.init()
        try:
            while True:
                fragment = fragments.get()
                if fragment is None:
                    break
                if fragment.strip():
                    engine.say(fragment.strip())
                    engine.runAndWait()
        finally:
            engine.stop()
