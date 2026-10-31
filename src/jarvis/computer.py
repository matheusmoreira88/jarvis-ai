"""Ações locais explícitas e limitadas a destinos conhecidos."""
from __future__ import annotations

import platform
import subprocess

APP_COMMANDS = {
    "bloco de notas": {"Windows": ["notepad.exe"], "Darwin": ["open", "-a", "TextEdit"], "Linux": ["gedit"]},
    "calculadora": {"Windows": ["calc.exe"], "Darwin": ["open", "-a", "Calculator"], "Linux": ["gnome-calculator"]},
    "explorador de arquivos": {"Windows": ["explorer.exe"], "Darwin": ["open", "."], "Linux": ["xdg-open", "."]},
}


def open_known_app(name: str) -> str:
    """Abre só nomes numa lista fixa; nunca interpreta comandos de shell."""
    command = APP_COMMANDS.get(name.strip().lower(), {}).get(platform.system())
    if not command:
        raise ValueError("Aplicativo fora da lista permitida neste protótipo.")
    subprocess.Popen(command, shell=False)
    return f"Solicitei ao sistema abrir {name}."
