"""Ações locais explícitas e limitadas a destinos conhecidos."""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path

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


def open_user_selected_executable(path: str) -> str:
    """Abre um executável local escolhido pela pessoa, sem passar por um shell."""
    if platform.system() != "Windows":
        raise NotImplementedError("A abertura de executáveis escolhidos está disponível no Windows.")
    executable = Path(path.strip().strip('"')).expanduser()
    if not executable.is_absolute():
        raise ValueError("Informe o caminho completo do arquivo .exe.")
    try:
        executable = executable.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError("Não encontrei esse arquivo .exe.") from exc
    if not executable.is_file() or executable.suffix.lower() != ".exe":
        raise ValueError("Escolha um arquivo executável .exe.")
    subprocess.Popen([str(executable)], cwd=str(executable.parent), shell=False)
    return f"Solicitei ao Windows abrir {executable.name}."


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
