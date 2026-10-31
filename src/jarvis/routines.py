"""Small, inspectable routines built from the app's existing local commands."""
from __future__ import annotations


def validate_routine(name: str, phrase: str, commands: list[str]) -> dict:
    """Keep routines bounded and limited to navigation, apps, and media commands."""
    name, phrase = name.strip(), phrase.strip()
    cleaned = [command.strip() for command in commands if command.strip()]
    if not name or not phrase or not 1 <= len(cleaned) <= 8:
        raise ValueError("Informe nome, frase e de 1 a 8 comandos.")
    allowed_exact = {"abrir painel", "abrir conversa", "abrir mídia",
                     "abrir configurações", "pausar música", "continuar música"}
    allowed_prefixes = ("abrir aplicativo:", "toca ", "toque ",
                        "pesquise no youtube ", "busque no youtube ")
    for command in cleaned:
        lowered = command.casefold()
        if lowered not in allowed_exact and not lowered.startswith(allowed_prefixes):
            raise ValueError(f"Comando não permitido na rotina: {command}")
    return {"name": name[:60], "phrase": phrase[:100], "commands": cleaned}
