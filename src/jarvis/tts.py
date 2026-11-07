"""Síntese local com Piper opcional e retorno confiável à voz do sistema."""
from __future__ import annotations

import os
import subprocess
import tempfile
import warnings
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path

from .settings import load_settings


def available_system_voices() -> list[tuple[str, str]]:
    """Return installed Windows/SAPI voices without failing on other platforms."""
    try:
        pyttsx3 = _load_pyttsx3()
        with _speech_thread_context():
            engine = pyttsx3.init()
            try:
                voices = engine.getProperty("voices") or []
                result = []
                seen = set()
                for voice in voices:
                    identifier = str(getattr(voice, "id", "")).strip()
                    if not identifier or identifier in seen:
                        continue
                    seen.add(identifier)
                    name = str(getattr(voice, "name", "") or identifier).strip()
                    result.append((identifier, name))
                return result
            finally:
                engine.stop()
    except Exception:
        return []


def _load_pyttsx3():
    """Carrega o driver sem exibir avisos internos incompatíveis com o HUD sem console."""
    with warnings.catch_warnings():
        # O aviso vem de uma dependência do driver SAPI no Python 3.15; ele não
        # representa falha de reprodução e não deve poluir diagnósticos do JARVIS.
        warnings.simplefilter("ignore", FutureWarning)
        return import_module("pyttsx3")


@contextmanager
def _speech_thread_context():
    """Inicializa o COM na thread atual antes de usar a voz do Windows.

    A resposta é falada por uma nova thread a cada pedido. No Windows, importar
    o mecanismo uma vez não inicializa automaticamente as threads seguintes;
    esse detalhe fazia a primeira resposta funcionar e as próximas ficarem mudas.
    """
    pythoncom = None
    if os.name == "nt":
        try:
            import pythoncom as windows_com
            windows_com.CoInitialize()
            pythoncom = windows_com
        except Exception:
            # O sintetizador ainda pode funcionar sem COM explícito em outros
            # drivers; o erro real será mostrado caso a inicialização falhe.
            pythoncom = None
    try:
        yield
    finally:
        if pythoncom is not None:
            pythoncom.CoUninitialize()


def _configure_system_voice(engine, settings: dict) -> None:
    """Aplica preferências simples e favorece uma voz em português quando houver."""
    volume = max(0.0, min(1.0, float(settings.get("voice_volume", 1.0))))
    rate = max(120, min(260, int(settings.get("voice_rate", 185))))
    engine.setProperty("volume", volume)
    engine.setProperty("rate", rate)
    preferred = str(settings.get("voice_id", "")).strip()
    voices = engine.getProperty("voices") or []
    if preferred and any(voice.id == preferred for voice in voices):
        engine.setProperty("voice", preferred)
        return
    for voice in voices:
        identity = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".casefold()
        languages = " ".join(str(value) for value in getattr(voice, "languages", [])).casefold()
        if any(marker in identity + " " + languages for marker in ("portugu", "pt-br", "brazil")):
            engine.setProperty("voice", voice.id)
            return


def _system_speak(text: str) -> None:
    pyttsx3 = _load_pyttsx3()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        with _speech_thread_context():
            engine = pyttsx3.init()
            try:
                _configure_system_voice(engine, load_settings())
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
        pyttsx3 = _load_pyttsx3()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            with _speech_thread_context():
                engine = pyttsx3.init()
                try:
                    _configure_system_voice(engine, settings)
                    while True:
                        fragment = fragments.get()
                        if fragment is None:
                            break
                        if fragment.strip():
                            engine.say(fragment.strip())
                            engine.runAndWait()
                finally:
                    engine.stop()
