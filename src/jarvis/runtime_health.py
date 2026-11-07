"""Fast offline startup checks; no microphone, screen or network is opened here."""
from __future__ import annotations

import importlib.util

from .local_wake import MODEL_NAME, MODEL_ROOT, _valid_model
from .settings import get_secret


def collect_runtime_health() -> dict[str, object]:
    modules = {
        "audio": "sounddevice",
        "screen_capture": "mss",
        "voice_filter": "vosk",
        "gemini_sdk": "google.genai",
    }
    available = {}
    for name, module in modules.items():
        try:
            available[name] = importlib.util.find_spec(module) is not None
        except (ImportError, ModuleNotFoundError):
            available[name] = False
    return {
        "modules": available,
        "gemini_key": bool(get_secret("gemini")),
        "voice_model_installed": _valid_model(MODEL_ROOT / MODEL_NAME),
    }


def blocking_issues(report: dict[str, object] | None = None) -> list[str]:
    report = report or collect_runtime_health()
    modules = report.get("modules", {})
    labels = {
        "audio": "áudio",
        "screen_capture": "captura de tela",
        "voice_filter": "filtro local de voz",
        "gemini_sdk": "conexão Gemini",
    }
    issues = [f"módulo de {labels[name]} ausente"
              for name, ready in modules.items() if not ready]
    if not report.get("gemini_key"):
        issues.append("chave Gemini não configurada")
    return issues

