"""Ações locais explícitas e limitadas a destinos conhecidos."""
from __future__ import annotations

import platform
import subprocess
from html import escape
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


def validate_screen_action(action: dict) -> dict:
    """Aceita só ações pequenas e valida cada valor antes de exibir a confirmação."""
    if not isinstance(action, dict):
        raise ValueError("A proposta de ação da tela veio em um formato inválido.")
    name = action.get("action")
    explanation = action.get("explanation", "")
    if not isinstance(explanation, str):
        raise ValueError("A descrição da ação veio em um formato inválido.")
    clean = {"action": name, "explanation": explanation.strip()[:240]}
    if name == "none":
        return clean
    if name == "click":
        x, y = action.get("x"), action.get("y")
        if isinstance(x, bool) or not isinstance(x, int) or isinstance(y, bool) or not isinstance(y, int):
            raise ValueError("A posição do clique precisa ser numérica.")
        width, height = pyautogui.size()
        source_width = action.get("source_width", width)
        source_height = action.get("source_height", height)
        if (isinstance(source_width, bool) or not isinstance(source_width, int)
                or isinstance(source_height, bool) or not isinstance(source_height, int)
                or source_width <= 0 or source_height <= 0):
            raise ValueError("A resolução da captura veio em um formato inválido.")
        if not (0 <= x < source_width and 0 <= y < source_height):
            raise ValueError("O clique proposto fica fora da tela atual.")
        # A captura usa pixels físicos; o controle pode usar a escala lógica do Windows.
        target_x = round((x + 0.5) * width / source_width - 0.5)
        target_y = round((y + 0.5) * height / source_height - 0.5)
        clean.update(x=max(0, min(width - 1, target_x)),
                     y=max(0, min(height - 1, target_y)))
        return clean
    if name == "scroll":
        direction = action.get("direction")
        if direction not in {"up", "down"}:
            raise ValueError("A rolagem precisa indicar cima ou baixo.")
        clean["direction"] = direction
        return clean
    if name == "press":
        key = action.get("key")
        if not isinstance(key, str) or key.lower() not in SAFE_KEYS | SAFE_SHORTCUTS:
            raise ValueError("A tecla proposta não está na lista permitida.")
        clean["key"] = key.lower()
        return clean
    raise ValueError("A ação proposta não é permitida.")


def describe_screen_action(action: dict) -> str:
    """Converte uma proposta validada em texto legível para a confirmação final."""
    action = validate_screen_action(action)
    if action["action"] == "click":
        description = f"Clique único na posição ({action['x']}, {action['y']})."
    elif action["action"] == "scroll":
        direction = "cima" if action["direction"] == "up" else "baixo"
        description = f"Rolar a janela ativa para {direction}."
    elif action["action"] == "press":
        description = f"Pressionar a tecla {action['key']}."
    else:
        description = "Nenhuma ação sugerida."
    if action["explanation"]:
        # A justificativa vem do modelo e aparece em uma caixa Qt com formatação automática.
        description += f"\n\nMotivo: {escape(action['explanation'])}"
    return description


def perform_screen_action(action: dict) -> str:
    """Executa somente uma ação revisada, após a confirmação explícita do usuário."""
    action = validate_screen_action(action)
    if action["action"] == "click":
        pyautogui.click(action["x"], action["y"])
        return f"Clique enviado na posição ({action['x']}, {action['y']})."
    if action["action"] == "scroll":
        amount = 4 if action["direction"] == "up" else -4
        pyautogui.scroll(amount)
        return f"Rolagem enviada para {'cima' if amount > 0 else 'baixo'}."
    if action["action"] == "press":
        return press_key(action["key"])
    return "Nenhuma ação foi executada."


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
