"""Ações locais explícitas e limitadas a destinos conhecidos."""
from __future__ import annotations

import platform
import subprocess

import pyautogui

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


SAFE_KEYS = {
    "enter", "tab", "esc", "backspace", "delete", "up", "down", "left", "right",
    "home", "end", "pageup", "pagedown", "space",
}
SAFE_SHORTCUTS = {
    "ctrl+a", "ctrl+c", "ctrl+v", "ctrl+x", "ctrl+z", "ctrl+s", "ctrl+f",
    "ctrl+shift+z", "alt+tab",
}


def press_key(name: str) -> str:
    """Press only common navigation/editing keys or fixed shortcuts."""
    key = name.strip().lower().replace(" ", "")
    if key in SAFE_KEYS:
        pyautogui.press(key)
    elif key in SAFE_SHORTCUTS:
        pyautogui.hotkey(*key.split("+"))
    else:
        choices = ", ".join(sorted(SAFE_KEYS | SAFE_SHORTCUTS))
        raise ValueError(f"Tecla fora da lista permitida. Opções: {choices}")
    return f"Tecla {key} pressionada."


def click_pointer() -> str:
    """Clica na posição atual do ponteiro, depois da confirmação da interface."""
    pyautogui.click()
    return "Clique enviado na posição atual do ponteiro."


def scroll_page(direction: str) -> str:
    """Rola uma quantidade curta para cima ou para baixo na janela ativa."""
    normalized = direction.strip().lower()
    if normalized not in {"cima", "baixo"}:
        raise ValueError("Use 'cima' ou 'baixo' para rolar a página.")
    pyautogui.scroll(4 if normalized == "cima" else -4)
    return f"Página rolada para {normalized}."
